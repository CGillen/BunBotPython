import math
import datetime
import os
from dotenv import load_dotenv

from services.interfaces import ErrorStates, Monitor

# Seconds since last active user before the bot leaves
load_dotenv()
EMPTY_CHANNEL_TIMEOUT = int(os.environ.get('EMPTY_CHANNEL_TIMEOUT', 45*60))

class HealthMonitor(Monitor):

  async def execute(self, guild_id: int, state: dict[int, dict[str, str]], stationinfo=None):
    issues = []

    if not state:
      return True

    issues.append(self.state_desync(guild_id))
    issues.append(self.station_health(guild_id, stationinfo))
    issues.append(self.bot_health(guild_id))
    issues = filter(None, issues)

    result = await self.handle_health_errors(guild_id, issues)

    # Update the last time we saw a user in the chat
    guild = self.client.get_guild(guild_id)
    # TODO: Check guild.voice_client.channel.members for any bots: https://discordpy.readthedocs.io/en/latest/api.html?highlight=voicechannel#discord.Member.bot
    if guild.voice_client is not None and len(guild.voice_client.channel.members) > 1:
      self.state_manager.set_state(guild.id, 'last_active_user_time', datetime.datetime.now(datetime.UTC))

    return result

  async def handle_health_errors(self, guild_id:int, health_errors: list):
    guild = self.client.get_guild(guild_id)
    channel = self.client.get_channel(self.state_manager.get_state(guild_id, 'text_channel_id'))

    health_error_counts = self.state_manager.get_state(guild_id, 'health_error_count')
    if not health_error_counts:
      health_error_counts = HealthMonitor.default_state()
    prev_health_error_counts = dict(health_error_counts or {})

    for health_error in health_errors:
      self.logger.warning(f"[{guild_id}]: Received health error: {health_error}")
      # Track how many times this error occurred and only handle it if it's the third time
      health_error_counts[health_error] += 1
      self.logger.warning(f"[{guild_id}]: Has failed check: '{health_error}' {health_error_counts[health_error]} times")
      if health_error_counts[health_error] < 3:
        continue

      match health_error:
        case ErrorStates.CLIENT_NOT_IN_CHAT:
          if channel.permissions_for(guild.me).send_messages:
            await channel.send("😰 The voice client left unexpectedly, try using /play to resume the stream!")
          else:
            self.logger.warning(f"[{guild_id}]: Do not have permission to send messages in {channel}")
          await self.bot.stop_playback(guild)
          return False
        case ErrorStates.NO_ACTIVE_STREAM:
          if channel.permissions_for(guild.me).send_messages:
            await channel.send("😰 No more active stream, disconnecting")
          else:
            self.logger.warning(f"[{guild_id}]: Do not have permission to send messages in {channel}")
          await self.bot.stop_playback(guild)
          return False
        case ErrorStates.STREAM_OFFLINE:
          self.logger.error(f"[{guild_id}]: The stream went offline: {health_error}")
          if channel.permissions_for(guild.me).send_messages:
            await channel.send("😰 The stream went offline, I gotta go!")
          else:
            self.logger.warning(f"[{guild_id}]: Do not have permission to send messages in {channel}")
          await self.bot.stop_playback(guild)
          return False
        case ErrorStates.NOT_PLAYING:
          if channel.permissions_for(guild.me).send_messages:
            await channel.send("😰 The stream stopped playing unexpectedly")
          else:
            self.logger.warning(f"[{guild_id}]: Do not have permission to send messages in {channel}")
          await self.bot.stop_playback(guild)
          return False
        case ErrorStates.INACTIVE_GUILD:
          self.logger.warning(f"[{guild_id}]: Desync detected, purging bad state!")
          url = None
          self.state_manager.clear_state(guild_id)
          return False
        case ErrorStates.STALE_STATE:
          self.logger.warning(f"[{guild_id}]: we still have a guild, attempting to finish normally")
          await self.bot.stop_playback(guild)
          return False
        case ErrorStates.INACTIVE_CHANNEL:
          inactivity_delta = (datetime.datetime.now(datetime.UTC) - self.state_manager.get_state(guild_id, 'last_active_user_time')).total_seconds() / 60
          self.logger.info(f"[{guild_id}]: Voice channel inactive for {inactivity_delta} minutes. Kicking bot")
          if channel.permissions_for(guild.me).send_messages:
            await channel.send(f"Where'd everybody go? Putting bot to bed after `{math.ceil(inactivity_delta)}` minutes of inactivity in voice channel")
          await self.bot.stop_playback(guild)
          return False

    # Reset error counts if they didn't change (error didn't fire this round)
    for key, value in prev_health_error_counts.items():
      if health_error_counts[key] == value:
        health_error_counts[key] = 0
    if self.state_manager.get_state(guild_id):
      self.state_manager.set_state(guild_id, 'health_error_count', health_error_counts)
    return True



  def state_desync(self, guild_id: int):
    try:
      guild = self.client.get_guild(guild_id)
      url = self.state_manager.get_state(guild_id, 'current_stream_url')

      if not url:
        return ErrorStates.STALE_STATE
      if not guild:
        return ErrorStates.INACTIVE_GUILD

      voice_client = guild.voice_client

      if not voice_client and url:
        self.logger.error(f"Client attempting to stream {url} but is not in voice chat for guild: {guild_id}")
        return ErrorStates.CLIENT_NOT_IN_CHAT

      if voice_client and not url:
        self.logger.error(f"Voice client in voice chat for guild: {guild_id} but no stream chosen")
        return ErrorStates.NO_ACTIVE_STREAM

      if voice_client and url:
        if not voice_client.is_connected():
          self.logger.error(f"Voice client is disconnected but state says stream is active")
          return ErrorStates.CLIENT_NOT_IN_CHAT
        if not voice_client.is_playing():
          self.logger.error(f"Voice client is connected but not playing")
          return ErrorStates.NOT_PLAYING

    except Exception as e:
      self.logger.debug(f"Could not check state consistency for guild {guild_id}: {repr(e)}")

  def station_health(self, guild_id: int, stationinfo=None):
    url = self.state_manager.get_state(guild_id, 'current_stream_url')
    if not url:
      return None

    try:
      if stationinfo is None:
        self.logger.warning(f"[{guild_id}|Health Check]: Streamscrobbler returned info as None")
      elif not stationinfo['status']:
        self.logger.error(f"[{guild_id}|Health Check]: Streamscrobbler found stream to be offline")
        return ErrorStates.STREAM_OFFLINE

      if not stationinfo['metadata']:
        self.logger.warning(f"[{guild_id}|Health Check]: Streamscrobbler returned metadata as None from server")

    except Exception as e:
      self.logger.debug(f"Could not check health of stream for guild {guild_id}: {repr(e)}")

  def bot_health(self, guild_id: int):
    last_active_user_time = self.state_manager.get_state(guild_id, 'last_active_user_time')
    if not last_active_user_time:
      return None

    last_active_delta = (datetime.datetime.now(datetime.UTC) - last_active_user_time).total_seconds()

    if EMPTY_CHANNEL_TIMEOUT > 0 and last_active_delta >= EMPTY_CHANNEL_TIMEOUT:
      return ErrorStates.INACTIVE_CHANNEL

  @staticmethod
  def default_state():
    state = {}
    for error in ErrorStates:
      state[error] = 0
    return state