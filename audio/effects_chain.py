"""
Audio Effects Chain for BunBot Audio Processing
"""

import logging
import asyncio
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import numpy as np

from core import StateManager, EventBus, ConfigurationManager
from .interfaces import (
    IEffectsChain, EffectType, AudioConfig, AUDIO_EVENTS
)

logger = logging.getLogger('discord.audio.effects_chain')

class EffectsChain(IEffectsChain):
    """
    Audio effects processing chain for BunBot.
    
    Manages a dynamic chain of audio effects that can be applied in real-time
    to enhance audio quality and provide creative processing capabilities.
    """
    
    def __init__(self, state_manager: StateManager, event_bus: EventBus, 
                 config_manager: ConfigurationManager):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.config_manager = config_manager
        
        # Effects chain state
        self._effect_chains: Dict[int, List[Dict[str, Any]]] = {}  # guild_id -> effects list
        self._effect_parameters: Dict[str, Dict[str, Any]] = {}    # effect_id -> parameters
        
        # EQ presets
        self._eq_presets = {
            'flat': {'bass': 0.0, 'mid': 0.0, 'treble': 0.0},
            'rock': {'bass': 4.0, 'mid': 2.0, 'treble': 3.0},
            'pop': {'bass': 2.0, 'mid': 1.0, 'treble': 4.0},
            'jazz': {'bass': 3.0, 'mid': -1.0, 'treble': 2.0},
            'classical': {'bass': 1.0, 'mid': -2.0, 'treble': 3.0},
            'electronic': {'bass': 6.0, 'mid': -2.0, 'treble': 4.0},
            'vocal': {'bass': -2.0, 'mid': 4.0, 'treble': 2.0},
            'bass_boost': {'bass': 8.0, 'mid': 0.0, 'treble': 0.0},
            'treble_boost': {'bass': 0.0, 'mid': 0.0, 'treble': 8.0}
        }
        
        # Crossfade state
        self._crossfade_state: Dict[int, Dict[str, Any]] = {}  # guild_id -> crossfade_info
        
        logger.info("EffectsChain initialized")
    
    async def add_effect(self, guild_id: int, effect_type: EffectType, 
                        parameters: Dict[str, Any]) -> str:
        """
        Add an effect to the processing chain.
        
        Args:
            guild_id: Discord guild ID
            effect_type: Type of effect to add
            parameters: Effect-specific parameters
            
        Returns:
            Effect ID for future reference
        """
        try:
            effect_id = str(uuid.uuid4())[:8]
            
            # Create effect definition
            effect_def = {
                'id': effect_id,
                'type': effect_type,
                'parameters': parameters.copy(),
                'enabled': True,
                'created_at': datetime.now(timezone.utc)
            }
            
            # Add to guild's effect chain
            if guild_id not in self._effect_chains:
                self._effect_chains[guild_id] = []
            
            self._effect_chains[guild_id].append(effect_def)
            self._effect_parameters[effect_id] = parameters.copy()
            
            # Emit effect added event
            await self.event_bus.emit_async(AUDIO_EVENTS['audio_effect_applied'],
                                          guild_id=guild_id,
                                          effect_id=effect_id,
                                          effect_type=effect_type.value,
                                          parameters=parameters)
            
            logger.info(f"[{guild_id}]: Added {effect_type.value} effect: {effect_id}")
            return effect_id
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to add effect: {e}")
            return ""
    
    async def remove_effect(self, guild_id: int, effect_id: str) -> bool:
        """
        Remove an effect from the processing chain.
        
        Args:
            guild_id: Discord guild ID
            effect_id: Effect ID to remove
            
        Returns:
            True if effect was removed successfully
        """
        try:
            if guild_id not in self._effect_chains:
                return False
            
            # Find and remove the effect
            effects = self._effect_chains[guild_id]
            for i, effect in enumerate(effects):
                if effect['id'] == effect_id:
                    removed_effect = effects.pop(i)
                    
                    # Clean up parameters
                    if effect_id in self._effect_parameters:
                        del self._effect_parameters[effect_id]
                    
                    # Emit effect removed event
                    await self.event_bus.emit_async(AUDIO_EVENTS['audio_effect_removed'],
                                                  guild_id=guild_id,
                                                  effect_id=effect_id,
                                                  effect_type=removed_effect['type'].value)
                    
                    logger.info(f"[{guild_id}]: Removed effect: {effect_id}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to remove effect {effect_id}: {e}")
            return False
    
    async def update_effect(self, guild_id: int, effect_id: str, 
                           parameters: Dict[str, Any]) -> bool:
        """
        Update effect parameters.
        
        Args:
            guild_id: Discord guild ID
            effect_id: Effect ID to update
            parameters: New parameters
            
        Returns:
            True if effect was updated successfully
        """
        try:
            if guild_id not in self._effect_chains:
                return False
            
            # Find and update the effect
            effects = self._effect_chains[guild_id]
            for effect in effects:
                if effect['id'] == effect_id:
                    effect['parameters'].update(parameters)
                    self._effect_parameters[effect_id].update(parameters)
                    
                    logger.info(f"[{guild_id}]: Updated effect {effect_id}: {list(parameters.keys())}")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to update effect {effect_id}: {e}")
            return False
    
    async def set_eq(self, guild_id: int, bass: float, mid: float, treble: float) -> bool:
        """
        Set 3-band equalizer values.
        
        Args:
            guild_id: Discord guild ID
            bass: Bass adjustment (-12 to +12 dB)
            mid: Mid adjustment (-12 to +12 dB)
            treble: Treble adjustment (-12 to +12 dB)
            
        Returns:
            True if EQ was set successfully
        """
        try:
            # Validate ranges
            bass = max(-12.0, min(12.0, bass))
            mid = max(-12.0, min(12.0, mid))
            treble = max(-12.0, min(12.0, treble))
            
            # Find existing EQ effect or create new one
            eq_effect_id = await self._find_eq_effect(guild_id)
            
            eq_params = {
                'bass': bass,
                'mid': mid,
                'treble': treble
            }
            
            if eq_effect_id:
                # Update existing EQ
                success = await self.update_effect(guild_id, eq_effect_id, eq_params)
            else:
                # Add new EQ effect
                eq_effect_id = await self.add_effect(guild_id, EffectType.EQUALIZER, eq_params)
                success = bool(eq_effect_id)
            
            if success:
                # Update audio config
                await self._update_audio_config(guild_id, {
                    'eq_enabled': True,
                    'eq_bass': bass,
                    'eq_mid': mid,
                    'eq_treble': treble
                })
            
            logger.info(f"[{guild_id}]: Set EQ - Bass: {bass}, Mid: {mid}, Treble: {treble}")
            return success
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to set EQ: {e}")
            return False
    
    async def apply_eq_preset(self, guild_id: int, preset_name: str) -> bool:
        """
        Apply a predefined EQ preset.
        
        Args:
            guild_id: Discord guild ID
            preset_name: Name of the preset to apply
            
        Returns:
            True if preset was applied successfully
        """
        try:
            if preset_name not in self._eq_presets:
                logger.warning(f"[{guild_id}]: Unknown EQ preset: {preset_name}")
                return False
            
            preset = self._eq_presets[preset_name]
            success = await self.set_eq(guild_id, preset['bass'], preset['mid'], preset['treble'])
            
            if success:
                # Update preset in audio config
                await self._update_audio_config(guild_id, {'eq_preset': preset_name})
            
            logger.info(f"[{guild_id}]: Applied EQ preset: {preset_name}")
            return success
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to apply EQ preset {preset_name}: {e}")
            return False
    
    async def enable_crossfade(self, guild_id: int, duration: float) -> bool:
        """
        Enable crossfading with specified duration.
        
        Args:
            guild_id: Discord guild ID
            duration: Crossfade duration in seconds
            
        Returns:
            True if crossfade was enabled successfully
        """
        try:
            duration = max(0.1, min(10.0, duration))  # Limit to reasonable range
            
            crossfade_params = {
                'duration': duration,
                'curve': 'linear'  # Could be 'linear', 'exponential', 'logarithmic'
            }
            
            # Store crossfade state
            self._crossfade_state[guild_id] = {
                'enabled': True,
                'duration': duration,
                'current_fade': None
            }
            
            # Update audio config
            await self._update_audio_config(guild_id, {
                'crossfade_enabled': True,
                'crossfade_duration': duration
            })
            
            logger.info(f"[{guild_id}]: Enabled crossfade with {duration}s duration")
            return True
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to enable crossfade: {e}")
            return False
    
    async def enable_ducking(self, guild_id: int, level: float, sensitivity: float) -> bool:
        """
        Enable audio ducking for voice chat.
        
        Args:
            guild_id: Discord guild ID
            level: Ducking level (0.0 to 1.0)
            sensitivity: Ducking sensitivity (0.0 to 1.0)
            
        Returns:
            True if ducking was enabled successfully
        """
        try:
            level = max(0.0, min(1.0, level))
            sensitivity = max(0.0, min(1.0, sensitivity))
            
            ducking_params = {
                'level': level,
                'sensitivity': sensitivity,
                'attack_time': 0.1,  # 100ms attack
                'release_time': 0.5  # 500ms release
            }
            
            # Add ducking effect
            effect_id = await self.add_effect(guild_id, EffectType.DUCKING, ducking_params)
            
            if effect_id:
                # Update audio config
                await self._update_audio_config(guild_id, {
                    'ducking_enabled': True,
                    'ducking_level': level,
                    'ducking_sensitivity': sensitivity
                })
            
            logger.info(f"[{guild_id}]: Enabled ducking - Level: {level}, Sensitivity: {sensitivity}")
            return bool(effect_id)
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to enable ducking: {e}")
            return False
    
    async def get_available_presets(self) -> List[str]:
        """Get list of available EQ presets"""
        return list(self._eq_presets.keys())
    
    def process_audio_effects(self, guild_id: int, audio_data: bytes, 
                            config: AudioConfig) -> bytes:
        """
        Process audio data through the effects chain.
        
        Args:
            guild_id: Discord guild ID
            audio_data: Raw audio data
            config: Audio configuration
            
        Returns:
            Processed audio data
        """
        try:
            if not audio_data or guild_id not in self._effect_chains:
                return audio_data
            
            # Convert to numpy array for processing
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            processed_audio = audio_array.copy()
            
            # Apply each effect in the chain
            effects = self._effect_chains[guild_id]
            for effect in effects:
                if effect['enabled']:
                    processed_audio = self._apply_effect(effect, processed_audio, config)
            
            # Convert back to bytes
            processed_audio = np.clip(processed_audio, -32768, 32767)
            return processed_audio.astype(np.int16).tobytes()
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to process effects: {e}")
            return audio_data
    
    def _apply_effect(self, effect: Dict[str, Any], audio: np.ndarray, 
                     config: AudioConfig) -> np.ndarray:
        """Apply a single effect to audio data"""
        try:
            effect_type = effect['type']
            parameters = effect['parameters']
            
            if effect_type == EffectType.EQUALIZER:
                return self._apply_eq(audio, parameters)
            elif effect_type == EffectType.COMPRESSOR:
                return self._apply_compressor(audio, parameters)
            elif effect_type == EffectType.DUCKING:
                return self._apply_ducking(audio, parameters)
            else:
                # Unsupported effect type, return unchanged
                logger.debug(f"Unsupported effect type: {effect_type}")
                return audio
                
        except Exception as e:
            logger.error(f"Error applying effect {effect['type']}: {e}")
            return audio
    
    def _apply_eq(self, audio: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        """Apply 3-band EQ (simplified implementation)"""
        try:
            # This is a very basic EQ implementation
            # In a full implementation, this would use proper digital filters
            
            bass_gain = 10 ** (params.get('bass', 0.0) / 20.0)
            mid_gain = 10 ** (params.get('mid', 0.0) / 20.0) 
            treble_gain = 10 ** (params.get('treble', 0.0) / 20.0)
            
            # Simple frequency-based gain adjustment (placeholder)
            # Real implementation would use proper bandpass filters
            processed = audio * mid_gain  # Apply mid gain to all frequencies as base
            
            return processed
            
        except Exception as e:
            logger.error(f"Error in EQ processing: {e}")
            return audio
    
    def _apply_compressor(self, audio: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        """Apply dynamic range compression"""
        try:
            threshold = params.get('threshold', 0.7)
            ratio = params.get('ratio', 0.5)
            
            # Simple compressor implementation
            abs_audio = np.abs(audio)
            gain_reduction = np.ones_like(abs_audio)
            
            over_threshold = abs_audio > threshold
            if np.any(over_threshold):
                excess = abs_audio[over_threshold] - threshold
                compressed_excess = excess * (1.0 - ratio)
                gain_reduction[over_threshold] = (threshold + compressed_excess) / abs_audio[over_threshold]
            
            return audio * gain_reduction
            
        except Exception as e:
            logger.error(f"Error in compressor processing: {e}")
            return audio
    
    def _apply_ducking(self, audio: np.ndarray, params: Dict[str, Any]) -> np.ndarray:
        """Apply ducking effect (placeholder - would need voice detection)"""
        try:
            # Placeholder ducking implementation
            # Real implementation would detect voice activity and duck accordingly
            ducking_level = params.get('level', 0.3)
            
            # For now, just apply a constant reduction when ducking is enabled
            # Real implementation would be much more sophisticated
            return audio * (1.0 - ducking_level * 0.5)
            
        except Exception as e:
            logger.error(f"Error in ducking processing: {e}")
            return audio
    
    async def _find_eq_effect(self, guild_id: int) -> Optional[str]:
        """Find existing EQ effect in the chain"""
        if guild_id not in self._effect_chains:
            return None
        
        for effect in self._effect_chains[guild_id]:
            if effect['type'] == EffectType.EQUALIZER:
                return effect['id']
        
        return None
    
    async def _update_audio_config(self, guild_id: int, updates: Dict[str, Any]) -> None:
        """Update audio configuration for a guild"""
        try:
            guild_state = self.state_manager.get_guild_state(guild_id, create_if_missing=True)
            if guild_state and hasattr(guild_state, 'audio_config') and guild_state.audio_config:
                for key, value in updates.items():
                    setattr(guild_state.audio_config, key, value)
                logger.debug(f"[{guild_id}]: Updated audio config: {list(updates.keys())}")
                
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to update audio config: {e}")
    
    def get_effects_stats(self, guild_id: int) -> Dict[str, Any]:
        """Get effects statistics for a guild"""
        try:
            effects = self._effect_chains.get(guild_id, [])
            
            effect_counts = {}
            for effect in effects:
                effect_type = effect['type'].value
                effect_counts[effect_type] = effect_counts.get(effect_type, 0) + 1
            
            return {
                'total_effects': len(effects),
                'effect_counts': effect_counts,
                'crossfade_enabled': guild_id in self._crossfade_state,
                'available_presets': len(self._eq_presets),
                'effects_list': [
                    {
                        'id': effect['id'],
                        'type': effect['type'].value,
                        'enabled': effect['enabled'],
                        'created_at': effect['created_at'].isoformat()
                    }
                    for effect in effects
                ]
            }
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Failed to get effects stats: {e}")
            return {}
