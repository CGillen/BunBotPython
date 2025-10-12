"""
Database abstraction layer for BunBot favorites system.
-- Considerations for eventual migration to cloud based. --
"""

import sqlite3
import os
import logging
import threading
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, ContextManager
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger('discord')

class DatabaseInterface(ABC):
    """Abstract database interface for future cloud migration"""

    @abstractmethod
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results as list of dictionaries"""
        pass

    @abstractmethod
    def execute_non_query(self, query: str, params: tuple = ()) -> int:
        """Execute INSERT/UPDATE/DELETE query and return affected rows"""
        pass

    @abstractmethod
    def transaction(self) -> ContextManager:
        """Get a transaction context manager"""
        pass

    @abstractmethod
    def close(self):
        """Close database connection"""
        pass

class SQLiteDatabase(DatabaseInterface):
    """SQLite implementation of database interface with thread safety and transaction support"""

    def __init__(self, db_path: str = "bunbot.db"):
        self.db_path = db_path
        self.local = threading.local()  # Thread-local storage for connections
        self.init_database()

    def get_connection(self):
        """Get thread-local database connection, create if needed"""
        if not hasattr(self.local, 'connection') or self.local.connection is None:
            self.local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0  # 30 second timeout
            )
            self.local.connection.row_factory = sqlite3.Row  # Enable dict-like access
            # Enable foreign key constraints
            self.local.connection.execute("PRAGMA foreign_keys = ON")
        return self.local.connection

    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def init_database(self):
        """Initialize database tables"""
        logger.info(f"Initializing SQLite database at {self.db_path}")

        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Create favorites table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    favorite_number INTEGER NOT NULL,
                    station_name TEXT NOT NULL,
                    stream_url TEXT NOT NULL,
                    added_by INTEGER NOT NULL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, favorite_number)
                )
            """)

            # Create role hierarchy table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS role_hierarchy (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role_name TEXT UNIQUE NOT NULL,
                    permission_level INTEGER NOT NULL,
                    can_set_favorites BOOLEAN DEFAULT FALSE,
                    can_remove_favorites BOOLEAN DEFAULT FALSE,
                    can_manage_roles BOOLEAN DEFAULT FALSE
                )
            """)

            # Create server roles mapping table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS server_roles (
                    guild_id INTEGER NOT NULL,
                    discord_role_id INTEGER NOT NULL,
                    role_name TEXT NOT NULL,
                    PRIMARY KEY (guild_id, discord_role_id),
                    FOREIGN KEY (role_name) REFERENCES role_hierarchy(role_name)
                )
            """)

            # Insert default role hierarchy if not exists
            cursor.execute("SELECT COUNT(*) FROM role_hierarchy")
            if cursor.fetchone()[0] == 0:
                default_roles = [
                    ('user', 1, False, False, False),
                    ('dj', 2, True, False, False),
                    ('radio manager', 3, True, True, False),
                    ('admin', 4, True, True, True)
                ]

                cursor.executemany("""
                    INSERT INTO role_hierarchy
                    (role_name, permission_level, can_set_favorites, can_remove_favorites, can_manage_roles)
                    VALUES (?, ?, ?, ?, ?)
                """, default_roles)

                logger.info("Inserted default role hierarchy")

            conn.commit()
            logger.info("Database initialization completed successfully")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            conn.rollback()
            raise

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return results as list of dictionaries"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            # Convert sqlite3.Row objects to dictionaries
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Query execution failed: {query} with params {params}. Error: {e}")
            raise

    def execute_non_query(self, query: str, params: tuple = ()) -> int:
        """Execute INSERT/UPDATE/DELETE query and return affected rows"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            logger.error(f"Non-query execution failed: {query} with params {params}. Error: {e}")
            conn.rollback()
            raise

    def close(self):
        """Close thread-local database connection"""
        if hasattr(self.local, 'connection') and self.local.connection:
            self.local.connection.close()
            self.local.connection = None
            logger.info("Database connection closed")

# Global database instance
_db_instance = None

def get_database() -> DatabaseInterface:
    """Get global database instance"""
    global _db_instance
    if _db_instance is None:
        # For now, always use SQLite. Later this can be configured via environment variables
        db_path = os.getenv('DATABASE_PATH', 'bunbot.db')
        _db_instance = SQLiteDatabase(db_path)
    return _db_instance

def close_database():
    """Close global database instance"""
    global _db_instance
    if _db_instance:
        _db_instance.close()
        _db_instance = None
