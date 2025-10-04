from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
from logging import Logger

from discord import Client

from services.state_manager import StateManager

class HealthStates(Enum):
    """Health status levels for components and systems"""
    HEALTHY = 'healthy'
    WARNING = 'warning'
    CRITICAL = 'critical'
    OFFLINE = 'offline'
    UNKNOWN = 'unknown'

class ErrorStates(Enum):
   CLIENT_NOT_IN_CHAT = 'client_not_in_chat'
   NO_ACTIVE_STREAM = 'no_active_stream'
   NOT_PLAYING = 'not_playing'
   STREAM_OFFLINE = 'stream_offline'
   STALE_STATE = 'state_state'
   INACTIVE_GUILD = 'inactive_guild'
   INACTIVE_CHANNEL = 'inactive_channel'

class Monitor(ABC):
  def __init__(self, bot: Client, state_manager: StateManager=None, logger: Logger=None, stationinfo=None):
    self.bot = bot
    self.state_manager = state_manager
    self.logger = logger

  @abstractmethod
  async def execute(self, guild_id: int, state: dict[int, dict[str, str]]):
    pass

    # Getter for state of a guild
  def get_state(self, guild_id, server_state={}, var=None):
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
  def set_state(self, guild_id, server_state, var, val):
    # Make sure guild is setup for state
    if guild_id not in server_state:
      server_state[guild_id] = {}
    # Make sure var is available in guild state
    if var not in server_state[guild_id]:
      server_state[guild_id][var] = None

    server_state[guild_id][var] = val
    return val

@dataclass
class State:
  pass