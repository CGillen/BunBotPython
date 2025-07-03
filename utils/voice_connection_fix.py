"""
Voice Connection Fix - Updated for Discord.py v8 with 4006 Error Handling

This module provides enhanced voice connection with specific handling for the 
4006 WebSocket error that affects US Discord servers.
"""

import logging
import asyncio
import discord

logger = logging.getLogger('discord.voice_connection_fix')

async def connect_to_voice_channel_safe(guild: discord.Guild, 
                                       channel: discord.VoiceChannel,
                                       timeout: float = 30.0,
                                       max_retries: int = 5) -> discord.VoiceClient:
    """
    Connect to voice channel with enhanced 4006 error handling.
    
    This function uses the native Discord.py v8 fix with additional retry logic
    specifically for the 4006 WebSocket error that affects US Discord servers.
    
    Args:
        guild: Discord guild
        channel: Voice channel to connect to
        timeout: Connection timeout in seconds
        max_retries: Maximum retry attempts
        
    Returns:
        VoiceClient if successful
        
    Raises:
        Exception: If connection fails after all retries
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            logger.info(f"[{guild.id}]: Voice connection attempt {attempt + 1}/{max_retries}")
            
            # Use native Discord.py connection with the v8 fix
            voice_client = await channel.connect(timeout=timeout, reconnect=True)
            
            logger.info(f"[{guild.id}]: Voice connection successful on attempt {attempt + 1}")
            return voice_client
            
        except discord.errors.ConnectionClosed as e:
            last_error = e
            
            # Check if it's a 4006 error (session no longer valid)
            if hasattr(e, 'code') and e.code == 4006:
                logger.warning(f"[{guild.id}]: 4006 error on attempt {attempt + 1} - session invalid")
                
                # For 4006 errors, wait longer between retries to let Discord reset
                if attempt < max_retries - 1:
                    wait_time = 3.0 + (attempt * 2.0)  # Increasing wait time
                    logger.info(f"[{guild.id}]: Waiting {wait_time}s before retry due to 4006 error")
                    await asyncio.sleep(wait_time)
            else:
                logger.warning(f"[{guild.id}]: Connection closed with code {getattr(e, 'code', 'unknown')}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(1.0 + attempt)
                    
        except asyncio.TimeoutError as e:
            last_error = e
            logger.warning(f"[{guild.id}]: Connection timeout on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2.0)
                
        except Exception as e:
            last_error = e
            logger.warning(f"[{guild.id}]: Connection error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1.0 + attempt)
    
    # All attempts failed
    logger.error(f"[{guild.id}]: Failed to connect after {max_retries} attempts. Last error: {last_error}")
    raise RuntimeError(f"Failed to connect to voice channel after {max_retries} attempts: {last_error}")


async def disconnect_voice_client_safe(guild: discord.Guild, force: bool = False) -> bool:
    """
    Safely disconnect voice client.
    
    Args:
        guild: Discord guild
        force: Whether to force disconnection
        
    Returns:
        True if disconnected successfully
    """
    try:
        if not guild.voice_client:
            return True
        
        logger.info(f"[{guild.id}]: Disconnecting voice client")
        await guild.voice_client.disconnect(force=force)
        logger.info(f"[{guild.id}]: Voice client disconnected successfully")
        return True
        
    except Exception as e:
        logger.error(f"[{guild.id}]: Error disconnecting voice client: {e}")
        return False


def is_us_voice_server(endpoint: str) -> bool:
    """
    Check if a voice endpoint is a US server (most affected by 4006 errors).
    
    Args:
        endpoint: Voice endpoint (e.g., 'c-dfw11-aa482543.discord.media')
        
    Returns:
        True if it's a US server
    """
    us_indicators = [
        'dfw',    # Dallas
        'lax',    # Los Angeles  
        'mia',    # Miami
        'ord',    # Chicago
        'atl',    # Atlanta
        'sea',    # Seattle
        'sjc',    # San Jose
        'us-',    # General US prefix
    ]
    
    endpoint_lower = endpoint.lower()
    return any(indicator in endpoint_lower for indicator in us_indicators)
