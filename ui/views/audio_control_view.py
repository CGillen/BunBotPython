"""
Audio Control Dashboard View

Real-time audio controls with visual feedback for Discord users.
Provides intuitive interface for volume, EQ, and audio metrics.
"""

import logging
from typing import Dict, Any, Optional, List
import asyncio
from datetime import datetime

import discord
from discord.ext import commands

from core import ServiceRegistry
from ui.views.base_view import BaseView
from audio import IVolumeManager, IEffectsChain, IAudioProcessor

logger = logging.getLogger('ui.views.audio_control')


class AudioControlView(BaseView):
    """
    Interactive audio control dashboard with real-time feedback.
    
    Features:
    - Volume slider with live preview
    - 3-band EQ controls (Bass/Mid/Treble)
    - Audio metrics display (RMS, Peak levels)
    - EQ preset selection
    - Audio processing status indicators
    """
    
    def __init__(self, service_registry: ServiceRegistry, guild_id: int):
        super().__init__(timeout=300)  # 5 minute timeout
        
        self.service_registry = service_registry
        self.guild_id = guild_id
        
        # Get audio services
        self.volume_manager = service_registry.get_optional(IVolumeManager)
        self.effects_chain = service_registry.get_optional(IEffectsChain)
        self.audio_processor = service_registry.get_optional(IAudioProcessor)
        
        # Current audio state
        self.current_volume = 0.8
        self.current_eq = {'bass': 0.0, 'mid': 0.0, 'treble': 0.0}
        self.audio_metrics = {'rms_db': -20, 'peak_db': -6, 'lufs': -18}
        self.is_processing = False
        
        # UI Components
        self.eq_controls: Dict[str, discord.ui.Button] = {}
        
        # EQ Presets
        self.eq_presets = {
            'flat': {'bass': 0.0, 'mid': 0.0, 'treble': 0.0},
            'bass_boost': {'bass': 0.3, 'mid': 0.0, 'treble': 0.0},
            'vocal': {'bass': -0.1, 'mid': 0.2, 'treble': 0.1},
            'rock': {'bass': 0.2, 'mid': 0.0, 'treble': 0.2},
            'jazz': {'bass': 0.1, 'mid': 0.1, 'treble': 0.0},
            'electronic': {'bass': 0.3, 'mid': -0.1, 'treble': 0.2},
            'classical': {'bass': 0.0, 'mid': 0.1, 'treble': 0.1},
            'pop': {'bass': 0.1, 'mid': 0.0, 'treble': 0.1},
            'broadcast': {'bass': -0.1, 'mid': 0.3, 'treble': 0.0}
        }
        
        # Initialize components
        self._setup_components()
        
        logger.info(f"AudioControlView initialized for guild {guild_id}")
    
    def _setup_components(self):
        """Set up all UI components for the audio control dashboard"""
        
        # Volume Control Section
        self.volume_slider = VolumeSlider(
            label="Master Volume",
            min_value=0.0,
            max_value=1.0,
            current_value=self.current_volume,
            callback=self._on_volume_change
        )
        
        # EQ Control Buttons
        eq_bands = ['bass', 'mid', 'treble']
        for band in eq_bands:
            self.eq_controls[band] = Button(
                label=f"{band.title()}: {self.current_eq[band]:+.1f}",
                style=discord.ButtonStyle.secondary,
                callback=self._on_eq_adjust,
                custom_id=f"eq_{band}"
            )
        
        # EQ Preset Buttons
        preset_names = list(self.eq_presets.keys())[:9]  # Limit to 9 for Discord UI
        for i, preset_name in enumerate(preset_names):
            preset_button = Button(
                label=preset_name.title(),
                style=discord.ButtonStyle.primary,
                callback=self._on_preset_select,
                custom_id=f"preset_{preset_name}",
                row=2 + (i // 3)  # Arrange in rows of 3
            )
            self.add_item(preset_button)
        
        # Audio Metrics Displays
        self.metrics_displays['rms'] = ProgressBar(
            label="RMS Level",
            min_value=-60,
            max_value=0,
            current_value=self.audio_metrics['rms_db'],
            color_good=-20,
            color_warning=-12,
            color_danger=-6
        )
        
        self.metrics_displays['peak'] = ProgressBar(
            label="Peak Level",
            min_value=-60,
            max_value=0,
            current_value=self.audio_metrics['peak_db'],
            color_good=-12,
            color_warning=-6,
            color_danger=-3
        )
        
        # Status Indicators
        self.status_indicators['processing'] = StatusIndicator(
            label="Audio Processing",
            status=self.is_processing
        )
        
        self.status_indicators['normalization'] = StatusIndicator(
            label="Normalization",
            status=True  # Always enabled
        )
        
        self.status_indicators['compression'] = StatusIndicator(
            label="Compression",
            status=True  # Always enabled
        )
        
        # Add primary controls to view
        self.add_item(self.volume_slider)
        for band_button in self.eq_controls.values():
            self.add_item(band_button)
        
        # Add utility buttons
        refresh_button = Button(
            label="🔄 Refresh",
            style=discord.ButtonStyle.secondary,
            callback=self._on_refresh,
            custom_id="refresh_audio",
            row=4
        )
        
        reset_button = Button(
            label="🔧 Reset",
            style=discord.ButtonStyle.danger,
            callback=self._on_reset,
            custom_id="reset_audio",
            row=4
        )
        
        close_button = Button(
            label="❌ Close",
            style=discord.ButtonStyle.secondary,
            callback=self._on_close,
            custom_id="close_dashboard",
            row=4
        )
        
        self.add_item(refresh_button)
        self.add_item(reset_button)
        self.add_item(close_button)
    
    async def _on_volume_change(self, interaction: discord.Interaction, volume: float):
        """Handle volume slider changes"""
        try:
            await interaction.response.defer()
            
            if self.volume_manager:
                success = await self.volume_manager.set_master_volume(self.guild_id, volume)
                if success:
                    self.current_volume = volume
                    await self._update_audio_metrics()
                    await self._update_display(interaction)
                    
                    await interaction.followup.send(
                        f"🔊 Volume set to {int(volume * 100)}%",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ Failed to set volume",
                        ephemeral=True
                    )
            else:
                await interaction.followup.send(
                    "❌ Volume control not available",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error changing volume: {e}")
            await interaction.followup.send(
                "❌ Error adjusting volume",
                ephemeral=True
            )
    
    async def _on_eq_adjust(self, interaction: discord.Interaction):
        """Handle EQ band adjustment"""
        try:
            band = interaction.data['custom_id'].replace('eq_', '')
            
            # Show EQ adjustment modal
            from ui.components.modal import EQAdjustModal
            modal = EQAdjustModal(
                band=band,
                current_value=self.current_eq[band],
                callback=self._apply_eq_change
            )
            
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            logger.error(f"Error in EQ adjust: {e}")
            await interaction.response.send_message(
                "❌ Error adjusting EQ",
                ephemeral=True
            )
    
    async def _apply_eq_change(self, band: str, value: float):
        """Apply EQ change to audio system"""
        try:
            if self.effects_chain:
                # Update EQ settings
                eq_settings = self.current_eq.copy()
                eq_settings[band] = max(-1.0, min(1.0, value))  # Clamp to valid range
                
                success = await self.effects_chain.set_equalizer_settings(
                    self.guild_id, eq_settings
                )
                
                if success:
                    self.current_eq = eq_settings
                    # Update button label
                    self.eq_controls[band].label = f"{band.title()}: {value:+.1f}"
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error applying EQ change: {e}")
            return False
    
    async def _on_preset_select(self, interaction: discord.Interaction):
        """Handle EQ preset selection"""
        try:
            await interaction.response.defer()
            
            preset_name = interaction.data['custom_id'].replace('preset_', '')
            preset_eq = self.eq_presets.get(preset_name)
            
            if not preset_eq:
                await interaction.followup.send(
                    "❌ Unknown preset",
                    ephemeral=True
                )
                return
            
            if self.effects_chain:
                success = await self.effects_chain.set_equalizer_settings(
                    self.guild_id, preset_eq
                )
                
                if success:
                    self.current_eq = preset_eq.copy()
                    
                    # Update EQ button labels
                    for band, value in preset_eq.items():
                        if band in self.eq_controls:
                            self.eq_controls[band].label = f"{band.title()}: {value:+.1f}"
                    
                    await self._update_display(interaction)
                    
                    await interaction.followup.send(
                        f"🎛️ Applied {preset_name.title()} EQ preset",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ Failed to apply EQ preset",
                        ephemeral=True
                    )
            else:
                await interaction.followup.send(
                    "❌ EQ control not available",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.error(f"Error applying preset: {e}")
            await interaction.followup.send(
                "❌ Error applying preset",
                ephemeral=True
            )
    
    async def _on_refresh(self, interaction: discord.Interaction):
        """Handle refresh button click"""
        try:
            await interaction.response.defer()
            
            # Update current audio state from services
            await self._update_audio_state()
            await self._update_display(interaction)
            
            await interaction.followup.send(
                "🔄 Audio dashboard refreshed",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error refreshing dashboard: {e}")
            await interaction.followup.send(
                "❌ Error refreshing dashboard",
                ephemeral=True
            )
    
    async def _on_reset(self, interaction: discord.Interaction):
        """Handle reset button click"""
        try:
            await interaction.response.defer()
            
            # Reset to default values
            if self.volume_manager:
                await self.volume_manager.set_master_volume(self.guild_id, 0.8)
            
            if self.effects_chain:
                default_eq = {'bass': 0.0, 'mid': 0.0, 'treble': 0.0}
                await self.effects_chain.set_equalizer_settings(self.guild_id, default_eq)
                self.current_eq = default_eq
            
            self.current_volume = 0.8
            
            # Update button labels
            for band, value in self.current_eq.items():
                if band in self.eq_controls:
                    self.eq_controls[band].label = f"{band.title()}: {value:+.1f}"
            
            await self._update_display(interaction)
            
            await interaction.followup.send(
                "🔧 Audio settings reset to defaults",
                ephemeral=True
            )
            
        except Exception as e:
            logger.error(f"Error resetting audio: {e}")
            await interaction.followup.send(
                "❌ Error resetting audio settings",
                ephemeral=True
            )
    
    async def _on_close(self, interaction: discord.Interaction):
        """Handle close button click"""
        try:
            await interaction.response.defer()
            
            # Disable all components
            for item in self.children:
                item.disabled = True
            
            await interaction.edit_original_response(
                content="🎛️ Audio Control Dashboard closed",
                view=self
            )
            
            self.stop()
            
        except Exception as e:
            logger.error(f"Error closing dashboard: {e}")
            await interaction.followup.send(
                "❌ Error closing dashboard",
                ephemeral=True
            )
    
    async def _update_audio_state(self):
        """Update current audio state from services"""
        try:
            if self.volume_manager:
                self.current_volume = await self.volume_manager.get_master_volume(self.guild_id)
            
            if self.effects_chain:
                eq_settings = await self.effects_chain.get_equalizer_settings(self.guild_id)
                if eq_settings:
                    self.current_eq = eq_settings
            
            await self._update_audio_metrics()
            
        except Exception as e:
            logger.error(f"Error updating audio state: {e}")
    
    async def _update_audio_metrics(self):
        """Update audio metrics from processor"""
        try:
            if self.audio_processor:
                metrics = await self.audio_processor.get_audio_metrics(self.guild_id)
                if metrics:
                    self.audio_metrics.update(metrics)
                    self.is_processing = metrics.get('is_processing', False)
            
        except Exception as e:
            logger.error(f"Error updating audio metrics: {e}")
    
    async def _update_display(self, interaction: discord.Interaction):
        """Update the dashboard display"""
        try:
            embed = self._create_dashboard_embed()
            await interaction.edit_original_response(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"Error updating display: {e}")
    
    def _create_dashboard_embed(self) -> discord.Embed:
        """Create the main dashboard embed"""
        embed = discord.Embed(
            title="🎛️ Audio Control Dashboard",
            description="Real-time audio controls and metrics",
            color=0x00ff88,
            timestamp=datetime.now()
        )
        
        # Volume Section
        volume_bar = self._create_progress_bar(self.current_volume, 1.0, 20)
        embed.add_field(
            name="🔊 Master Volume",
            value=f"{volume_bar} {int(self.current_volume * 100)}%",
            inline=False
        )
        
        # EQ Section
        eq_display = ""
        for band, value in self.current_eq.items():
            bar = self._create_eq_bar(value)
            eq_display += f"**{band.title()}:** {bar} {value:+.1f}\n"
        
        embed.add_field(
            name="🎚️ Equalizer",
            value=eq_display,
            inline=True
        )
        
        # Audio Metrics
        metrics_display = ""
        rms_bar = self._create_level_bar(self.audio_metrics['rms_db'], -60, 0)
        peak_bar = self._create_level_bar(self.audio_metrics['peak_db'], -60, 0)
        
        metrics_display += f"**RMS:** {rms_bar} {self.audio_metrics['rms_db']:.1f} dB\n"
        metrics_display += f"**Peak:** {peak_bar} {self.audio_metrics['peak_db']:.1f} dB\n"
        metrics_display += f"**LUFS:** {self.audio_metrics['lufs']:.1f}\n"
        
        embed.add_field(
            name="📊 Audio Metrics",
            value=metrics_display,
            inline=True
        )
        
        # Status Indicators
        status_display = ""
        for name, indicator in self.status_indicators.items():
            status_icon = "🟢" if indicator.status else "🔴"
            status_display += f"{status_icon} {indicator.label}\n"
        
        embed.add_field(
            name="⚡ Processing Status",
            value=status_display,
            inline=False
        )
        
        # Footer with instructions
        embed.set_footer(text="Use buttons below to adjust settings • Auto-refresh every 30s")
        
        return embed
    
    def _create_progress_bar(self, value: float, max_value: float, length: int = 20) -> str:
        """Create a text-based progress bar"""
        filled_length = int(length * (value / max_value))
        bar = "█" * filled_length + "░" * (length - filled_length)
        return f"`{bar}`"
    
    def _create_eq_bar(self, value: float, length: int = 10) -> str:
        """Create EQ visualization bar"""
        center = length // 2
        if value > 0:
            filled = int(value * center)
            bar = "░" * center + "█" * filled + "░" * (center - filled)
        else:
            filled = int(abs(value) * center)
            bar = "░" * (center - filled) + "█" * filled + "░" * center
        
        return f"`{bar}`"
    
    def _create_level_bar(self, db_value: float, min_db: float, max_db: float, length: int = 15) -> str:
        """Create audio level bar with color coding"""
        normalized = (db_value - min_db) / (max_db - min_db)
        filled_length = int(length * max(0, min(1, normalized)))
        
        # Color coding based on level
        if db_value > -6:
            bar_char = "🟥"  # Red - too loud
        elif db_value > -12:
            bar_char = "🟨"  # Yellow - warning
        else:
            bar_char = "🟩"  # Green - good level
        
        empty_char = "⬜"
        bar = bar_char * filled_length + empty_char * (length - filled_length)
        return bar
    
    async def refresh_dashboard(self):
        """Auto-refresh the dashboard (called by background task)"""
        try:
            await self._update_audio_state()
            # Note: We don't update the display here to avoid conflicts
            # The display will update on next user interaction
            
        except Exception as e:
            logger.error(f"Error in auto-refresh: {e}")
    
    async def on_timeout(self):
        """Handle view timeout"""
        try:
            # Disable all components
            for item in self.children:
                item.disabled = True
            
            # Try to edit the message if possible
            if hasattr(self, 'message') and self.message:
                try:
                    await self.message.edit(
                        content="⏰ Audio Control Dashboard timed out",
                        view=self
                    )
                except:
                    pass  # Message might be deleted
            
        except Exception as e:
            logger.error(f"Error handling timeout: {e}")


async def create_audio_dashboard(service_registry: ServiceRegistry, 
                                guild_id: int) -> AudioControlView:
    """
    Factory function to create an audio control dashboard.
    
    Args:
        service_registry: Service registry instance
        guild_id: Discord guild ID
        
    Returns:
        Configured AudioControlView instance
    """
    dashboard = AudioControlView(service_registry, guild_id)
    await dashboard._update_audio_state()
    return dashboard
