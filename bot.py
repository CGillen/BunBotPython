import discord
from discord.ext import commands
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

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='/', case_insensitive=True, intents=intents)
server_state = {}
### Available state variables ###
# current_stream_url = URL to playing (or about to be played) shoutcast stream
# current_stream_response = http.client.HTTPResponse object from connecting to shoutcast stream
# metadata_listener = Asyncio task for listening to metadata (monitor_metadata())

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
  logger.info(f"Logged on as {bot.user}")


@bot.tree.command(
    name='play',
    description="Begin playback of a shoutcast/icecast stream"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
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
    await stop_playback(interaction)
  else:
    raise shout_errors.NoVoiceClient("😨 I'm not even playing any music! You don't have to be so mean")

@bot.tree.command(
    name="song",
    description="Send an embed with the current song information to this channel"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
async def song(interaction: discord.Interaction):
  if (get_state(interaction.guild.id, 'current_stream_url')):
    stationinfo = get_station_info(interaction)
    await interaction.response.send_message(f"Now Playing: 🎶 {stationinfo['metadata']['song']} 🎶")
  else:
    raise shout_errors.NoStreamSelected("🔎 None. There's no song playing. Turn the stream on maybe?")

@bot.tree.command(
    name="refresh",
    description="Refresh the stream. Bot will leave and come back"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
async def refresh(interaction: discord.Interaction):
  if (get_state(interaction.guild.id, 'current_stream_url')):
    await interaction.response.send_message("♻️ Refreshing stream, the bot may skip or leave and re-enter")
    await refresh_stream(interaction)
  else:
    raise shout_errors.NoStreamSelected

@bot.tree.command(
    name="debug",
    description="Show debug stats & info"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
async def debug(interaction: discord.Interaction):
  resp = []
  resp.append("==\tGlobal Info\t==")
  ephemeral = False

  if (await bot.is_owner(interaction.user)):
    ephemeral = True
    resp.append("Guilds:")
    for guild in bot.guilds:
      guild_name = f"[{guild.name}]({guild.vanity_url})" if guild.vanity_url else guild.name
      resp.append(f"- {guild_name}: user count - {guild.member_count}")
      resp.append(f"\tState: {get_state(guild.id)}")
  else:
    resp.append(f"Guild count: {bot.guilds.count()}")

  await interaction.response.send_message("\n".join(resp), ephemeral=ephemeral)



@bot.tree.error
async def on_command_error(interaction, error):
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
  else:
    # General error handler for other errors
    error_message = f"🤷 An unexpected error occurred while processing your command:\n{error}"
  if interaction.response.is_done():
    await interaction.channel.send(error_message)
  else:
    await interaction.response.send_message(error_message)



### Helper methods ###

def is_valid_url(url):
  return validators.url(url)

async def send_song_info(interaction: discord.Interaction):
  stationinfo = get_station_info(interaction)
  url = get_state(interaction.guild.id, 'current_stream_url')

  embed_data = {
    'title': "Now Playing",
    'color': 0x0099ff,
    'description': f"🎶 {stationinfo["metadata"]["song"]} 🎶",
    'timestamp': str(datetime.datetime.now(datetime.UTC)),
  }
  embed = discord.Embed.from_dict(embed_data)
  embed.set_footer(text=f"Source: {url}")
  await interaction.channel.send(embed=embed)

def get_station_info(interaction: discord.Interaction):
  url = get_state(interaction.guild.id, 'current_stream_url')
  if not url:
    logger.warning("Stream URL not set, can't send song information to channel")
    raise shout_errors.NoStreamSelected()

  stationinfo = streamscrobbler.get_server_info(url)
  if stationinfo['status'] <= 0:
    logger.warning("Stream not up, unable to update song title")
    raise shout_errors.StreamOffline()

  return stationinfo

async def refresh_stream(interaction: discord.Interaction):
  url = get_state(interaction.guild.id, 'current_stream_url')

  await stop_playback(interaction)
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
    resp = urllib.request.urlopen(url)
  except Exception as error: # If there was any error connecting let user know and error out
    logger.error(f"Failed to connect to stream: {error}")
    await interaction.channel.send("Error fetching stream. Maybe the stream is down?")
    return

  # Connect client to voice channel
  if not voice_client:
    voice_client = await voice_channel.connect()

  # Pipe music stream to FFMpeg
  music_stream = discord.FFmpegPCMAudio(resp, pipe=True, options="-filter:a loudnorm=I=-36:LRA=4:TP=-4")
  # voice_client.play(music_stream)
  voice_client.play(music_stream, after=lambda e: asyncio.run_coroutine_threadsafe(voice_client.disconnect(), bot.loop))

  metadata_listener = bot.loop.create_task(monitor_metadata(interaction))
  # Everything was successful, lets keep all the data
  set_state(interaction.guild.id, 'current_stream_url', url)
  set_state(interaction.guild.id, 'current_stream_response', resp)
  set_state(interaction.guild.id, 'metadata_listener', metadata_listener)
  logger.info("Metadata monitor & state set")

  await send_song_info(interaction)

async def close_stream_connection(interaction: discord.Interaction):
  resp = get_state(interaction.guild.id, 'current_stream_response')
  logger.info("Closing stream")
  if resp:
    try:
      resp.close()
    except Exception as e:
      logger.warning(f"Failed closing stream: #{e}")
  logger.info("resp closed")

async def stop_playback(interaction: discord.Interaction):
  voice_client = interaction.guild.voice_client
  metadata_listener = get_state(interaction.guild.id, 'metadata_listener')
  if voice_client and voice_client.is_playing():
    voice_client.stop()
    logger.info("cancelling metadata listener")
    #TODO Some crashes get stuck here. But running `/refresh` will make this continue and finish this method
    metadata_listener.cancel()
    await metadata_listener

    while voice_client.is_connected():
      logger.debug("waiting for client to leave")
      await asyncio.sleep(1)
    logger.info("voice client stopped")

  logger.debug("Call stream close")
  await close_stream_connection(interaction)
  logger.debug("Stream close called")

  # Reset the bot for this guild
  logger.debug(f"Clearing guild state: {get_state(interaction.guild.id)}")
  clear_state(interaction.guild.id)
  logger.debug(f"Guild state cleared: {get_state(interaction.guild.id)}")

# Watch the stream's metadata to see if it's still up
async def monitor_metadata(interaction: discord.Interaction):
  logger.info("Starting metadata monitor")

  url = get_state(interaction.guild.id, 'current_stream_url')
  resp = get_state(interaction.guild.id, 'current_stream_response')
  voice_client = interaction.guild.voice_client
  song = None

  if None in {url, resp, voice_client}:
    logger.warning("Metadata monitor does not have enough information to start")
    return

  try:
    logger.info("Monitoring stream for metadata")
    # This is a looping "daemon"
    while voice_client.is_playing():
      stationinfo = streamscrobbler.get_server_info(url)
      # Stream is over if the server reports closed or no bytes have been read since we last checked
      if stationinfo is None:
        logger.warning("Streamscrobbler returned info as None from server")
      elif stationinfo['status'] <= 0:
        logger.info("Stream ended, disconnecting stream")
        logger.debug(stationinfo)
        raise shout_errors.StreamOffline("Stream is offline")
      elif stationinfo['metadata'] is None:
        logger.warning("Streamscrobbler returned metadata as None from server")
      else:
        # Check if the song has changed & announce the new one
        if isinstance(stationinfo['metadata']['song'], str):
          if song is None:
            song = stationinfo['metadata']['song']
            logger.info(f"Current station info: {stationinfo}")
          elif song != stationinfo['metadata']['song']:
            await send_song_info(interaction)
            song = stationinfo['metadata']['song']
            logger.info(f"Current station info: {stationinfo}")
          logger.debug(stationinfo)
        else:
          logger.warning("Received non-string value from server metadata")

      # Only check every 15sec
      await asyncio.sleep(15)
  except asyncio.CancelledError:
    logger.info("We've been canceled!")
  except Exception as error: # Something went wrong, let's just close it all out
    logger.error(f"Something went wrong while checking stream metadata: {error}")
    logger.error("Closing down stream & disconnecting bot")
    if voice_client.is_playing():
      await stop_playback(interaction)
  logger.info("Ending metadata monitor")

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
    server_state[guild_id][var] = None

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