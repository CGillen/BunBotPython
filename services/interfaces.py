from dataclasses import dataclass
from enum import Enum

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

@dataclass
class State:
  pass