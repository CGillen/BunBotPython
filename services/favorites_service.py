"""
Favorites Service for BunBot
"""

import logging
import sqlite3
from typing import Dict, Any, Optional, List
from datetime import datetime
import discord

from core import ServiceRegistry, StateManager, EventBus

logger = logging.getLogger('services.favorites_service')

class FavoritesService:
    """
    Favorites management service for BunBot.
    
    Provides database-backed favorites management with stream validation.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.state_manager = service_registry.get(StateManager)
        self.event_bus = service_registry.get(EventBus)
        
        # Initialize database
        self.db_path = "bunbot.db"
        self._init_database()
        
        logger.info("FavoritesService initialized")
    
    def _init_database(self):
        """Initialize the favorites database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Create table with all columns
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS favorites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        favorite_number INTEGER NOT NULL,
                        stream_url TEXT NOT NULL,
                        station_name TEXT NOT NULL,
                        added_by INTEGER,
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(guild_id, favorite_number)
                    )
                """)
                
                # Add added_date column if it doesn't exist (for existing databases)
                try:
                    conn.execute("SELECT added_date FROM favorites LIMIT 1")
                except sqlite3.OperationalError:
                    # Column doesn't exist, add it
                    conn.execute("ALTER TABLE favorites ADD COLUMN added_date TIMESTAMP")
                    logger.info("Added added_date column to existing favorites table")
                
                conn.commit()
                logger.info("Initialized SQLite database at bunbot.db")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def add_favorite(self, guild_id: int, url: str, name: Optional[str] = None, 
                          user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Add a favorite radio station for a guild.
        
        Args:
            guild_id: Discord guild ID
            url: Stream URL to add
            name: Optional custom name for the station
            user_id: User who added the favorite
            
        Returns:
            Result dictionary with success status and details
        """
        try:
            logger.info(f"[{guild_id}]: Adding favorite: {url}")
            
            # Validate URL format
            if not self._is_valid_url(url):
                return {
                    'success': False,
                    'error': 'Invalid URL format provided'
                }
            
            # Validate stream is accessible
            if not await self._validate_stream(url):
                return {
                    'success': False,
                    'error': 'Stream is not accessible or invalid'
                }
            
            # Get station name from stream if not provided
            if not name:
                try:
                    from streamscrobbler import streamscrobbler
                    station_info = streamscrobbler.get_server_info(url)
                    name = station_info.get('server_name', 'Unknown Station') if station_info else 'Unknown Station'
                except:
                    name = 'Unknown Station'
            
            # Get next favorite number
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT MAX(favorite_number) FROM favorites WHERE guild_id = ?",
                    (guild_id,)
                )
                max_num = cursor.fetchone()[0]
                next_number = (max_num or 0) + 1
                
                # Insert new favorite
                conn.execute("""
                    INSERT INTO favorites (guild_id, favorite_number, stream_url, station_name, added_by)
                    VALUES (?, ?, ?, ?, ?)
                """, (guild_id, next_number, url, name, user_id or 0))
                conn.commit()
            
            # Emit success event
            await self.event_bus.emit_async('favorite_added',
                                          guild_id=guild_id,
                                          url=url,
                                          station_name=name,
                                          favorite_number=next_number,
                                          user_id=user_id)
            
            logger.info(f"[{guild_id}]: Added favorite #{next_number}: {name}")
            
            return {
                'success': True,
                'station_name': name,
                'favorite_number': next_number
            }
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to add favorite: {e}")
            return {
                'success': False,
                'error': f'Internal error: {str(e)}'
            }
    
    async def remove_favorite(self, guild_id: int, number: int) -> Dict[str, Any]:
        """
        Remove a favorite radio station by number.
        
        Args:
            guild_id: Discord guild ID
            number: Favorite number to remove
            
        Returns:
            Result dictionary with success status and details
        """
        try:
            logger.info(f"[{guild_id}]: Removing favorite #{number}")
            
            # Check if favorite exists and get its name
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT station_name FROM favorites WHERE guild_id = ? AND favorite_number = ?",
                    (guild_id, number)
                )
                result = cursor.fetchone()
                
                if not result:
                    return {
                        'success': False,
                        'error': f'Favorite #{number} not found'
                    }
                
                station_name = result[0]
                
                # Remove the favorite
                conn.execute(
                    "DELETE FROM favorites WHERE guild_id = ? AND favorite_number = ?",
                    (guild_id, number)
                )
                
                # Renumber remaining favorites
                conn.execute("""
                    UPDATE favorites 
                    SET favorite_number = favorite_number - 1 
                    WHERE guild_id = ? AND favorite_number > ?
                """, (guild_id, number))
                
                conn.commit()
            
            # Emit success event
            await self.event_bus.emit_async('favorite_removed',
                                          guild_id=guild_id,
                                          number=number,
                                          station_name=station_name)
            
            logger.info(f"[{guild_id}]: Removed favorite #{number}: {station_name}")
            
            return {
                'success': True,
                'station_name': station_name
            }
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to remove favorite: {e}")
            return {
                'success': False,
                'error': f'Internal error: {str(e)}'
            }
    
    def get_favorite_by_number(self, guild_id: int, number: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific favorite by number.
        
        Args:
            guild_id: Discord guild ID
            number: Favorite number
            
        Returns:
            Favorite data or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT favorite_number, stream_url, station_name, added_by, added_date
                    FROM favorites 
                    WHERE guild_id = ? AND favorite_number = ?
                """, (guild_id, number))
                result = cursor.fetchone()
                
                if result:
                    return {
                        'favorite_number': result[0],
                        'stream_url': result[1],
                        'station_name': result[2],
                        'added_by': result[3],
                        'added_date': result[4]
                    }
                return None
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to get favorite #{number}: {e}")
            return None
    
    def get_all_favorites(self, guild_id: int) -> List[Dict[str, Any]]:
        """
        Get all favorites for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            List of favorite data dictionaries
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT favorite_number, stream_url, station_name, added_by, added_date
                    FROM favorites 
                    WHERE guild_id = ? 
                    ORDER BY favorite_number
                """, (guild_id,))
                results = cursor.fetchall()
                
                favorites = []
                for result in results:
                    favorites.append({
                        'favorite_number': result[0],
                        'stream_url': result[1],
                        'station_name': result[2],
                        'added_by': result[3],
                        'added_date': result[4]
                    })
                
                return favorites
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to get favorites: {e}")
            return []
    
    def get_favorites_count(self, guild_id: int) -> int:
        """
        Get the total number of favorites for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Number of favorites
        """
        try:
            favorites = self.get_all_favorites(guild_id)
            return len(favorites)
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to get favorites count: {e}")
            return 0
    
    def search_favorites(self, guild_id: int, query: str) -> List[Dict[str, Any]]:
        """
        Search favorites by name or URL.
        
        Args:
            guild_id: Discord guild ID
            query: Search query
            
        Returns:
            List of matching favorites
        """
        try:
            all_favorites = self.get_all_favorites(guild_id)
            query_lower = query.lower()
            
            matching_favorites = []
            for favorite in all_favorites:
                station_name = favorite.get('station_name', '').lower()
                stream_url = favorite.get('stream_url', '').lower()
                
                if query_lower in station_name or query_lower in stream_url:
                    matching_favorites.append(favorite)
            
            logger.debug(f"[{guild_id}]: Found {len(matching_favorites)} favorites matching '{query}'")
            return matching_favorites
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to search favorites: {e}")
            return []
    
    async def validate_all_favorites(self, guild_id: int) -> Dict[str, Any]:
        """
        Validate all favorites for a guild and report any issues.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Validation results with counts and details
        """
        try:
            logger.info(f"[{guild_id}]: Validating all favorites")
            
            favorites = self.get_all_favorites(guild_id)
            if not favorites:
                return {
                    'total': 0,
                    'valid': 0,
                    'invalid': 0,
                    'invalid_favorites': []
                }
            
            valid_count = 0
            invalid_favorites = []
            
            for favorite in favorites:
                url = favorite.get('stream_url', '')
                is_valid = await self._validate_stream(url)
                
                if is_valid:
                    valid_count += 1
                else:
                    invalid_favorites.append({
                        'number': favorite.get('favorite_number'),
                        'name': favorite.get('station_name'),
                        'url': url
                    })
            
            result = {
                'total': len(favorites),
                'valid': valid_count,
                'invalid': len(invalid_favorites),
                'invalid_favorites': invalid_favorites
            }
            
            # Emit validation event
            await self.event_bus.emit_async('favorites_validated',
                                          guild_id=guild_id,
                                          **result)
            
            logger.info(f"[{guild_id}]: Validation complete - {valid_count}/{len(favorites)} valid")
            return result
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to validate favorites: {e}")
            return {
                'total': 0,
                'valid': 0,
                'invalid': 0,
                'invalid_favorites': [],
                'error': str(e)
            }
    
    async def import_favorites(self, guild_id: int, favorites_data: List[Dict[str, Any]], 
                             user_id: int) -> Dict[str, Any]:
        """
        Import a list of favorites for a guild.
        
        Args:
            guild_id: Discord guild ID
            favorites_data: List of favorite data to import
            user_id: User performing the import
            
        Returns:
            Import results with success/failure counts
        """
        try:
            logger.info(f"[{guild_id}]: Importing {len(favorites_data)} favorites")
            
            imported = 0
            failed = 0
            errors = []
            
            for favorite_data in favorites_data:
                try:
                    url = favorite_data.get('url') or favorite_data.get('stream_url')
                    name = favorite_data.get('name') or favorite_data.get('station_name')
                    
                    if not url:
                        errors.append(f"Missing URL in favorite data: {favorite_data}")
                        failed += 1
                        continue
                    
                    result = await self.add_favorite(guild_id, url, name, user_id)
                    
                    if result['success']:
                        imported += 1
                    else:
                        failed += 1
                        errors.append(f"Failed to import {url}: {result.get('error')}")
                        
                except Exception as e:
                    failed += 1
                    errors.append(f"Error importing favorite: {e}")
            
            result = {
                'total': len(favorites_data),
                'imported': imported,
                'failed': failed,
                'errors': errors
            }
            
            # Emit import event
            await self.event_bus.emit_async('favorites_imported',
                                          guild_id=guild_id,
                                          user_id=user_id,
                                          **result)
            
            logger.info(f"[{guild_id}]: Import complete - {imported}/{len(favorites_data)} imported")
            return result
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to import favorites: {e}")
            return {
                'total': len(favorites_data) if favorites_data else 0,
                'imported': 0,
                'failed': len(favorites_data) if favorites_data else 0,
                'errors': [f"Import failed: {e}"]
            }
    
    async def export_favorites(self, guild_id: int) -> Dict[str, Any]:
        """
        Export all favorites for a guild.
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Export data with favorites list and metadata
        """
        try:
            favorites = self.get_all_favorites(guild_id)
            
            export_data = {
                'guild_id': guild_id,
                'export_date': datetime.now().isoformat(),
                'total_favorites': len(favorites),
                'favorites': favorites
            }
            
            logger.info(f"[{guild_id}]: Exported {len(favorites)} favorites")
            return export_data
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to export favorites: {e}")
            return {
                'guild_id': guild_id,
                'export_date': datetime.now().isoformat(),
                'total_favorites': 0,
                'favorites': [],
                'error': str(e)
            }
    
    async def _validate_stream(self, url: str) -> bool:
        """Validate that a stream URL is accessible"""
        try:
            # Use streamscrobbler validation
            from streamscrobbler import streamscrobbler
            station_info = streamscrobbler.get_server_info(url)
            return bool(station_info and station_info.get('status', 0) > 0)
            
        except Exception as e:
            logger.debug(f"Stream validation failed for {url}: {e}")
            return False
    
    def _is_valid_url(self, url: str) -> bool:
        """Validate URL format"""
        try:
            import validators
            result = validators.url(url)
            return bool(result)
            
        except ImportError:
            # Simple fallback
            return url.startswith(('http://', 'https://'))
        except Exception as e:
            logger.debug(f"URL validation failed for {url}: {e}")
            return False
    
    def get_favorites_stats(self, guild_id: int) -> Dict[str, Any]:
        """Get statistics about favorites for a guild"""
        try:
            favorites = self.get_all_favorites(guild_id)
            
            # Analyze station types by URL patterns
            stream_types = {}
            for favorite in favorites:
                url = favorite.get('stream_url', '')
                if 'shoutcast' in url.lower():
                    stream_types['shoutcast'] = stream_types.get('shoutcast', 0) + 1
                elif 'icecast' in url.lower():
                    stream_types['icecast'] = stream_types.get('icecast', 0) + 1
                else:
                    stream_types['other'] = stream_types.get('other', 0) + 1
            
            return {
                'total_favorites': len(favorites),
                'stream_types': stream_types,
                'has_favorites': len(favorites) > 0,
                'max_favorites': 50  # Assumed limit
            }
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to get favorites stats: {e}")
            return {
                'total_favorites': 0,
                'stream_types': {},
                'has_favorites': False,
                'max_favorites': 50
            }
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get overall service statistics"""
        database_available = False
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("SELECT 1").fetchone()
                database_available = True
        except Exception:
            database_available = False
        
        # Check if service is properly initialized
        service_initialized = (
            hasattr(self, 'service_registry') and self.service_registry is not None and
            hasattr(self, 'state_manager') and self.state_manager is not None and
            hasattr(self, 'event_bus') and self.event_bus is not None and
            hasattr(self, 'db_path') and self.db_path is not None
        )
            
        return {
            'database_available': database_available,
            'service_initialized': service_initialized
        }
