from services.interfaces import Monitor

class MetadataMonitor(Monitor):
  async def execute(self, guild_id: int, state: dict[int, dict[str, str]], stationinfo=None):
    self.logger.debug(f"[{guild_id}|Metadata Monitor]: {self.state_manager.get_state(guild_id)}")

    song = self.state_manager.get_state(guild_id, 'current_song')
    url = self.state_manager.get_state(guild_id, 'current_stream_url')

    if url is None:
      return

    # Metadata updates
    try:
      if stationinfo is None:
        self.logger.warning(f"[{guild_id}|Metadata Monitor]: Streamscrobbler returned info as None")
      elif stationinfo['metadata'] is None or stationinfo['metadata'] is False:
        self.logger.warning(f"[{guild_id}|Metadata Monitor]: Streamscrobbler returned metadata as None from server")
      else:
        # Check if the song has changed & announce the new one
        if isinstance(stationinfo['metadata']['song'], str):
          self.logger.debug(f"[{guild_id}|Metadata Monitor]: {stationinfo}")
          if song is None:
            self.state_manager.set_state(guild_id, 'current_song', stationinfo['metadata']['song'])
            self.logger.info(f"[{guild_id}|Metadata Monitor]: Current station info: {stationinfo}")
          elif song != stationinfo['metadata']['song']:
            if await self.bot.send_song_info(guild_id):
              self.state_manager.set_state(guild_id, 'current_song', stationinfo['metadata']['song'])
            self.logger.info(f"[{guild_id}|Metadata Monitor]: Current station info: {stationinfo}")
        else:
          self.logger.warning("Received non-string value from server metadata")
    except Exception as error: # Something went wrong, let's just close it all out
      self.logger.error(f"[{guild_id}|Metadata Monitor]: Something went wrong while checking stream metadata: {error}")
