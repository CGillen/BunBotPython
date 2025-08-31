from logging import Logger
from discord import Client
import streamscrobbler

from services.state_manager import StateManager
from services.interfaces import ErrorStates


class HealthMonitor:
  def __init__(self, bot: Client, state_manager: StateManager=None, logger: Logger=None):
    self.bot = bot
    self.state_manager = state_manager
    self.logger = logger

  def execute(self, guild_id: int, state: dict[int, dict[str, str]]):
    issues = []

    if not state:
      return issues

    issues.append(self.state_desync(guild_id, state))
    issues.append(self.station_health(guild_id, state))

    return issues

  def state_desync(self, guild_id: int, state: dict):
    try:
      guild = self.bot.get_guild(guild_id)

      if not guild:
        return None

      voice_client = guild.voice_client

      if not voice_client and state['current_stream_url']:
        self.logger.error(f"Client attempting to stream {state['current_stream_url']} but is not in voice chat for guild: {guild_id}")
        return ErrorStates.CLIENT_NOT_IN_CHAT

      if voice_client and not state['current_stream_url']:
        self.logger.error(f"Voice client in voice chat for guild: {guild_id} but no stream chosen")
        return ErrorStates.NO_ACTIVE_STREAM

      if voice_client and state['current_stream_url']:
        if not voice_client.is_connected():
          self.logger.error(f"Voice client is disconnected but state says stream is active")
          return ErrorStates.CLIENT_NOT_IN_CHAT
        if not voice_client.is_playing():
          self.logger.error(f"Voice client is connected but not playing")
          return ErrorStates.NOT_PLAYING

    except Exception as e:
        self.logger.debug(f"Could not check state consistency for guild {guild_id}: {e}")

  def station_health(self, guild_id: int, state: dict):
    try:
      if not state['stream_offline_count']:
        state['stream_offline_count'] = 0

      stationinfo = streamscrobbler.get_server_info(state['current_stream_url'])

      if stationinfo is None:
        self.logger.warning(f"[{guild_id}]: Streamscrobbler returned info as None")
      elif not stationinfo['status'] and state['stream_offline_count'] >= 3:
        state['stream_offline_count']
        return ErrorStates.STREAM_OFFLINE
      elif not stationinfo['status']:
        state['stream_offline_count'] += 1
      elif stationinfo['status']:
        state['stream_offline_count'] = 0

      if not stationinfo['metadata']:
        self.logger.warning(f"[{guild_id}]: Streamscrobbler returned metadata as None from server")

      pass
    except Exception as e:
      pass
