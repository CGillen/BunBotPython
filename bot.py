import discord
import asyncio
import os, datetime
import logging, logging.handlers
import requests
import validators
import shout_errors
from discord.ext import commands
from dotenv import load_dotenv
from pathlib import Path
from streamscrobbler import streamscrobbler

load_dotenv()  # take environment variables from .env.

BOT_TOKEN = os.getenv('BOT_TOKEN')
LOG_FILE_PATH = Path(os.getenv('LOG_FILE_PATH', './')).joinpath('log.txt')
LOG_LEVEL = os.environ.get('LOGLEVEL', 'INFO').upper()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', case_insensitive=True, intents=intents)
server_state = {}
### Available state variables ###
# current_stream_url = URL to playing (or about to be played) shoutcast stream
# current_stream_response = Requests Response object from connecting to shoutcast stream
# voice_client = VoiceClient object where the bot is connected
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
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)



@bot.event
async def on_ready():
  logger.info(f'Logged on as {bot.user}')


@bot.command()
async def play(ctx, url: str):
  if not is_valid_url(url):
    raise commands.BadArgument()

  set_state(ctx.guild.id, 'current_stream_url', url)
  await play_stream(ctx)

@bot.command()
async def leave(ctx):
    await disconnect_stream(ctx)
    await ctx.send("👋 Seeya Later, Gator!")

@bot.command()
async def song(ctx):
    if (get_state(ctx.guild.id, 'current_stream_url')):
      await send_song_info(ctx)
    else:
      raise shout_errors.NoStreamSelected

@bot.command()
async def refresh(ctx):
    if (get_state(ctx.guild.id, 'current_stream_url')):
      await refresh_stream(ctx)
    else:
      raise shout_errors.NoStreamSelected

@bot.event
async def on_command_error(ctx, error):
  logger.debug(error.message)
  if isinstance(error, commands.MissingRequiredArgument):
    # Handle missing argument error for this specific command
    await ctx.send(f"☠️ Please provide a valid Shoutcast v2 stream link Example: `!play [shoutcast v2 stream link]`")
  elif isinstance(error, commands.BadArgument):
    # Handle bad argument error (e.g., type error)
    await ctx.send(f"'☠️ The provided link is not a valid URL. Please provide a valid Shoutcast stream link.'")
  elif isinstance(error, shout_errors.StreamOffline):
    # Steam was found to be offline somewhere
    await ctx.send(f'📋 Error fetching stream. Maybe the stream is down?')
  elif isinstance(error, shout_errors.AuthorNotInVoice):
    # The person sending the command isn't in a voice chat
    await ctx.send(f'😢 You are not in a voice channel. What are you doing? Where am I supposed to go? Don\'t leave me here')
  elif isinstance(error, shout_errors.NoStreamSelected):
    # A stream hasn't started yet
    await ctx.send(f'🙄 No stream started, what did you expect me to do?')
  else:
    # General error handler for other errors
    await ctx.send(f'🤷 An unexpected error occurred while processing your command:\n{error.message}')



### Helper methods ###

def is_valid_url(url):
  return validators.url(url)

async def send_song_info(ctx):
  url = get_state(ctx.guild.id, 'current_stream_url')

  stationinfo = streamscrobbler.get_server_info(url)
  if stationinfo['status'] <= 0:
    logger.warning('Stream not up, unable to update song title')
    raise shout_errors.StreamOffline()

  embed_data = {
    'title': 'Now Playing',
    'color': 0x0099ff,
    'description': f'🎶 {stationinfo['metadata']['song']} 🎶',
    'timestamp': str(datetime.datetime.now(datetime.UTC)),
  }
  embed = discord.Embed.from_dict(embed_data)
  embed.set_footer(text=f'Source: {url}')
  await ctx.send(embed=embed)

async def refresh_stream(ctx):
  await ctx.send('♻️ Refreshing stream, the bot may skip or leave and re-enter')
  await close_stream_connection(ctx)
  await asyncio.sleep(1)
  await play_stream(ctx)

