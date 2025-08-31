"""
BunBot - Discord Radio Bot

Usage:
    python bot.py

Environment Variables:
    BOT_TOKEN - Discord bot token (required)
    LOG_LEVEL - Logging level (default: INFO)
    LOG_FILE_PATH - Path for log files (default: ./)
    TLS_VERIFY - Enable TLS verification (default: True)
    CLUSTER_ID - Cluster ID for sharding (default: 0)
    TOTAL_CLUSTERS - Total number of clusters (default: 1)
    TOTAL_SHARDS - Total number of shards (default: 1)
"""

import logging
import sys
from pathlib import Path

# Set up basic logging first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger('bunbot')

def main():
    """Main entry point for BunBot"""
    try:
        logger.info("Starting BunBot...")
        logger.info("🎵 BunBot - Discord radio bot")
        
        # Start keep-alive server for cloud deployment
        try:
            from keep_alive import start_keep_alive
            start_keep_alive()
            logger.info("Keep-alive server started for cloud deployment")
        except ImportError:
            logger.info("Keep-alive server not available (running locally)")
        except Exception as e:
            logger.warning(f"Failed to start keep-alive server: {e}")
        
        # Import and create the application
        from services.bot_application import create_application
        
        app = create_application()
        
        # Run the application
        app.run_sync()
        
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error("Make sure all dependencies are installed:")
        logger.error("  pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Application failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
