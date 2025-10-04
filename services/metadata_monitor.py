import bot

from services.interfaces import Monitor

class MetadataMonitor(Monitor):
  async def execute(self, guild_id: int, state: dict[int, dict[str, str]], stationinfo=None):
    self.logger.debug(f"[{guild_id}]: {bot.get_state(guild_id)}")

    guild = self.bot.get_guild(guild_id)
    channel = bot.get_state(guild_id, 'text_channel')
    song = bot.get_state(guild_id, 'current_song')
    url = bot.get_state(guild_id, 'current_stream_url')

    if url is None:
      return

    # Metadata updates
    try:
      if stationinfo is None:
        self.logger.warning(f"[{guild_id}]: Streamscrobbler returned info as None")
      elif stationinfo['metadata'] is None or stationinfo['metadata'] is False:
        self.logger.warning(f"[{guild_id}]: Streamscrobbler returned metadata as None from server")
      else:
        # Check if the song has changed & announce the new one
        if isinstance(stationinfo['metadata']['song'], str):
          self.logger.info(f"[{guild_id}]: {stationinfo}")
          if song is None:
            bot.set_state(guild_id, 'current_song', stationinfo['metadata']['song'])
            self.logger.info(f"[{guild_id}]: Current station info: {stationinfo}")
          elif song != stationinfo['metadata']['song']:
            if await bot.send_song_info(guild_id):
              bot.set_state(guild_id, 'current_song', stationinfo['metadata']['song'])
            self.logger.info(f"[{guild_id}]: Current station info: {stationinfo}")
        else:
          self.logger.warning("Received non-string value from server metadata")
    except Exception as error: # Something went wrong, let's just close it all out
      self.logger.error(f"[{guild_id}]: Something went wrong while checking stream metadata: {error}")
      channel =  bot.get_state(guild_id, 'text_channel')
      guild = self.bot.get_guild(guild_id)
      if channel.permissions_for(guild.me).send_messages:
        await channel.send("😰 Something happened to the stream! I uhhh... gotta go!")
      else:
        self.logger.warning(f"[{guild_id}]: Do not have permission to send messages in {channel}")
      await bot.stop_playback(guild)
    pass