# Start playing music from the stream
#  Check connection/status of server
#  Get stream connection to server
#  Connect to voice channel
#  Start ffmpeg transcoding stream
#  Play stream
#  Start metadata monitor (will close stream if streaming server goes down)
async def play_stream(ctx):
  url = get_state(ctx.guild.id, 'current_stream_url')
  logger.info(f'Starting channel {url}')
  await ctx.send(f'Starting channel {url}')

  stationinfo = streamscrobbler.get_server_info(url)
  ## metadata is the bitrate and current song
  metadata = stationinfo['metadata']
  ## status is the integer to tell if the server is up or down, 0 means down, 1 up, 2 means up but also got metadata.
  status = stationinfo['status']
  logger.info(f'metadata: {metadata}, status: {status}')

  # If the stream status isn't >0, it's offline. Exit out early
  if status <= 0:
    logger.error('Stream is not online')
    raise shout_errors.StreamOffline()

  # Try to get an http stream connection to the ... stream
  try:
    resp = requests.get(url, stream=True)
    resp.raise_for_status()
    set_state(ctx.guild.id, 'current_stream_response', resp)
  except Exception as e: # If there was any error connecting let user know and error out
    logger.error(f'Failed to connect to stream: {e.message}')
    await ctx.send(f'Error fetching stream. Maybe the stream is down?')
    return

  # Connect to voice channel author is currently in
  voice_channel = ctx.message.author.voice.channel
  if voice_channel is None:
    raise shout_errors.AuthorNotInVoice

  voice_client = await voice_channel.connect()

  # Pipe music stream to FFMpeg
  music_stream = discord.FFmpegPCMAudio(resp.raw, pipe=True, options='-filter:a loudnorm=I=-36:LRA=4:TP=-4')
  voice_client.play(music_stream)
  set_state(ctx.guild.id, 'voice_client', voice_client)

  metadata_listener = asyncio.create_task(monitor_metadata(ctx))
  set_state(ctx.guild.id, 'metadata_listener', metadata_listener)
  logger.info('Metadata monitor set')

  await send_song_info(ctx)


# Handle disconnecting the bot from VC after stream closes
async def disconnect_stream(ctx):
  logger.info('Disconnecting bot')

  voice_client = get_state(ctx.guild.id, 'voice_client')
  await voice_client.disconnect()

  logger.info('Bot disconnected')
  # Make sure to close out stream connection, just in case
  close_stream_connection(ctx)

  # Reset the bot for this guild
  clear_state(ctx.guild.id)

async def close_stream_connection(ctx):
  resp = get_state(ctx.guild.id, 'current_stream_response')
  resp.close()

# Watch the stream's metadata to see if it's still up
async def monitor_metadata(ctx):
  logger.info('Starting metadata monitor')

  url = get_state(ctx.guild.id, 'current_stream_url')
  resp = get_state(ctx.guild.id, 'current_stream_response')
  voice_client = get_state(ctx.guild.id, 'voice_client')
  song = None
  num_read_bytes = 0

  try:
    logger.info('Monitoring stream for metadata')
    # This is a looping "daemon"
    while voice_client.is_playing():
      stationinfo = streamscrobbler.get_server_info(url)
      # Stream is over if the server reports closed or no bytes have been read since we last checked
      if stationinfo['status'] <= 0 or resp.raw.tell() <= num_read_bytes:
        logger.info('Stream ended, disconnecting stream')
        raise shout_errors.StreamOffline('Stream is offline')
      else:
        # Check if the song has changed & announce the new one
        if song is None:
          song = stationinfo['metadata']['song']
          logger.info(f'Current station info: {stationinfo}')
        elif song != stationinfo['metadata']['song']:
          await send_song_info(ctx)
          song = stationinfo['metadata']['song']
          logger.info(f'Current station info: {stationinfo}')
        num_read_bytes = resp.raw.tell()
        logger.debug(stationinfo)

      # Only check every 15sec
      await asyncio.sleep(15)
  except Exception as e: # Something went wrong, let's just close it all out
    logger.error(f'Something went wrong while checking stream metadata: {e.message}')
    logger.error(f'Closing down stream & disconnecting bot')
    await disconnect_stream(ctx)
  logger.info('Ending metadata monitor')

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