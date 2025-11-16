import math
import sys
import discord
from discord.ext import commands, tasks
import asyncio
import os, datetime, signal
import logging, logging.handlers
import urllib
import validators
import psutil
from services.health_monitor import HealthMonitor
from services.metadata_monitor import MetadataMonitor
from services.state_manager import StateManager
from pls_parser import parse_pls
import shout_errors
import urllib_hack
from dotenv import load_dotenv
from pathlib import Path
from streamscrobbler import streamscrobbler
from favorites_manager import get_favorites_manager
from permissions import get_permission_manager, can_set_favorites_check, can_remove_favorites_check, can_manage_roles_check
from stream_validator import get_stream_validator
from input_validator import get_input_validator
from ui_components import FavoritesView, create_favorites_embed, create_favorites_list_embed, create_role_setup_embed, ConfirmationView

load_dotenv()  # take environment variables from .env.

BOT_TOKEN = os.getenv('BOT_TOKEN')
LOG_FILE_PATH = Path(os.getenv('LOG_FILE_PATH', './')).joinpath('log.txt')
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()

# TLS VERIFY
TLS_VERIFY = bool(os.environ.get('TLS_VERIFY', True))

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
intents.members = True
intents.guilds = True
intents.voice_states = True
# minimal member cache: only cache members related to events / interactions
member_cache_flags = discord.MemberCacheFlags.from_intents(intents)

bot = commands.AutoShardedBot(command_prefix='/', case_insensitive=True, intents=intents, member_cache_flags=member_cache_flags , shard_ids=shard_ids, shard_count=TOTAL_SHARDS)
bot.cluster_id = CLUSTER_ID
bot.total_shards = TOTAL_SHARDS


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

_active_heartbeats = {}

# TODO: Clean this up?
STATE_MANAGER = None
MONITORS = []

async def init():
  ### Setup various services ###
  # Create State Manager to manage the state
  global STATE_MANAGER
  STATE_MANAGER = await StateManager.create_state_manager(bot=bot)
  # Create list of monitors
  global MONITORS
  MONITORS = [
    HealthMonitor(sys.modules[__name__], client=bot, state_manager=STATE_MANAGER, logger=logger),
    MetadataMonitor(sys.modules[__name__], client=bot, state_manager=STATE_MANAGER, logger=logger)
  ]
asyncio.run(init())


@bot.event
async def on_ready():
  # Initialize a hack for urllib that replaces `ICY 200 OK` as the status line with `HTTP/1.0 200 OK`
  urllib_hack.init_urllib_hack(TLS_VERIFY)

  logger.info("Syncing slash commands")
  await bot.tree.sync()
  logger.info(f"Logged on as {bot.user}")
  logger.info(f"Shard IDS: {bot.shard_ids}")
  logger.info(f"Cluster ID: {bot.cluster_id}")

### Custom Checks ###

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

def bot_not_in_maintenance():
  async def predicate(interaction: discord.Interaction):
    if STATE_MANAGER.get_maint() and not await bot.is_owner(interaction.user):
      await interaction.response.send_message(f"🚧 This bot is currently experiencing maintenance. Check back later.")
      return False
    return True
  return discord.app_commands.checks.check(predicate)

