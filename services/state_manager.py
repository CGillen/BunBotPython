

from services.interfaces import State

class StateManager:
  guilds: dict[int, State]
  bot: dict[str, str]
  pass
