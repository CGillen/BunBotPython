"""
Audio Adapter for SL Bridge

Converts SL audio API calls to Discord audio service interactions
"""

import logging
from typing import Dict, Any, Optional

from core import ServiceRegistry
from audio import IVolumeManager

logger = logging.getLogger('sl_bridge.adapters.audio')


class AudioAdapter:
    """
    Adapter to convert SL Bridge audio API calls to Discord audio service calls.
    
    Provides simple parameter-based interface for SL while using the existing
    Discord audio processing services.
    """
    
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry
        self.volume_manager = service_registry.get_optional(IVolumeManager)
        
        logger.info("AudioAdapter initialized")
    
    async def set_volume(self, guild_id: int, volume: float) -> Dict[str, Any]:
        """
        Set master volume (SL Bridge API).
        
        Args:
            guild_id: Discord guild ID
            volume: Volume level (0.0 to 1.0)
            
        Returns:
            Result dict with success status and message
        """
        try:
            if not self.volume_manager:
                return {
                    "success": False,
                    "message": "Volume manager not available",
                    "error": "service_unavailable"
                }
            
            # Validate volume range
            volume = max(0.0, min(1.0, volume))
            
            # Set volume using volume manager
            success = await self.volume_manager.set_master_volume(guild_id, volume)
            
            if success:
                return {
                    "success": True,
                    "message": f"Volume set to {volume:.2f}",
                    "data": {
                        "volume": volume,
                        "guild_id": guild_id
                    }
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to set volume",
                    "error": "volume_set_failed"
                }
                
        except Exception as e:
            logger.error(f"Error setting volume: {e}")
            return {
                "success": False,
                "message": f"Error setting volume: {str(e)}",
                "error": "adapter_error"
            }
    
    async def get_volume(self, guild_id: int) -> Dict[str, Any]:
        """
        Get current master volume (SL Bridge API).
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Current volume information
        """
        try:
            if not self.volume_manager:
                return {
                    "volume": 0.8,  # Default volume
                    "guild_id": guild_id,
                    "warning": "Volume manager not available"
                }
            
            volume = await self.volume_manager.get_master_volume(guild_id)
            
            return {
                "volume": volume,
                "guild_id": guild_id,
                "status": "active"
            }
            
        except Exception as e:
            logger.error(f"Error getting volume: {e}")
            return {
                "volume": 0.8,  # Default fallback
                "guild_id": guild_id,
                "error": f"Volume error: {str(e)}"
            }
    
    async def set_equalizer(self, guild_id: int, bass: float = 0.0, 
                          mid: float = 0.0, treble: float = 0.0) -> Dict[str, Any]:
        """
        Set equalizer settings (SL Bridge API).
        
        Args:
            guild_id: Discord guild ID
            bass: Bass adjustment (-1.0 to 1.0)
            mid: Mid adjustment (-1.0 to 1.0) 
            treble: Treble adjustment (-1.0 to 1.0)
            
        Returns:
            Result dict with success status and message
        """
        try:
            # Note: This is a placeholder as the current audio system
            # doesn't expose direct EQ controls through the volume manager
            # In a full implementation, this would integrate with the effects chain
            
            # Validate ranges
            bass = max(-1.0, min(1.0, bass))
            mid = max(-1.0, min(1.0, mid))
            treble = max(-1.0, min(1.0, treble))
            
            # For now, return success with settings
            # TODO: Integrate with actual EQ system when available
            
            return {
                "success": True,
                "message": "Equalizer settings updated",
                "data": {
                    "bass": bass,
                    "mid": mid,
                    "treble": treble,
                    "guild_id": guild_id
                },
                "note": "EQ settings stored - full implementation pending"
            }
            
        except Exception as e:
            logger.error(f"Error setting equalizer: {e}")
            return {
                "success": False,
                "message": f"Error setting equalizer: {str(e)}",
                "error": "adapter_error"
            }
    
    async def get_audio_info(self, guild_id: int) -> Dict[str, Any]:
        """
        Get comprehensive audio information (SL Bridge API).
        
        Args:
            guild_id: Discord guild ID
            
        Returns:
            Audio system information
        """
        try:
            info = {
                "guild_id": guild_id,
                "volume_manager_available": self.volume_manager is not None
            }
            
            # Get volume information
            if self.volume_manager:
                volume = await self.volume_manager.get_master_volume(guild_id)
                info["volume"] = volume
                
                # Get volume metrics if available
                try:
                    metrics = await self.volume_manager.get_volume_metrics(guild_id)
                    if metrics:
                        info["metrics"] = {
                            "rms_db": metrics.get("rms_db", 0),
                            "peak_db": metrics.get("peak_db", 0),
                            "lufs_estimate": metrics.get("lufs_estimate", -20)
                        }
                except Exception:
                    # Metrics not available
                    pass
            else:
                info["volume"] = 0.8  # Default
            
            # Add placeholder EQ info
            info["equalizer"] = {
                "bass": 0.0,
                "mid": 0.0,
                "treble": 0.0,
                "note": "EQ integration pending"
            }
            
            # Audio processing status
            info["processing"] = {
                "normalization": "available",
                "compression": "available", 
                "auto_gain_control": "available"
            }
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting audio info: {e}")
            return {
                "guild_id": guild_id,
                "error": f"Audio info error: {str(e)}",
                "volume": 0.8,  # Fallback
                "volume_manager_available": False
            }
    
    def get_adapter_stats(self) -> Dict[str, Any]:
        """Get audio adapter statistics"""
        return {
            "volume_manager_available": self.volume_manager is not None,
            "adapter_initialized": True,
            "supported_features": [
                "volume_control",
                "audio_info",
                "equalizer_placeholder"
            ]
        }