@bot.tree.command(
    name='play',
    description="Begin playback of a shoutcast/icecast stream"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
@bot_has_channel_permissions(permissions=discord.Permissions(send_messages=True))
@bot_not_in_maintenance()
async def play(interaction: discord.Interaction, url: str, private_stream: bool = False):
  if not is_valid_url(url):
    raise commands.BadArgument("🙇 I'm sorry, I don't know what that means!")
  if await is_cleaning_up(interaction):
    raise shout_errors.CleaningUp('Bot is still cleaning up from last session')

  response_message = f"Starting channel {url}" if not private_stream else "Starting channel ***OMINOUSLY***"
  await interaction.response.send_message(response_message, ephemeral=True)
  if await play_stream(interaction, url):
    STATE_MANAGER.set_state(interaction.guild_id, 'private_stream', private_stream)

@bot.tree.command(
    name='leave',
    description="Remove the bot from the current call"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
@bot_not_in_maintenance()
async def leave(interaction: discord.Interaction, force: bool = False):
  voice_client = interaction.guild.voice_client
  has_state = bool(STATE_MANAGER.get_state(interaction.guild.id, 'current_stream_url'))

  # Handle normal case - voice client exists
  if voice_client:
    await interaction.response.send_message("👋 Seeya Later, Gator!")
    await stop_playback(interaction.guild)
    return

  # Handle desync case - AUTOMATIC RECOVERY
  if has_state:
    if force:
      await interaction.response.send_message("🔧 Force clearing stale state...")
    else:
      await interaction.response.send_message("🔄 Detected state desync - automatically recovering...")

    # Automatically clear stale state
    STATE_MANAGER.clear_state(interaction.guild.id)
    logger.info(f"[{interaction.guild.id}]: Auto-recovered from state desync via /leave")

    if force:
      await interaction.edit_original_response(content="✅ Force cleared stale bot state. Ready for new streams!")
    else:
      await interaction.edit_original_response(content="✅ Auto-recovered from state issue. Ready for new streams!")
    return

  # Normal case - nothing playing
  raise shout_errors.NoVoiceClient("😨 I'm not even playing any music! You don't have to be so mean")

@bot.tree.command(
    name="song",
    description="Send an embed with the current song information to this channel"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
async def song(interaction: discord.Interaction):
  url = STATE_MANAGER.get_state(interaction.guild.id, 'current_stream_url')
  if url:
    await interaction.response.send_message("Fetching song title...")
    stationinfo = await get_station_info(url)
    if stationinfo['metadata']:
      await interaction.edit_original_response(content=f"Now Playing: 🎶 {stationinfo['metadata']['song']} 🎶")
    else:
      await interaction.edit_original_response(content=f"Could not retrieve song title. This feature may not be supported by the station")
  else:
    raise shout_errors.NoStreamSelected("🔎 None. There's no song playing. Turn the stream on maybe?")

@bot.tree.command(
    name="refresh",
    description="Refresh the stream. Bot will leave and come back. Song updates will start displaying in this channel"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
@bot_has_channel_permissions(permissions=discord.Permissions(send_messages=True))
@bot_not_in_maintenance()
async def refresh(interaction: discord.Interaction):
  if STATE_MANAGER.get_state(interaction.guild.id, 'current_stream_url'):
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
    'description': """
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
async def debug(interaction: discord.Interaction, page: int = 0, per_page: int = 10, id: str = ''):
  resp = []
  resp.append("==\tGlobal Info\t==")
  page_count = math.ceil(len(bot.guilds) / per_page)
  page = max(0, page-1)
  page = min(page, page_count-1)
  page_index = page * per_page

  if await bot.is_owner(interaction.user):
    if id:
      resp.append(id)
      resp.append("Guild:")
      guild = next((x for x in bot.guilds if str(x.id) == id), None)
      if guild:
        start_time = STATE_MANAGER.get_state(guild.id, 'start_time')

        resp.append(f"- {guild.name} ({guild.id}): user count - {guild.member_count}")
        resp.append(f"\tState: {STATE_MANAGER.get_state(guild.id)}")
        if start_time:
          resp.append(f"\tRun time: {datetime.datetime.now(datetime.UTC) - start_time}")
        resp.append(f"\tShard: {guild.shard_id}")

    else:
      resp.append("Guilds:")
      for guild in bot.guilds[page_index:page_index+per_page]:
        start_time = STATE_MANAGER.get_state(guild.id, 'start_time')

        resp.append(f"- {guild.name} ({guild.id}): user count - {guild.member_count}")
        resp.append(f"\tStatus: {STATE_MANAGER.get_state(guild.id, 'current_stream_url') or "Not Playing"}")
      resp.append(f"Total pages: {page_count}")
      resp.append(f"Current page: {math.floor(page_count/per_page) + 1}")
    resp.append("Bot:")
    resp.append(f"\tCluster ID: {bot.cluster_id}")
    resp.append(f"\tShards: {bot.shard_ids}")
  else:
    resp.append(f"\tGuild count: {len(bot.guilds)}")

  start_time = STATE_MANAGER.get_state(interaction.guild.id, 'start_time')

  resp.append("==\tServer Info\t==")
  resp.append(f"\tStream URL: {STATE_MANAGER.get_state(interaction.guild.id, 'current_stream_url') or "Not Playing"}")
  resp.append(f"\tCurrent song: {STATE_MANAGER.get_state(interaction.guild.id, 'current_song') or "Not Playing"}")
  if start_time:
    resp.append(f"\tRun time: {datetime.datetime.now(datetime.UTC) - start_time}")

  await interaction.response.send_message("\n".join(resp), ephemeral=True)

@bot.tree.command(
    name='maint',
    description="Toggle maintenance mode! (Bot maintainer only)"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
@bot_has_channel_permissions(permissions=discord.Permissions(send_messages=True))
async def maint(interaction: discord.Interaction, status: bool = True):
    if await bot.is_owner(interaction.user):
      if status == STATE_MANAGER.get_maint():
        await interaction.response.send_message("❌ Given maintenance status matches bot maintenance status. Nothing interesting happens.")
        return

      await interaction.response.send_message("🛠️ Toggling maintenance mode... please wait")
      await STATE_MANAGER.set_maint(status=status)
      active_guild_ids = STATE_MANAGER.all_active_guild_ids()
      for guild_id in active_guild_ids:
        text_channel = bot.get_channel(STATE_MANAGER.get_state(guild_id, 'text_channel_id'))
        is_active = STATE_MANAGER.get_state(guild_id, 'is_active') or False
        if status and is_active is True:
            embed_data = {
              'title': "Maintenance",
              'color': 0xfce053,
              'description': "The bot is entering maintenance mode. Commands and playback will be unavailable until maintenance is complete",
              'timestamp': str(datetime.datetime.now(datetime.UTC)),
            }
            await stop_playback(bot.get_guild(guild_id))
            STATE_MANAGER.set_state(guild_id, 'was_active', True)
            embed = discord.Embed.from_dict(embed_data)
            await text_channel.send(embed=embed)
        else:
          was_active = STATE_MANAGER.get_state(guild_id, 'was_active') or False
          if was_active is True and status == False:
            embed_data = {
              'title': "Maintenance",
              'color': 0xfce053,
              'description': "Maintenance has concluded.",
              'timestamp': str(datetime.datetime.now(datetime.UTC)),
          }
            embed = discord.Embed.from_dict(embed_data)
            await text_channel.send(embed=embed)

      if status:
        await interaction.edit_original_response(content="💾 saving state...")
        await STATE_MANAGER.save_state()
        asyncio.sleep(5)
        await interaction.edit_original_response(content="👷 Maintenance mode enabled")
      else:
        await interaction.edit_original_response(content="🧼 Purging State + DB...")
        STATE_MANAGER.clear_state(force=True)
        await STATE_MANAGER.clear_state_db()
        asyncio.sleep(5)
        await STATE_MANAGER.set_maint(status=status)
        await interaction.edit_original_response(content="👷 Maintenance mode disabled")

    else:
      logger.info("😂 Pleb tried to put me in maintenance mode")
      await interaction.response.send_message("Awww look at you, how cute")

### FAVORITES COMMANDS ###

@bot.tree.command(
    name='set-favorite',
    description="Add a radio station to favorites"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
async def set_favorite(interaction: discord.Interaction, url: str, name: str = None):
  # Check permissions
  perm_manager = get_permission_manager()
  if not perm_manager.can_set_favorites(interaction.guild.id, interaction.user):
    await interaction.response.send_message(
      "❌ You don't have permission to set favorites. Ask an admin to assign you the appropriate role.",
      ephemeral=True
    )
    return

  # Validate URL format first
  if not is_valid_url(url):
    await interaction.response.send_message("❌ Please provide a valid URL.", ephemeral=True)
    return

  await interaction.response.send_message("🔍 Validating stream and adding to favorites...")

  try:
    favorites_manager = get_favorites_manager()
    result = await favorites_manager.add_favorite(
      guild_id=interaction.guild.id,
      url=url,
      name=name,
      user_id=interaction.user.id
    )

    if result['success']:
      await interaction.edit_original_response(
        content=f"✅ Added **{result['station_name']}** as favorite #{result['favorite_number']}"
      )
    else:
      await interaction.edit_original_response(
        content=f"❌ Failed to add favorite: {result['error']}"
      )

  except Exception as e:
    logger.error(f"Error in set_favorite command: {e}")
    await interaction.edit_original_response(
      content="❌ An unexpected error occurred while adding the favorite."
    )

@bot.tree.command(
    name='play-favorite',
    description="Play a favorite radio station by number"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
async def play_favorite(interaction: discord.Interaction, number: int):
  try:
    favorites_manager = get_favorites_manager()
    favorite = favorites_manager.get_favorite_by_number(interaction.guild.id, number)

    if not favorite:
      await interaction.response.send_message(f"❌ Favorite #{number} not found.", ephemeral=True)
      return

    await interaction.response.send_message(
      f"🎵 Starting favorite #{number}: **{favorite['station_name']}**"
    )
    await play_stream(interaction, favorite['stream_url'])

  except Exception as e:
    logger.error(f"Error in play_favorite command: {e}")
    if interaction.response.is_done():
      await interaction.followup.send("❌ An error occurred while playing the favorite.", ephemeral=True)
    else:
      await interaction.response.send_message("❌ An error occurred while playing the favorite.", ephemeral=True)

@bot.tree.command(
    name='favorites',
    description="Show favorites with clickable buttons"
)
@discord.app_commands.checks.cooldown(rate=1, per=10)
async def favorites(interaction: discord.Interaction):
  try:
    favorites_manager = get_favorites_manager()
    favorites_list = favorites_manager.get_favorites(interaction.guild.id)

    if not favorites_list:
      await interaction.response.send_message(
        "📻 No favorites set for this server yet! Use `/set-favorite` to add some.",
        ephemeral=True
      )
      return

    # Create embed and view with buttons
    embed = create_favorites_embed(favorites_list, 0, interaction.guild.name)
    view = FavoritesView(favorites_list, 0)

    await interaction.response.send_message(embed=embed, view=view)

  except Exception as e:
    logger.error(f"Error in favorites command: {e}")
    await interaction.response.send_message("❌ An error occurred while loading favorites.", ephemeral=True)

@bot.tree.command(
    name='list-favorites',
    description="List all favorites (text only, mobile-friendly)"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
async def list_favorites(interaction: discord.Interaction):
  try:
    favorites_manager = get_favorites_manager()
    favorites_list = favorites_manager.get_favorites(interaction.guild.id)

    embed = create_favorites_list_embed(favorites_list, interaction.guild.name)
    await interaction.response.send_message(embed=embed)

  except Exception as e:
    logger.error(f"Error in list_favorites command: {e}")
    await interaction.response.send_message("❌ An error occurred while listing favorites.", ephemeral=True)

@bot.tree.command(
    name='remove-favorite',
    description="Remove a favorite radio station"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
async def remove_favorite(interaction: discord.Interaction, number: int):
  # Check permissions
  perm_manager = get_permission_manager()
  if not perm_manager.can_remove_favorites(interaction.guild.id, interaction.user):
    await interaction.response.send_message(
      "❌ You don't have permission to remove favorites. Ask an admin to assign you the appropriate role.",
      ephemeral=True
    )
    return

  try:
    favorites_manager = get_favorites_manager()

    # Check if favorite exists first
    favorite = favorites_manager.get_favorite_by_number(interaction.guild.id, number)
    if not favorite:
      await interaction.response.send_message(f"❌ Favorite #{number} not found.", ephemeral=True)
      return

    # Create confirmation view
    view = ConfirmationView("remove", f"favorite #{number}: {favorite['station_name']}")
    await interaction.response.send_message(
      f"⚠️ Are you sure you want to remove favorite #{number}: **{favorite['station_name']}**?\n"
      f"This will reorder all subsequent favorites.",
      view=view
    )

    # Wait for confirmation
    await view.wait()

    if view.confirmed:
      result = favorites_manager.remove_favorite(interaction.guild.id, number)
      if result['success']:
        await interaction.followup.send(
          f"✅ Removed **{result['station_name']}** from favorites. Subsequent favorites have been renumbered."
        )
      else:
        await interaction.followup.send(f"❌ Failed to remove favorite: {result['error']}")

  except Exception as e:
    logger.error(f"Error in remove_favorite command: {e}")
    if interaction.response.is_done():
      await interaction.followup.send("❌ An error occurred while removing the favorite.", ephemeral=True)
    else:
      await interaction.response.send_message("❌ An error occurred while removing the favorite.", ephemeral=True)

@bot.tree.command(
    name='setup-roles',
    description="Configure which Discord roles can manage favorites"
)
@discord.app_commands.checks.cooldown(rate=1, per=5)
async def setup_roles(interaction: discord.Interaction, role: discord.Role = None, permission_level: str = None):
  # Check permissions
  perm_manager = get_permission_manager()
  if not perm_manager.can_manage_roles(interaction.guild.id, interaction.user):
    await interaction.response.send_message(
      "❌ You don't have permission to manage role assignments. Ask an admin to assign you the appropriate role.",
      ephemeral=True
    )
    return

  try:
    # If no parameters provided, show current setup
    if not role and not permission_level:
      role_assignments = perm_manager.get_server_role_assignments(interaction.guild.id)
      available_roles = perm_manager.get_available_permission_roles()

      embed = create_role_setup_embed(role_assignments, available_roles, interaction.guild.name)
      await interaction.response.send_message(embed=embed)
      return

    # Both parameters required for assignment
    if not role or not permission_level:
      await interaction.response.send_message(
        "❌ Please provide both a role and permission level.\n"
        "Example: `/setup-roles @DJ dj`\n"
        "Available levels: user, dj, radio manager, admin",
        ephemeral=True
      )
      return

    # Validate permission level
    available_roles = perm_manager.get_available_permission_roles()
    valid_levels = [r['role_name'] for r in available_roles]

    if permission_level.lower() not in valid_levels:
      await interaction.response.send_message(
        f"❌ Invalid permission level. Available levels: {', '.join(valid_levels)}",
        ephemeral=True
      )
      return

    # Assign the role
    success = perm_manager.assign_role_permission(
      guild_id=interaction.guild.id,
      role_id=role.id,
      role_name=permission_level.lower()
    )

    if success:
      await interaction.response.send_message(
        f"✅ Assigned role {role.mention} to permission level **{permission_level}**"
      )
    else:
      await interaction.response.send_message(
        "❌ Failed to assign role permission. Please check the permission level is valid.",
        ephemeral=True
      )

  except Exception as e:
    logger.error(f"Error in setup_roles command: {e}")
    if interaction.response.is_done():
      await interaction.followup.send("❌ An error occurred while setting up roles.", ephemeral=True)
    else:
      await interaction.response.send_message("❌ An error occurred while setting up roles.", ephemeral=True)

### END FAVORITES COMMANDS ###

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
  elif isinstance(original_error, shout_errors.CleaningUp):
    # The client is still cleaning up after itself
    error_message = "🗑️ I'm still cleaning up after myself, give me a sec"
  elif isinstance(original_error, discord.app_commands.errors.CommandOnCooldown):
    # Commands are being sent too quickly
    error_message = "🥵 Slow down, I can only handle so much!"
  elif isinstance(original_error, discord.app_commands.errors.BotMissingPermissions):
    # We don't have permission to send messages here
    error_message = f"😶 It looks like I'm missing permissions for this channel:\n{error}"
  elif isinstance(original_error, discord.app_commands.CheckFailure):
    # Handle these messages in the permissions check function
    return
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


def url_slicer(url: str, max_display: int = 10) -> str:
  """
  Return a markdown link for use in embed fields. If the Path is longer than
  max_display value, return an ellipsized label that preserves the hostname and
  beginning of the path.

  The returned string is intended to be placed directly into an embed field
  value so it will be clickable in Discord.
  """
  if not url:
    return ""

  sliced_url = urllib.parse.urlparse(url)
  url_raw = str(url)
  path_raw = sliced_url.path.rstrip('/')
  hostname = sliced_url.hostname
  port = sliced_url.port
  # Slice the path if necessary
  if len(path_raw) <= max_display:
    path = path_raw
  else:
    path = "%s..." % (path_raw[:max_display])

  # If port is present and is not the default HTTP/HTTPS port, include it
  try:
    if port and int(port) not in (80, 443):
      display = f"{hostname}:{port}{path}"
    else:
      display = f"{hostname}{path}"
  except Exception:
    logger.warning(f"an unexpected error occurred while slicing port: {url}")
    display = "Error-slicing-URL"
    pass
  # Keep the full URL (with scheme) as the hyperlink target
  return f"[{display}]({url_raw})"

# Find information about the playing station & send that as an embed to the original text channel
async def send_song_info(guild_id: int):
  url = STATE_MANAGER.get_state(guild_id, 'current_stream_url')
  channel = bot.get_channel(STATE_MANAGER.get_state(guild_id, 'text_channel_id'))
  stationinfo = await get_station_info(url)

  if not stationinfo['metadata']:
    logger.warning("We didn't get metadata back from the station, can't send the station info")
    return

  # We need to quite now if we can't send messages
  guild = bot.get_guild(guild_id)
  if not channel.permissions_for(guild.me).send_messages:
    logger.warning("we don't have permission to send the song info!")
    return False

  embed_data = {
    'title': "Now Playing",
    'color': 0x0099ff,
    'description': f"🎶 {stationinfo['metadata']['song']} 🎶",
    # 'timestamp': str(datetime.datetime.now(datetime.UTC)),
  }

  embed = discord.Embed.from_dict(embed_data)
  sliced_url = url_slicer(url)
  bitrate = stationinfo['metadata'].get('bitrate', None)
  now_utc = datetime.datetime.now(datetime.timezone.utc)
  discord_time = f"<t:{int(now_utc.timestamp())}:R>"

  # Set information about the source in the "footer"
  if STATE_MANAGER.get_state(guild_id, 'private_stream'):
    # stream is private, do not show URL
    try:
      if bitrate not in (None, 0):
        embed.add_field(name="\u200b", value=f"Source: `Private` • Bitrate: {bitrate}kbps • {discord_time}", inline=True)
      else:
        embed.add_field(name="\u200b", value=f"Source: `Private` • {discord_time}", inline=True)
    except Exception:
      # Legacy Footer fallback
        logger.warning("Failed to add fields to embed, falling back to legacy footer")
        embed.set_footer(text=f"Source: Private")
  else:
      # stream is public, show URL
      try:
        if bitrate not in (None, 0):
          embed.add_field(name="\u200b", value=f"Source: {sliced_url} • Bitrate: {bitrate}kbps • {discord_time}", inline=True)
        else:
          embed.add_field(name="\u200b", value=f"Source: {sliced_url} • {discord_time}", inline=True)
      except Exception:
        # Legacy Footer fallback
          logger.warning("Failed to add fields to embed, falling back to legacy footer")
          embed.set_footer(text=f"Source: {url}")
  return await channel.send(embed=embed)



# Retrieve information about the shoutcast stream
async def get_station_info(url: str):
  if not url:
    logger.warning("Stream URL not set, can't send song information to channel")
    raise shout_errors.NoStreamSelected()

  stationinfo = streamscrobbler.get_server_info(url)
  if stationinfo['status'] <= 0:
    logger.warning("Stream not up, unable to update song title")
    raise shout_errors.StreamOffline()

  return stationinfo

# Handle stream disconnect with proper state cleanup
async def handle_stream_disconnect(guild: discord.Guild):
  """Handle stream disconnection and clean up state properly"""
  try:
    _active_heartbeats[guild.id].cancel()
    logger.info(f"[{guild.id}]: checking for stream disconnected")

    # Get current state before clearing
    channel = bot.get_channel(STATE_MANAGER.get_state(guild.id, 'text_channel_id'))

    # Notify users if possible
    if channel:
      try:
        # Check if we have permission to send messages
        if channel.permissions_for(guild.me).send_messages:
          await channel.send("🔌 Stream disconnected. Use `/play` to start a new stream!")
      except Exception as e:
        logger.warning(f"[{guild.id}]: Could not send disconnect notification: {e}")

    # Ensure voice client is properly disconnected
    voice_client = guild.voice_client
    if voice_client:
      try:
        if voice_client.is_connected():
          await voice_client.disconnect()
          logger.info(f"[{guild.id}]: Voice client disconnected")
      except Exception as e:
        logger.warning(f"[{guild.id}]: Error disconnecting voice client: {e}")

    # Ensure ffmpeg is not left running
    try:
      kill_ffmpeg_process(guild.id)
    except Exception as e:
      logger.debug(f"[{guild.id}]: Error attempting to purge ffmpeg in Handle_stream_disconnect: {e}")

    # Clear all state for this guild
    STATE_MANAGER.clear_state(guild.id)
    logger.info(f"[{guild.id}]: stream cleaned successfully!")

  except Exception as e:
    logger.error(f"[{guild.id}]: Error in handle_stream_disconnect: {e}")
    # Ensure state is cleared even if other operations fail
    STATE_MANAGER.clear_state(guild.id)

# Resync the stream by leaving and coming back
async def refresh_stream(interaction: discord.Interaction):
  url = STATE_MANAGER.get_state(interaction.guild.id, 'current_stream_url') # preserve current stream url
  await stop_playback(interaction.guild)
  await play_stream(interaction, url)

#  Start playing music from the stream
#  Check connection/status of stream
#  Check if stream link is .pls and parse it first
#  Get stream connection to server
#  Connect to voice channel
#  Start ffmpeg transcoding stream
#  Play stream
#  Start metadata monitor (will close stream if streaming server goes down)
async def play_stream(interaction, url):
  if not url:
    logger.warning("No stream currently set, can't play nothing")
    raise shout_errors.NoStreamSelected

  # Handle .pls playlist files
  sliced_url = urllib.parse.urlparse(url)
  path = sliced_url.path
  pls = path.find('.pls')
  if pls != -1:
    logger.debug(f"Detected .pls file, attempting to parse: {url}")
    await interaction.edit_original_response(content="❓ Looks Like this is a `.pls`, Let's see if I can figure it out...")
    stream_url = await parse_pls(url)
    if not stream_url:
      # catch all
      logger.error("Failed to parse .pls or no valid stream URL found")
      raise shout_errors.StreamOffline()
    url = stream_url

  # Connect to voice channel author is currently in
  voice_state = getattr(interaction.user, 'voice', None)   # voice channel check, explicitly set to None if not found for some reason
  voice_channel = voice_state.channel if voice_state and getattr(voice_state, 'channel', None) else None
  if voice_channel is None:
    raise shout_errors.AuthorNotInVoice
  # Find if voice client is already playing music
  voice_client = interaction.guild.voice_client
  # If a voice client exists but is not connected, purge it and start over
  if voice_client and not voice_client.is_connected():
    try:
      logger.info("Attempting to purge stale client")
      await interaction.edit_original_response(content="this is taking a while... don't worry we're still trying to get your stream!")
      STATE_MANAGER.set_state(interaction.guild.id, 'cleaning_up', True)
      await voice_client.disconnect(force=True)
      logger.info("Disconnected stale voice client before starting new stream")
    except Exception as e: # Last ditch effort
      logger.warning(f"Error disconnecting stale voice client: {e}")
    voice_client = None

  # If a voice client is already playing, raise error
  if voice_client and voice_client.is_playing():
    raise shout_errors.AlreadyPlaying

  logger.info(f"Starting channel {url}")

  stationinfo = streamscrobbler.get_server_info(url)
  ## metadata is the bitrate and current song
  metadata = stationinfo['metadata']
  ## status is the integer to tell if the server is up or down, 0 is down, 1 is up, 2 is up with metadata
  status = stationinfo['status']
  logger.info(f"metadata: {metadata}, status: {status}")

  # If the stream status isn't >0, it's offline. Exit out early
  if status <= 0:
    logger.error("Stream is not online")
    raise shout_errors.StreamOffline()

  # Try to get an http stream connection to the ... stream
  try:
    urllib.request.urlopen(url, timeout=10)
  except Exception as error: # if there is an error, let the user know.
    logger.error(f"Failed to connect to stream: {error}")
    await interaction.edit_original_response(content="Error fetching stream. Maybe the stream is down?")
    return False

  # Try to connect to voice chat, and only consider connected if both conditions met
  if not voice_client or not voice_client.is_connected():
    try:
      voice_client = await voice_channel.connect(timeout=7)
      logger.info("Connected to voice channel for playback")
    except Exception as e:
      logger.error(f"Failed to connect to voice channel: {e}")
      max_users = voice_channel.user_limit
      user_count = len(voice_channel.members)
      if user_count >= max_users:
        await interaction.edit_original_response(content="There's no room for me in there 🥺")
      else:
        await interaction.edit_original_response(content="Failed to connect to voice channel. Please try again.")
      return False

  # TRY to Pipe music stream to FFMpeg:

  # We love adhering to SHOUTcast recommended buffer sizes arounder here! yay!
  #                  MARKER BYTES REQUIRED FOR PROPER SYNC!
  # 4080 bytes per tick * 8 chunks = 32640 + 8 marker bytes = 32648 bits buffer (8 chunks)
  # 4080 bytes per tick * 4 Chunks = 16320 + 4 marker bytes = 16324 bits per analysis (4 chunks)
  try:
    music_stream = discord.FFmpegOpusAudio(source=url, options="-analyzeduration 16324 -rtbufsize 32648 -filter:a loudnorm=I=-30:LRA=7:TP=-3 -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 120 -tls_verify 0 -protocol_whitelist http,https,tls,pipe")
    await asyncio.sleep(1)  # Give FFmpeg a moment to start
  except Exception as e:
    logger.error(f"Failed to start FFmpeg stream: {e}")
    await interaction.edit_original_response(content="Failed to start stream processing. Please try again.")
    return False

  # Try to detect and record the ffmpeg subprocess PID so we can clean it up later
  try:
    proc = None ## default to None, probably not needed.
    for attr in ("process", "proc", "_process", "_proc", "_popen"): ## look in all these for FFmpeg
      proc = getattr(music_stream, attr, None) ## try to get it from music_stream, default to None
      if proc:
        break ## we found it, please stop

    pid = None ## default to None, probably not needed.
    if proc is not None:
      pid = getattr(proc, 'pid', None) ## great, lets try to get the pid! default is none!
      if pid is None and hasattr(proc, 'pid'):
        pid = proc.pid ## hmm... we still don't have it, try this way instead
    if pid:
      STATE_MANAGER.set_state(interaction.guild.id, 'ffmpeg_process_pid', pid) ## we got it, lets keep it safe
      logger.debug(f"[{interaction.guild.id}]: Recorded ffmpeg PID: {pid}")
  except Exception as e:
    logger.warning(f"[{interaction.guild.id}]: Could not record ffmpeg process PID: {e}")  ## darn, we tried!

  # Create proper cleanup callback that handles state
  def stream_finished_callback(error):
    if error:
      logger.error(f"Stream finished with error: {error}")
    else:
      logger.info("Stream finished normally")

    # Schedule proper cleanup with state management
    asyncio.run_coroutine_threadsafe(handle_stream_disconnect(interaction.guild), bot.loop)

  # if the voice client exists, lets try to play through it.
  try:
    voice_client.play(music_stream, after=stream_finished_callback)
  except discord.ClientException as e:
    logger.error(f"Voice client play failed: {e}")
    await interaction.edit_original_response(content="Failed to start playback. Voice client not connected.")
    return False

  # Everything was successful, lets keep all the data
  STATE_MANAGER.set_state(interaction.guild.id, 'current_stream_url', url)
  STATE_MANAGER.set_state(interaction.guild.id, 'text_channel_id', interaction.channel.id)
  STATE_MANAGER.set_state(interaction.guild.id, 'start_time', datetime.datetime.now(datetime.UTC))
  STATE_MANAGER.set_state(interaction.guild.id, 'is_active', True)

  # And let the user know what song is playing
  await send_song_info(interaction.guild.id)
  STATE_MANAGER.set_state(interaction.guild.id, 'cleaning_up', False)
  create_and_start_heartbeat(interaction.guild.id)

  return True


# Disconnect the bot, close the stream, BAN FFmpeg, and reset state
async def stop_playback(guild: discord.Guild):
  # Let the bot know we're cleaning up and it needs to wait before any more commands are processed
  STATE_MANAGER.set_state(guild.id, 'cleaning_up', True)
  # handle case where client says connected when it shouldn't be
  voice_client = guild.voice_client
  if voice_client:
    # fist we stop playback if it says its playing
    if voice_client.is_playing():
      while voice_client.is_playing():
        voice_client.stop()
        logger.debug("Attempting to stop client")
        await asyncio.sleep(1)
      logger.info("voice client stopped")
    # then we handle disconnect from voice
    if voice_client.is_connected():
      while voice_client.is_connected():
        await voice_client.disconnect()
        logger.debug("Attempting to disconnect client")
        await asyncio.sleep(1)
      logger.info("voice client disconnected")
    # if we still have voice_client after all that, tell it to go away so we can just forget it ever happened
    if hasattr(guild, 'voice_client'):
      try:
        guild.voice_client = None
        logger.error("state desynced, revovering state")
      except Exception:
        pass

  # Ensure any lingering ffmpeg process is terminated before clearing state
  logger.debug(f"Starting guild state Clean: {STATE_MANAGER.get_state(guild.id)}")
  try:
    logger.debug(f"[{guild.id}]: Purging ffmpeg first")
    kill_ffmpeg_process(guild.id)
  except Exception as e:
    logger.debug(f"[{guild.id}]: Error attempting to purge ffmpeg during Stop_playback: {e}")

  STATE_MANAGER.clear_state(guild.id)
  logger.debug(f"Guild state cleared: {STATE_MANAGER.get_state(guild.id)}")
  STATE_MANAGER.set_state(guild.id, 'cleaning_up', False)

  _active_heartbeats[guild.id].cancel()


def create_and_start_heartbeat(guild_id: int):
  @tasks.loop(seconds = 15)
  async def heartbeat(guild_id: int):
    try:
      logger.debug(f"Running heartbeat for: {guild_id}")
      url = STATE_MANAGER.get_state(guild_id, 'current_stream_url')

      if url is None:
        return

      # Loop through monitors and execute. Let them handle their own shit
      stationinfo = streamscrobbler.get_server_info(url)
      for monitor in MONITORS:
        await monitor.execute(guild_id=guild_id, state=STATE_MANAGER.get_state(guild_id), stationinfo=stationinfo)
    except Exception as e:
      logger.error(f"An unhandled error occurred in the heartbeat: {e}")

  _active_heartbeats[guild_id] = heartbeat.start(guild_id)


# TODO: maybe add these checks to health monitor
def kill_ffmpeg_process(guild_id: int, timeout: float = 3.0):
  """Attempt to terminate a recorded ffmpeg process for the guild.
  This checks `ffmpeg_process_pid` in the guild state and tries to terminate it.
  Uses psutil when available for safer termination; otherwise falls back to os.kill.
  """
  pid = None ## specify default as none, probably not necessary
  try:
    pid = STATE_MANAGER.get_state(guild_id, 'ffmpeg_process_pid') ## lets try to get the pid from state
  except Exception:
    pid = None ## we couldn't get it, set it to none

  if not pid:
    logger.debug(f"[{guild_id}]: No ffmpeg PID recorded, or ffmpeg already purged")
    return False

  # Use psutil to terminate FFMPEG process
  try:
    ffmpeg = psutil.Process(int(pid))
    if ffmpeg.is_running():
      ffmpeg.terminate() ## let's try to be nice first
      logger.debug(f"[{guild_id}]: attempting to terminate ffmpeg process {pid} with psutil")
      try:
        ffmpeg.wait(timeout=timeout) ## wait for it to leave
        logger.info(f"[{guild_id}]: ffmpeg process {pid} terminated gracefully")
      except psutil.TimeoutExpired:
        ffmpeg.kill() ## we tried to be nice, let's kill it.
        logger.warning(f"[{guild_id}]: ffmpeg process {pid} terminated ungracefully due to timeout")
    return True
  except psutil.NoSuchProcess:
    logger.debug(f"ffmpeg process {pid} exited early, ready to go!")
    return False


# Utility method to check if the bot is cleaning up
async def is_cleaning_up(interaction: discord.Interaction):
  return STATE_MANAGER.get_state(interaction.guild.id, 'cleaning_up')

bot.run(BOT_TOKEN, log_handler=None)
