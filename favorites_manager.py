"""
Favorites management system for BunBot.
Handles CRUD operations for radio station favorites with sequential numbering.
"""

import logging
from typing import List, Dict, Any, Optional
from database import get_database
from stream_validator import get_stream_validator
from input_validator import get_input_validator

logger = logging.getLogger('discord')

class FavoritesManager:
    """Manages radio station favorites for Discord servers"""

    def __init__(self):
        self.db = get_database()
        self.validator = get_stream_validator()
        self.input_validator = get_input_validator()

    async def add_favorite(self, guild_id: int, url: str, name: Optional[str], user_id: int) -> Dict[str, Any]:
        """
        Add a new favorite radio station

        Args:
            guild_id: Discord guild ID
            url: Stream URL
            name: Station name (if None, will auto-detect)
            user_id: User ID who added the favorite

        Returns:
            Dict with 'success', 'favorite_number', 'station_name', 'error' keys
        """
        try:
            # Validate URL input first
            url_validation = self.input_validator.validate_url(url)
            if not url_validation['valid']:
                return {
                    'success': False,
                    'error': url_validation['error'],
                    'favorite_number': None,
                    'station_name': None
                }

            # Use sanitized URL
            url = url_validation['sanitized_url']

            # Validate station name if provided
            if name:
                name_validation = self.input_validator.validate_station_name(name)
                if not name_validation['valid']:
                    return {
                        'success': False,
                        'error': name_validation['error'],
                        'favorite_number': None,
                        'station_name': None
                    }
                name = name_validation['sanitized_name']

            # Validate the stream
            validation = await self.validator.validate_stream(url)
            if not validation['valid']:
                logger.warning(f"Stream validation failed for {url}: {validation['error']}")
                return {
                    'success': False,
                    'error': validation['error'],
                    'favorite_number': None,
                    'station_name': None
                }

            # Use provided name or auto-detected name
            station_name = name if name else validation['station_name']

            # Validate the final station name
            if station_name:
                final_name_validation = self.input_validator.validate_station_name(station_name)
                if not final_name_validation['valid']:
                    return {
                        'success': False,
                        'error': f"Auto-detected station name is invalid: {final_name_validation['error']}",
                        'favorite_number': None,
                        'station_name': None
                    }
                station_name = final_name_validation['sanitized_name']

            # Use transaction to ensure atomic favorite addition
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                # Check for duplicate URLs in this guild within transaction
                cursor.execute("""
                    SELECT favorite_number, station_name
                    FROM favorites
                    WHERE guild_id = ? AND stream_url = ?
                """, (guild_id, url))

                existing = cursor.fetchone()
                if existing:
                    return {
                        'success': False,
                        'error': f"This stream is already saved as favorite #{existing[0]}: {existing[1]}",
                        'favorite_number': existing[0],
                        'station_name': existing[1]
                    }

                # Get next available favorite number atomically
                cursor.execute("""
                    SELECT MAX(favorite_number) as max_num
                    FROM favorites
                    WHERE guild_id = ?
                """, (guild_id,))

                result = cursor.fetchone()
                favorite_number = (result[0] if result and result[0] else 0) + 1

                # Insert the new favorite
                cursor.execute("""
                    INSERT INTO favorites (guild_id, favorite_number, station_name, stream_url, added_by)
                    VALUES (?, ?, ?, ?, ?)
                """, (guild_id, favorite_number, station_name, url, user_id))

            logger.info(f"Added favorite #{favorite_number} for guild {guild_id}: {station_name}")
            return {
                'success': True,
                'favorite_number': favorite_number,
                'station_name': station_name,
                'error': None
            }

        except Exception as e:
            logger.error(f"Error adding favorite: {e}")
            return {
                'success': False,
                'error': f"Database error: {str(e)}",
                'favorite_number': None,
                'station_name': None
            }

    def get_favorite_by_number(self, guild_id: int, number: int) -> Optional[Dict[str, Any]]:
        """
        Get a favorite by its number

        Args:
            guild_id: Discord guild ID
            number: Favorite number

        Returns:
            Favorite data dict or None if not found
        """
        try:
            results = self.db.execute_query("""
                SELECT id, favorite_number, station_name, stream_url, added_by, added_at
                FROM favorites
                WHERE guild_id = ? AND favorite_number = ?
            """, (guild_id, number))

            return results[0] if results else None

        except Exception as e:
            logger.error(f"Error getting favorite #{number}: {e}")
            return None

    def get_favorites(self, guild_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all favorites for a guild

        Args:
            guild_id: Discord guild ID
            limit: Maximum number of favorites to return (None for all)

        Returns:
            List of favorite data dicts
        """
        try:
            query = """
                SELECT id, favorite_number, station_name, stream_url, added_by, added_at
                FROM favorites
                WHERE guild_id = ?
                ORDER BY favorite_number ASC
            """

            if limit is not None and limit > 0:
                query += f" LIMIT {limit}"

            results = self.db.execute_query(query, (guild_id,))
            return results

        except Exception as e:
            logger.error(f"Error getting favorites for guild {guild_id}: {e}")
            return []

    def remove_favorite(self, guild_id: int, number: int) -> Dict[str, Any]:
        """
        Remove a favorite and reorder subsequent numbers atomically

        Args:
            guild_id: Discord guild ID
            number: Favorite number to remove

        Returns:
            Dict with 'success', 'station_name', 'error' keys
        """
        try:
            # Use transaction to ensure atomicity
            with self.db.transaction() as conn:
                cursor = conn.cursor()

                # Get the favorite before deleting for return info
                cursor.execute("""
                    SELECT station_name FROM favorites
                    WHERE guild_id = ? AND favorite_number = ?
                """, (guild_id, number))

                result = cursor.fetchone()
                if not result:
                    return {
                        'success': False,
                        'error': f"Favorite #{number} not found",
                        'station_name': None
                    }

                station_name = result[0]

                # Remove the favorite
                cursor.execute("""
                    DELETE FROM favorites
                    WHERE guild_id = ? AND favorite_number = ?
                """, (guild_id, number))

                # Reorder subsequent favorites (decrement their numbers)
                cursor.execute("""
                    UPDATE favorites
                    SET favorite_number = favorite_number - 1
                    WHERE guild_id = ? AND favorite_number > ?
                """, (guild_id, number))

                logger.info(f"Removed favorite #{number} from guild {guild_id}: {station_name}")
                return {
                    'success': True,
                    'station_name': station_name,
                    'error': None
                }

        except Exception as e:
            logger.error(f"Error removing favorite #{number}: {e}")
            return {
                'success': False,
                'error': f"Database error: {str(e)}",
                'station_name': None
            }

    def get_next_favorite_number(self, guild_id: int) -> int:
        """
        Get the next available favorite number for a guild

        Args:
            guild_id: Discord guild ID

        Returns:
            Next sequential favorite number
        """
        try:
            results = self.db.execute_query("""
                SELECT MAX(favorite_number) as max_num
                FROM favorites
                WHERE guild_id = ?
            """, (guild_id,))

            max_num = results[0]['max_num'] if results and results[0]['max_num'] else 0
            return max_num + 1

        except Exception as e:
            logger.error(f"Error getting next favorite number: {e}")
            return 1  # Default to 1 on error

    def get_favorites_count(self, guild_id: int) -> int:
        """
        Get the total number of favorites for a guild

        Args:
            guild_id: Discord guild ID

        Returns:
            Number of favorites
        """
        try:
            results = self.db.execute_query("""
                SELECT COUNT(*) as count
                FROM favorites
                WHERE guild_id = ?
            """, (guild_id,))

            return results[0]['count'] if results else 0

        except Exception as e:
            logger.error(f"Error getting favorites count: {e}")
            return 0

    def update_favorite_name(self, guild_id: int, number: int, new_name: str) -> bool:
        """
        Update the name of a favorite

        Args:
            guild_id: Discord guild ID
            number: Favorite number
            new_name: New station name

        Returns:
            True if update was successful
        """
        try:
            affected_rows = self.db.execute_non_query("""
                UPDATE favorites
                SET station_name = ?
                WHERE guild_id = ? AND favorite_number = ?
            """, (new_name, guild_id, number))

            success = affected_rows > 0
            if success:
                logger.info(f"Updated favorite #{number} name to '{new_name}' in guild {guild_id}")
            else:
                logger.warning(f"Favorite #{number} not found for update in guild {guild_id}")

            return success

        except Exception as e:
            logger.error(f"Error updating favorite name: {e}")
            return False

    def search_favorites(self, guild_id: int, search_term: str) -> List[Dict[str, Any]]:
        """
        Search favorites by station name

        Args:
            guild_id: Discord guild ID
            search_term: Search term for station names

        Returns:
            List of matching favorites
        """
        try:
            results = self.db.execute_query("""
                SELECT id, favorite_number, station_name, stream_url, added_by, added_at
                FROM favorites
                WHERE guild_id = ? AND station_name LIKE ?
                ORDER BY favorite_number ASC
            """, (guild_id, f"%{search_term}%"))

            return results

        except Exception as e:
            logger.error(f"Error searching favorites: {e}")
            return []

    async def validate_all_favorites(self, guild_id: int) -> Dict[str, List[Dict[str, Any]]]:
        """
        Validate all favorites for a guild and return status

        Args:
            guild_id: Discord guild ID

        Returns:
            Dict with 'online', 'offline', 'error' lists
        """
        favorites = self.get_favorites(guild_id)
        online = []
        offline = []
        error = []

        for favorite in favorites:
            try:
                validation = await self.validator.validate_stream(favorite['stream_url'])
                if validation['valid']:
                    online.append(favorite)
                else:
                    offline.append({**favorite, 'error': validation['error']})
            except Exception as e:
                error.append({**favorite, 'error': str(e)})

        return {
            'online': online,
            'offline': offline,
            'error': error
        }

# Global favorites manager instance
_favorites_manager = None

def get_favorites_manager() -> FavoritesManager:
    """Get global favorites manager instance"""
    global _favorites_manager
    if _favorites_manager is None:
        _favorites_manager = FavoritesManager()
    return _favorites_manager
