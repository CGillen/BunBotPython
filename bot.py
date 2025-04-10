from http.client import HTTPResponse
import discord
from discord.ext import commands, tasks
import asyncio
import os, datetime
import logging, logging.handlers
import urllib
import validators
import shout_errors
import urllib_hack
from dotenv import load_dotenv
from pathlib import Path
from streamscrobbler import streamscrobbler

load_dotenv()  # take environment variables from .env.

BOT_TOKEN = os.getenv('BOT_TOKEN')
LOG_FILE_PATH = Path(os.getenv('LOG_FILE_PATH', './')).joinpath('log.txt')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()

# CLUSETERING INFORMATION
CLUSTER_ID = int(os.environ.get('CLUSTER_ID', 0))
TOTAL_CLUSTERS = int(os.environ.get('TOTAL_CLUSTERS', 1))
TOTAL_SHARDS = int(os.environ.get('TOTAL_SHARDS', 1))
NUMBER_OF_SHARDS_PER_CLUSTER = int(TOTAL_SHARDS / TOTAL_CLUSTERS)

# Identify which shards we are, based on our max shards & cluster ID
shard_ids = [
  i
  for i in range(
    CLUSTER_ID * NUMBER_OF_SHARDS_PER_CLUSTER,
    (CLUSTER_ID * NUMBER_OF_SHARDS_PER_CLUSTER) + NUMBER_OF_SHARDS_PER_CLUSTER
  )
  if i < TOTAL_SHARDS
]
# END CLUSTERING

intents = discord.Intents.default()
intents.message_content = True

bot = commands.AutoShardedBot(command_prefix='/', case_insensitive=True, intents=intents, shard_ids=shard_ids, shard_count=TOTAL_SHARDS)
bot.cluster_id = CLUSTER_ID
bot.total_shards = TOTAL_SHARDS

server_state = {}
### Available state variables ###
# current_stream_url = URL to playing (or about to be played) shoutcast stream
# current_stream_response = http.client.HTTPResponse object from connecting to shoutcast stream
# metadata_listener = Asyncio task for listening to metadata (monitor_metadata())
# text_channel = Text channel original play command came from
# start_time = Time the current stream started playing
# cleaning_up = Boolean for if the bot is currently stopping/cleaning up True|None

# Set up logging
logger = logging.getLogger('discord')
logger.setLevel(LOG_LEVEL)  # Set the desired logging level (DEBUG, INFO, etc.)
logging.getLogger('discord.http').setLevel(logging.INFO)
logging.getLogger('discord.client').setLevel(logging.INFO)
logging.getLogger('discord.gateway').setLevel(logging.INFO)

# Create handlers
console_handler = logging.StreamHandler()  # Logs to standard output
file_handler = logging.handlers.RotatingFileHandler(  # Logs to a file
  filename=LOG_FILE_PATH,
  encoding='utf-8',
  maxBytes=32 * 1024 * 1024,  # 32 MiB
  backupCount=5,  # Rotate through 5 files
)

# Set log format
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)



@bot.event
async def on_ready():
  # Initialize a hack for urllib that replaces `ICY 200 OK` as the status line with `HTTP/1.0 200 OK`
  urllib_hack.init_urllib_hack()

  logger.info("Syncing slash commands")
  await bot.tree.sync()
  monitor_metadata.start()
  logger.info(f"Logged on as {bot.user}")
  logger.info(f"Shard IDS: {bot.shard_ids}")
  logger.info(f"Cluster ID: {bot.cluster_id}")



### Custom Checks ###

# Verify bot is not cleaning up from a previous session (TODO)
async def is_not_cleanup(interaction: discord.Interaction):
  if get_state(interaction.guild.id, 'cleaning_up'):
    raise shout_errors.CleaningUp('Bot is still cleaning up from last session')
  return not get_state(interaction.guild.id, 'cleaning_up')

