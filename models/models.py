from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from services.interfaces import ErrorStates

class Base(DeclarativeBase):
  __abstract__ = True

  def to_dict(self):
    """
    Converts the ORM object to a dictionary, including only mapped columns.
    """
    return {
      column.name: getattr(self, column.name)
      for column in self.__table__.columns
    }

class GuildState(Base):
  ### Available state variables ###
  # current_stream_url = URL to playing (or about to be played) shoutcast stream
  # private_stream = If the stream source should be presented
  # text_channel = Text channel original play command came from
  # start_time = Time the current stream started playing
  # last_active_user_time = Time the last active user was spotted in the voice channel
  # cleaning_up = Boolean for if the bot is currently stopping/cleaning up True|None
  # health_error_count = Int number of times a health error occurred in a row
  # ffmpeg_process_pid = PID for the FFMPEG process associated with the guild
  __tablename__ = "guild_state"

  guild_id: Mapped[int] = mapped_column(primary_key=True)
  current_stream_url: Mapped[str] = mapped_column(String)
  private_stream: Mapped[bool] = mapped_column(Boolean)
  text_channel_id: Mapped[int] = mapped_column(Integer)
  start_time: Mapped[datetime] = mapped_column(DateTime)
  last_active_user_time: Mapped[datetime] = mapped_column(DateTime)
  cleaning_up: Mapped[bool] = mapped_column(Boolean)
  ffmpeg_process_pid: Mapped[int] = mapped_column(Integer)
  health_error_count: list[{ErrorStates, int}] = []

class BotState(Base):
  __tablename__ = "bot_state"

  id: Mapped[int] = mapped_column(primary_key=True)
  maint: Mapped[bool] = mapped_column(Boolean)
