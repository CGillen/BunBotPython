import os
from logging import Logger
from sqlalchemy import func, null, select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from stream_validator import get_stream_validator
from input_validator import get_input_validator

from models.models import PersonalFavorite

class PersonalFavoritesManager:

  MAX_FAVORITES: int = int(os.environ.get('MAXIMUM_FAVORITES_COUNT', 10))

  def __init__(self, logger: Logger):
    self.db_engine = create_async_engine("sqlite+aiosqlite:///.db", echo=True)
    self.ASYNC_SESSION_LOCAL = async_sessionmaker(self.db_engine, expire_on_commit=False)
    self.stream_validator = get_stream_validator()
    self.input_validator = get_input_validator()
    self.logger = logger


  # Attempt to add a favorite station for the user.
  # Fails if:
  #   - stream_url is not an actual url
  #   - station_name has disallowed characters
  #   - stream_url does not point to a valide radio station
  #   - user already has this stream_url in their favorites
  #   - user has too many favorites already
  async def create_user_favorite(self, user_id: int, stream_url: str, station_name: str = null) -> bool:
    # not a url
    if not self.input_validator.validate_url(stream_url)['valid']:
      self.logger.warning('Failed to validate url %s as url', stream_url)
      return False
    # station name has invalid characters
    if not self.input_validator.validate_station_name(station_name)['valid']:
      self.logger.warning('Failed to validate station_name %s as an allowed name', station_name)
      return False
    # not a real station
    if not self.stream_validator.validate_stream(stream_url)['valid']:
      self.logger.warning('Failed to validate stream %s as a radio station', stream_url)
      return False

    async with self.ASYNC_SESSION_LOCAL() as session:
      stmt = select(func.count()).where(PersonalFavorite.user_id == user_id).where(PersonalFavorite.stream_url == stream_url)
      matched_favorites = await session.execute(stmt)
      stmt = select(func.count()).where(PersonalFavorite.user_id == user_id)
      fav_count = await session.execute(stmt)
      await session.commit()

    # station url already exists
    if matched_favorites.scalar() > 0:
      self.logger.error('User already has %s as a favorited station', stream_url)
      return False
    # user has max favorites
    if fav_count > self.MAX_FAVORITES:
      self.logger.error('%s already has maximum favorites', user_id)
      return False

    personal_favorite = PersonalFavorite(user_id=user_id, stream_url=stream_url, station_name=station_name)
    async with self.ASYNC_SESSION_LOCAL() as session:
      session.add(personal_favorite)
      await session.commit()
    return True
  async def retrieve_user_favorites(self, user_id: int) -> list[str]:
    async with self.ASYNC_SESSION_LOCAL() as session:
      stmt = select(PersonalFavorite).where(PersonalFavorite.user_id == user_id).order_by(PersonalFavorite.__table__.c.creation_date)
      user_favorites = await session.execute(stmt)
      await session.commit()
    pass
  async def delete_user_favorite(self, user_id: int, favorite_id: int) -> bool:
    pass
