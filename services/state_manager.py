from discord import Client

class StateManager:
  ### Available state variables ###
  # current_stream_url = URL to playing (or about to be played) shoutcast stream
  # metadata_listener = Asyncio task for listening to metadata (monitor_metadata())
  # text_channel = Text channel original play command came from
  # start_time = Time the current stream started playing
  # last_active_user_time = Time the last active user was spotted in the voice channel
  # cleaning_up = Boolean for if the bot is currently stopping/cleaning up True|None
  # health_error_count = Int number of times a health error occurred in a row
  # ffmpeg_process_pid = PID for the FFMPEG process associated with the guild

  state: dict[int, object] = {}
  bot: Client

  def get_state(self, guild_id: int=None, var: str=None):
    # Make sure guild is setup for state
    if guild_id not in self.state:
      self.state[guild_id] = {}
    # Return whole state object if no var name was passed
    if var is None:
      return self.state[guild_id]
    # Make sure var is available in guild state
    if var not in self.state[guild_id]:
      return None

    return self.state[guild_id][var]

  # Setter for state of a guild
  def set_state(self, guild_id: int=None, var: str=None, val: object=None):
    # Make sure guild is setup for state
    if guild_id not in self.state:
      self.state[guild_id] = {}
    # Make sure var is available in guild state
    if var not in self.state[guild_id]:
      self.state[guild_id][var] = None

    self.state[guild_id][var] = val
    return val

  # Clear out state so we can start all over
  def clear_state(self, guild_id: int=None):
    # Just throw it all away, idk, maybe we'll need to close and disconnect stuff later
    self.state[guild_id] = {}

  # Get all ids of guilds that have a valid voice clients or server state
  def all_active_guild_ids(self):
    active_ids = []
    for guild_id, _ in self.state:
      # Only consider active if state exists and voice client is connected
      guild = self.bot.get_guild(guild_id)

      # Sometimes we need to exclude some state variables when considering if the guild is active
      vars_to_exclude = ['cleaning_up']
      temp_state = {key: value for key, value in self.get_state(guild_id).items() if key not in vars_to_exclude}

      state_active = bool(temp_state)
      vc_active = guild and guild.voice_client and guild.voice_client.is_connected()
      if state_active or vc_active:
        active_ids.append(guild_id)
    return active_ids

  # TODO: Create a way to dump and load state
  def save_state(self):
    pass
  def load_state(self):
    pass
