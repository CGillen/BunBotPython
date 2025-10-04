import bot
import datetime
from logging import Logger
import os
from dotenv import load_dotenv
from discord import Client
from streamscrobbler import streamscrobbler

from services.state_manager import StateManager
from services.interfaces import ErrorStates, Monitor

# Seconds since last active user before the bot leaves
load_dotenv()
EMPTY_CHANNEL_TIMEOUT = int(os.environ.get('EMPTY_CHANNEL_TIMEOUT', 45*60))

class HealthMonitor(Monitor):

  async def execute(self, guild_id: int, state: dict[int, dict[str, str]], stationinfo=None):
    issues = []

    if not state:
      return issues

    issues.append(self.state_desync(guild_id, state))
    issues.append(self.station_health(guild_id, state, stationinfo))
    issues.append(self.bot_health(guild_id, state))

    return filter(None, issues)

  def state_desync(self, guild_id: int, state: dict):
    try:
      guild = self.bot.get_guild(guild_id)
      url = bot.get_state(guild_id, 'current_stream_url')

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

  def station_health(self, guild_id: int, state: dict, stationinfo=None):
    url = bot.get_state(guild_id, 'current_stream_url')
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

  def bot_health(self, guild_id: int, state: dict):
    last_active_user_time = bot.get_state(guild_id, 'last_active_user_time')
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