# Verify bot permissions in the initiating channel
def bot_has_channel_permissions(permissions: discord.Permissions):
    def predicate(interaction: discord.Interaction):
        # Get current permissions
        bot_permissions = interaction.channel.permissions_for(interaction.guild.me)
        # Check if bot_permissions contains all of requested permissions
        if bot_permissions >= permissions:
          return True
        # Figure out which permissions we don't have
        missing_permissions = dict((bot_permissions | permissions) ^ bot_permissions)
        # Find which permissions are missing & raise it as an errror
        missing_permissions = [v for v in missing_permissions.keys() if missing_permissions[v]]
        raise discord.app_commands.BotMissingPermissions(missing_permissions=missing_permissions)
    return discord.app_commands.checks.check(predicate)

@bot.tree.command(
    name='play',
    description="Begin playback of a shoutcast/icecast stream"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
@bot_has_channel_permissions(permissions=discord.Permissions(send_messages=True))
# @discord.app_commands.check(is_not_cleanup)
async def play(interaction: discord.Interaction, url: str):
  if not is_valid_url(url):
    raise commands.BadArgument("🙇 I'm sorry, I don't know what that means!")

  await interaction.response.send_message(f"Starting channel {url}")
  await play_stream(interaction, url)

@bot.tree.command(
    name='leave',
    description="Remove the bot from the current call"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
async def leave(interaction: discord.Interaction):
  voice_client = interaction.guild.voice_client
  if voice_client:
    await interaction.response.send_message("👋 Seeya Later, Gator!")
    await stop_playback(interaction.guild)
  else:
    raise shout_errors.NoVoiceClient("😨 I'm not even playing any music! You don't have to be so mean")

@bot.tree.command(
    name="song",
    description="Send an embed with the current song information to this channel"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
async def song(interaction: discord.Interaction):
  url = get_state(interaction.guild.id, 'current_stream_url')
  if (url):
    await interaction.response.send_message("Fetching song title...")
    stationinfo = get_station_info(url)
    await interaction.edit_original_response(content=f"Now Playing: 🎶 {stationinfo['metadata']['song']} 🎶")
  else:
    raise shout_errors.NoStreamSelected("🔎 None. There's no song playing. Turn the stream on maybe?")

@bot.tree.command(
    name="refresh",
    description="Refresh the stream. Bot will leave and come back. Song updates will start displaying in this channel"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
@bot_has_channel_permissions(permissions=discord.Permissions(send_messages=True))
# @discord.app_commands.check(is_not_cleanup)
async def refresh(interaction: discord.Interaction):
  if (get_state(interaction.guild.id, 'current_stream_url')):
    await interaction.response.send_message("♻️ Refreshing stream, the bot may skip or leave and re-enter")
    await refresh_stream(interaction)
  else:
    raise shout_errors.NoStreamSelected

@bot.tree.command(
    name='support',
    description="Information on how to get support"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
async def support(interaction: discord.Interaction):
  embed_data = {
    'title': "BunBot Support",
    'color': 0xF0E9DE,
    'description': f"""
      ❔ Got a question?
         Join us at https://discord.gg/ksZbX723Jn
         The team is always happy to help

      ⚠️ Found an issue?
         Please consider creating a ticket at
         https://github.com/CGillen/BunBotPython/issues
         We'll appreciate it

      🛠️ Or contribute your own fix!
         BunBot is completely open source and free to use under the GPLv3 license
         Just remember to give us a shoutout

      📜 ToS: https://github.com/CGillen/BunBotPython/blob/main/COPYING

      🫶 Like what we're doing?
         Support us on Ko-Fi: https://ko-fi.com/bunbot
    """,
  }
  embed = discord.Embed.from_dict(embed_data)
  await interaction.response.send_message(embed=embed)

@bot.tree.command(
    name="debug",
    description="Show debug stats & info"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
async def debug(interaction: discord.Interaction):
  resp = []
  resp.append("==\tGlobal Info\t==")

  if (await bot.is_owner(interaction.user)):
    resp.append("Guilds:")
    for guild in bot.guilds:
      start_time = get_state(guild.id, 'start_time')

      resp.append(f"- {guild.name} ({guild.id}): user count - {guild.member_count}")
      resp.append(f"\tState: {get_state(guild.id)}")
      if start_time:
        resp.append(f"\tRun time: {datetime.datetime.now(datetime.UTC) - start_time}")
      resp.append(f"\tShard: {guild.shard_id}")
    resp.append("Bot:")
    resp.append(f"\tCluster ID: {bot.cluster_id}")
    resp.append(f"\tShards: {bot.shard_ids}")
  else:
    resp.append(f"Guild count: {len(bot.guilds)}")

  await interaction.response.send_message("\n".join(resp), ephemeral=True)



@bot.tree.error
async def on_command_error(interaction: discord.Interaction, error):
  original_error = error.original if hasattr(error, 'original') else error
  error_message=""
  if isinstance(original_error, commands.MissingRequiredArgument):
    # Handle missing argument error for this specific command
    error_message = "☠️ Please provide a valid Shoutcast v2 stream link Example: `!play [shoutcast v2 stream link]`"
  elif isinstance(original_error, commands.BadArgument):
    # Handle bad argument error (e.g., type error)
    error_message = "☠️ The provided link is not a valid URL. Please provide a valid Shoutcast stream link."
  elif isinstance(original_error, commands.CommandNotFound):
    pass
  elif isinstance(original_error, shout_errors.AlreadyPlaying):
    # Steam was found to be offline somewhere
    error_message = "😱 I'm already playing music! I can't be in two places at once"
  elif isinstance(original_error, shout_errors.StreamOffline):
    # Steam was found to be offline somewhere
    error_message = "📋 Error fetching stream. Maybe the stream is down?"
  elif isinstance(original_error, shout_errors.AuthorNotInVoice):
    # The person sending the command isn't in a voice chat
    error_message = "😢 You are not in a voice channel. What are you doing? Where am I supposed to go? Don't leave me here"
  elif isinstance(original_error, shout_errors.NoStreamSelected):
    # A stream hasn't started yet
    error_message = "🙄 No stream started, what did you expect me to do?"
  elif isinstance(original_error, shout_errors.NoVoiceClient):
    # There isn't a voice client to operate on
    error_message = "🙇 I'm not playing any music! Please stop harassing me"
  elif isinstance(original_error, discord.app_commands.errors.CommandOnCooldown):
    # Commands are being sent too quickly
    error_message = "🥵 Slow down, I can only handle so much!"
  elif isinstance(original_error, discord.app_commands.errors.BotMissingPermissions):
    # We don't have permission to send messages here
    error_message = f"😶 It looks like I'm missing permissions for this channel:\n{error}"
  else:
    # General error handler for other errors
    error_message = f"🤷 An unexpected error occurred while processing your command:\n{error}"
  if interaction.response.is_done():
    original_response = await interaction.original_response()
    original_response_text = original_response.content
    error_message = original_response_text + f"\n{error_message}"
    await interaction.edit_original_response(content=error_message)
  else:
    await interaction.response.send_message(error_message)



### Helper methods ###

def is_valid_url(url):
  return validators.url(url)

# Find information about the playing station & send that as an embed to the original text channel
async def send_song_info(guild_id: int):
  url = get_state(guild_id, 'current_stream_url')
  channel = get_state(guild_id, 'text_channel')
  stationinfo = get_station_info(url)

  # We need to quite now if we can't send messages
  guild = bot.get_guild(guild_id)
  if not channel.permissions_for(guild.me).send_messages:
    logger.warning("we don't have permission to send the song info!")
    return False

  embed_data = {
    'title': "Now Playing",
    'color': 0x0099ff,
    'description': f"🎶 {stationinfo['metadata']['song']} 🎶",
    'timestamp': str(datetime.datetime.now(datetime.UTC)),
  }
  embed = discord.Embed.from_dict(embed_data)
  embed.set_footer(text=f"Source: {url}")
  return await channel.send(embed=embed)

# Retrieve information about the shoutcast stream
def get_station_info(url: str):
  if not url:
    logger.warning("Stream URL not set, can't send song information to channel")
    raise shout_errors.NoStreamSelected()

  stationinfo = streamscrobbler.get_server_info(url)
  if stationinfo['status'] <= 0:
    logger.warning("Stream not up, unable to update song title")
    raise shout_errors.StreamOffline()

  return stationinfo

# Resync the stream by leaving and coming back
async def refresh_stream(interaction: discord.Interaction):
  url = get_state(interaction.guild.id, 'current_stream_url')

  await stop_playback(interaction.guild)
  await play_stream(interaction, url)

# Start playing music from the stream
#  Check connection/status of server
#  Get stream connection to server
#  Connect to voice channel
#  Start ffmpeg transcoding stream
#  Play stream
#  Start metadata monitor (will close stream if streaming server goes down)
async def play_stream(interaction, url):
  if not url:
    logger.warning("No stream currently set, can't play nothing")
    raise shout_errors.NoStreamSelected
  # Connect to voice channel author is currently in
  voice_channel = interaction.user.voice.channel
  if voice_channel is None:
    raise shout_errors.AuthorNotInVoice
  # Find if voice client is already playing music
  voice_client = interaction.guild.voice_client
  if voice_client and voice_client.is_playing():
    raise shout_errors.AlreadyPlaying

  logger.info(f"Starting channel {url}")

  stationinfo = streamscrobbler.get_server_info(url)
  ## metadata is the bitrate and current song
  metadata = stationinfo['metadata']
  ## status is the integer to tell if the server is up or down, 0 means down, 1 up, 2 means up but also got metadata.
  status = stationinfo['status']
  logger.info(f"metadata: {metadata}, status: {status}")

  # If the stream status isn't >0, it's offline. Exit out early
  if status <= 0:
    logger.error("Stream is not online")
    raise shout_errors.StreamOffline()

  # Try to get an http stream connection to the ... stream
  try:
    resp = urllib.request.urlopen(url, timeout=10)
  except Exception as error: # If there was any error connecting let user know and error out
    logger.error(f"Failed to connect to stream: {error}")
    await interaction.edit_original_response(content="Error fetching stream. Maybe the stream is down?")
    return

  # Connect client to voice channel
  if not voice_client:
    voice_client = await voice_channel.connect()

  # Pipe music stream to FFMpeg
  music_stream = discord.FFmpegPCMAudio(resp, pipe=True, options="-filter:a loudnorm=I=-36:LRA=4:TP=-4")
  # voice_client.play(music_stream)
  voice_client.play(music_stream, after=lambda e: asyncio.run_coroutine_threadsafe(voice_client.disconnect(), bot.loop))

  # Everything was successful, lets keep all the data
  set_state(interaction.guild.id, 'current_stream_url', url)
  set_state(interaction.guild.id, 'current_stream_response', resp)
  set_state(interaction.guild.id, 'text_channel', interaction.channel)
  set_state(interaction.guild.id, 'start_time', datetime.datetime.now(datetime.UTC))

  # And let the user know what song is playing
  await send_song_info(interaction.guild.id)


# Disconnect the bot, close the stream, and reset state
async def stop_playback(guild: discord.Guild):
  # Let the bot know we're cleaning up and it needs to wait before any more commands are processed
  set_state(guild.id, 'cleaning_up', True)

  voice_client = guild.voice_client
  if voice_client and voice_client.is_playing():
    while voice_client.is_playing():
      voice_client.stop()
      logger.debug("Attempting to stop client")
      await asyncio.sleep(1)
    logger.info("voice client stopped")
  if voice_client and voice_client.is_connected():
    while voice_client.is_connected():
      await voice_client.disconnect()
      logger.debug("Attempting to disconnect client")
      await asyncio.sleep(1)
    logger.info("voice client disconnected")

  # Reset the bot for this guild first, then we can do cleanup
  logger.debug(f"Clearing guild state: {get_state(guild.id)}")
  clear_state(guild.id)
  logger.debug(f"Guild state cleared: {get_state(guild.id)}")


@tasks.loop(seconds = 15)
async def monitor_metadata():
  try:
    logger.debug(f"Checking metadata for all streams")
    active_guild_ids = all_active_guild_ids()
    for guild_id in active_guild_ids:
      logger.info(f"[{guild_id}]: Checking metadata")

      try:
        logger.debug(f"[{guild_id}]: {get_state(guild_id)}")
        song = get_state(guild_id, 'current_song')
        url = get_state(guild_id, 'current_stream_url')

        if url is None:
          logger.warning("Metadata monitor does not have enough information to check")
          continue

        stationinfo = streamscrobbler.get_server_info(url)
        if stationinfo is None:
          logger.warning(f"[{guild_id}]: Streamscrobbler returned info as None")
        elif stationinfo['status'] <= 0:
          logger.info(f"[{guild_id}]: Stream ended, disconnecting stream")
          logger.debug(stationinfo)
          raise shout_errors.StreamOffline(f"[{guild_id}]: Stream is offline")
        elif stationinfo['metadata'] is None:
          logger.warning(f"[{guild_id}]: Streamscrobbler returned metadata as None from server")
        else:
          # Check if the song has changed & announce the new one
          if isinstance(stationinfo['metadata']['song'], str):
            logger.info(f"[{guild_id}]: {stationinfo}")
            if song is None:
              set_state(guild_id, 'current_song', stationinfo['metadata']['song'])
              logger.info(f"[{guild_id}]: Current station info: {stationinfo}")
            elif song != stationinfo['metadata']['song']:
              if await send_song_info(guild_id):
                set_state(guild_id, 'current_song', stationinfo['metadata']['song'])
              logger.info(f"[{guild_id}]: Current station info: {stationinfo}")
          else:
            logger.warning("Received non-string value from server metadata")
      except shout_errors.StreamOffline as error: # Stream went offline gracefully
        logger.error(f"[{guild_id}]: The stream went offline: {error}")
        channel = get_state(guild_id, 'text_channel')
        guild = bot.get_guild(guild_id)
        if channel.permissions_for(guild.me).send_messages:
          await channel.send("😰 The stream went offline, I gotta go!")
        else:
          logger.warning(f"[{guild_id}]: Do not have permission to send messages in {channel}")
        await stop_playback(guild)
      except Exception as error: # Something went wrong, let's just close it all out
        logger.error(f"[{guild_id}]: Something went wrong while checking stream metadata: {error}")
        channel = get_state(guild_id, 'text_channel')
        guild = bot.get_guild(guild_id)
        if channel.permissions_for(guild.me).send_messages:
          await channel.send("😰 Something happened to the stream! I uhhh... gotta go!")
        else:
          logger.warning(f"[{guild_id}]: Do not have permission to send messages in {channel}")
        await stop_playback(guild)
  except Exception as e:
    logger.error(f"An unhandled error occurred in the metadata listener: {e}")


# Get all ids of guilds that have active streams
def all_active_guild_ids():
  return [x for x in server_state.keys() if server_state[x]]

# Getter for state of a guild
def get_state(guild_id, var=None):
  # Make sure guild is setup for state
  if guild_id not in server_state:
    server_state[guild_id] = {}
  # Return whole state object if no var name was passed
  if var is None:
    return server_state[guild_id]
  # Make sure var is available in guild state
  if var not in server_state[guild_id]:
    return None

  return server_state[guild_id][var]

# Setter for state of a guild
def set_state(guild_id, var, val):
  # Make sure guild is setup for state
  if guild_id not in server_state:
    server_state[guild_id] = {}
  # Make sure var is available in guild state
  if var not in server_state[guild_id]:
    server_state[guild_id][var] = None

  server_state[guild_id][var] = val
  return val

# Clear out state so we can start all over
def clear_state(guild_id):
  # Just throw it all away, idk, maybe we'll need to close and disconnect stuff later
  server_state[guild_id] = {}


bot.run(BOT_TOKEN, log_handler=None)