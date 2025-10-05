from enum import Enum
from abc import ABC, abstractmethod
from logging import Logger
from discord import Client
from services.state_manager import StateManager


class ErrorStates(Enum):
   CLIENT_NOT_IN_CHAT = 'client_not_in_chat'
   NO_ACTIVE_STREAM = 'no_active_stream'
   NOT_PLAYING = 'not_playing'
   STREAM_OFFLINE = 'stream_offline'
   STALE_STATE = 'state_state'
   INACTIVE_GUILD = 'inactive_guild'
   INACTIVE_CHANNEL = 'inactive_channel'

class Monitor(ABC):
  def __init__(self, bot, client: Client, state_manager: StateManager=None, logger: Logger=None):
    self.bot = bot
    self.client = client
    self.state_manager = state_manager
    self.logger = logger

  @abstractmethod
  async def execute(self, guild_id: int, state: dict[int, dict[str, str]]):
    pass
