"""
Advanced Audio Processing Commands

Discord slash commands for the new scipy-based audio processing system.
Provides EQ, spectral analysis, and filter controls.
"""

import logging
import io
import numpy as np
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List

from core import ServiceRegistry
from audio import (
    AdvancedAudioProcessor, ParametricEqualizer, EQPresets,
    FrequencyBand, ProcessingQuality, FilterType, FilterResponse,
    FilterSpecification, ScipyFilterDesigner
)

logger = logging.getLogger('services.advanced_audio_commands')

class AdvancedAudioCommands(commands.Cog):
    """
    Advanced audio processing commands using scipy.
    
    Provides parametric EQ, spectral analysis, and filter design capabilities.
    """
    
    def __init__(self, bot: commands.AutoShardedBot, service_registry: ServiceRegistry):
        self.bot = bot
        self.service_registry = service_registry
        
        # Initialize advanced audio processor
        self.audio_processor = AdvancedAudioProcessor()
        
        logger.info("AdvancedAudioCommands initialized")
    
    @app_commands.command(name="eq_preset", description="Apply an EQ preset")
    @app_commands.describe(
        preset="EQ preset to apply",
        quality="Processing quality level"
    )
    @app_commands.choices(preset=[
        app_commands.Choice(name="Flat (No EQ)", value="flat"),
        app_commands.Choice(name="Bass Boost", value="bass_boost"),
        app_commands.Choice(name="Vocal Enhance", value="vocal_enhance"),
        app_commands.Choice(name="Classical", value="classical"),
        app_commands.Choice(name="Rock", value="rock"),
        app_commands.Choice(name="Electronic", value="electronic")
    ])
    @app_commands.choices(quality=[
        app_commands.Choice(name="Low (Fast)", value="low"),
        app_commands.Choice(name="Medium", value="medium"),
        app_commands.Choice(name="High", value="high"),
        app_commands.Choice(name="Ultra (Slow)", value="ultra")
    ])
    async def eq_preset(
        self, 
        interaction: discord.Interaction, 
        preset: str,
        quality: Optional[str] = "high"
    ):
        """Apply an EQ preset to the current guild"""
        try:
            await interaction.response.defer()
            
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send("❌ This command can only be used in a server.")
                return
            
            # Set processing quality
            quality_map = {
                "low": ProcessingQuality.LOW,
                "medium": ProcessingQuality.MEDIUM,
                "high": ProcessingQuality.HIGH,
                "ultra": ProcessingQuality.ULTRA
            }
            quality_level = quality_map.get(quality, ProcessingQuality.HIGH)
            self.audio_processor.set_quality(guild_id, quality_level)
            
            # Apply EQ preset
            success = self.audio_processor.apply_eq_preset(guild_id, preset)
            
            if success:
                # Get preset info
                preset_bands = EQPresets.get_preset(preset)
                band_count = len(preset_bands)
                
                embed = discord.Embed(
                    title="🎛️ EQ Preset Applied",
                    description=f"Applied **{preset.replace('_', ' ').title()}** preset",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Settings",
                    value=f"• Bands: {band_count}\n• Quality: {quality.title()}",
                    inline=True
                )
                
                if band_count > 0:
                    band_info = []
                    for i, band in enumerate(preset_bands[:3]):  # Show first 3 bands
                        band_info.append(
                            f"{band.center_frequency:.0f} Hz: {band.gain_db:+.1f} dB"
                        )
                    if len(preset_bands) > 3:
                        band_info.append(f"... and {len(preset_bands) - 3} more")
                    
                    embed.add_field(
                        name="EQ Bands",
                        value="\n".join(band_info),
                        inline=True
                    )
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"❌ Failed to apply EQ preset '{preset}'. Check logs for details."
                )
                
        except Exception as e:
            logger.error(f"EQ preset command failed: {e}")
            await interaction.followup.send(f"❌ Error applying EQ preset: {e}")
    
    @app_commands.command(name="eq_band", description="Add or modify an EQ band")
    @app_commands.describe(
        frequency="Center frequency in Hz (20-20000)",
        gain="Gain in dB (-12 to +12)",
        q_factor="Q factor (0.1 to 10.0, higher = narrower)"
    )
    async def eq_band(
        self,
        interaction: discord.Interaction,
        frequency: float,
        gain: float,
        q_factor: Optional[float] = 1.0
    ):
        """Add or modify an EQ band"""
        try:
            await interaction.response.defer()
            
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send("❌ This command can only be used in a server.")
                return
            
            # Validate parameters
            if not (20 <= frequency <= 20000):
                await interaction.followup.send("❌ Frequency must be between 20 and 20000 Hz.")
                return
            
            if not (-12 <= gain <= 12):
                await interaction.followup.send("❌ Gain must be between -12 and +12 dB.")
                return
            
            if not (0.1 <= q_factor <= 10.0):
                await interaction.followup.send("❌ Q factor must be between 0.1 and 10.0.")
                return
            
            # Create frequency band
            band = FrequencyBand(
                center_frequency=frequency,
                gain_db=gain,
                q_factor=q_factor
            )
            
            # Add band to equalizer
            equalizer = self.audio_processor.get_equalizer(guild_id)
            band_id = equalizer.add_band(band)
            
            embed = discord.Embed(
                title="🎛️ EQ Band Added",
                description=f"Added EQ band #{band_id}",
                color=0x00ff00
            )
            embed.add_field(
                name="Band Settings",
                value=f"• Frequency: {frequency:.0f} Hz\n• Gain: {gain:+.1f} dB\n• Q Factor: {q_factor:.1f}",
                inline=True
            )
            embed.add_field(
                name="Frequency Range",
                value=f"{band.low_frequency:.0f} - {band.high_frequency:.0f} Hz",
                inline=True
            )
            
            total_bands = equalizer.get_band_count()
            embed.add_field(
                name="Total Bands",
                value=f"{total_bands} active",
                inline=True
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"EQ band command failed: {e}")
            await interaction.followup.send(f"❌ Error adding EQ band: {e}")
    
    @app_commands.command(name="eq_clear", description="Clear all EQ bands")
    async def eq_clear(self, interaction: discord.Interaction):
        """Clear all EQ bands (flat response)"""
        try:
            await interaction.response.defer()
            
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send("❌ This command can only be used in a server.")
                return
            
            equalizer = self.audio_processor.get_equalizer(guild_id)
            band_count = equalizer.get_band_count()
            equalizer.reset()
            
            embed = discord.Embed(
                title="🎛️ EQ Cleared",
                description=f"Removed {band_count} EQ bands",
                color=0xff9900
            )
            embed.add_field(
                name="Status",
                value="EQ is now flat (no processing)",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"EQ clear command failed: {e}")
            await interaction.followup.send(f"❌ Error clearing EQ: {e}")
    
    @app_commands.command(name="eq_status", description="Show current EQ settings")
    async def eq_status(self, interaction: discord.Interaction):
        """Show current EQ configuration"""
        try:
            await interaction.response.defer()
            
            guild_id = interaction.guild_id
            if not guild_id:
                await interaction.followup.send("❌ This command can only be used in a server.")
                return
            
            # Get processing stats
            stats = self.audio_processor.get_processing_stats(guild_id)
            
            embed = discord.Embed(
                title="🎛️ EQ Status",
                description="Current equalizer configuration",
                color=0x0099ff
            )
            
            # Basic info
            embed.add_field(
                name="Configuration",
                value=(
                    f"• EQ Bands: {stats.get('eq_band_count', 0)}\n"
                    f"• Quality: {stats.get('quality_setting', 'high').title()}\n"
                    f"• Sample Rate: {stats.get('sample_rate', 48000)} Hz"
                ),
                inline=True
            )
            
            # Performance stats
            eq_stats = stats.get('equalizer_stats', {})
            if eq_stats:
                avg_time = eq_stats.get('average_processing_time_ms', 0)
                embed.add_field(
                    name="Performance",
                    value=(
                        f"• Processed: {eq_stats.get('processing_count', 0)} buffers\n"
                        f"• Avg Time: {avg_time:.2f} ms"
                    ),
                    inline=True
                )
            
            # Noise reduction
            has_noise_profile = stats.get('has_noise_profile', False)
            embed.add_field(
                name="Noise Reduction",
                value="✅ Enabled" if has_noise_profile else "❌ Disabled",
                inline=True
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"EQ status command failed: {e}")
            await interaction.followup.send(f"❌ Error getting EQ status: {e}")
    
    @app_commands.command(name="audio_analyze", description="Analyze audio spectrum (demo)")
    async def audio_analyze(self, interaction: discord.Interaction):
        """Demonstrate spectral analysis with synthetic audio"""
        try:
            await interaction.response.defer()
            
            # Generate demo audio signal
            sample_rate = 48000
            duration = 1.0  # 1 second
            t = np.linspace(0, duration, int(sample_rate * duration))
            
            # Create a complex signal with multiple frequency components
            signal = (
                0.5 * np.sin(2 * np.pi * 440 * t) +      # A4 note
                0.3 * np.sin(2 * np.pi * 880 * t) +      # A5 note  
                0.2 * np.sin(2 * np.pi * 1760 * t) +     # A6 note
                0.1 * np.random.normal(0, 1, len(t))      # Noise
            )
            
            # Analyze spectrum
            analysis = self.audio_processor.analyze_audio_spectrum(signal)
            
            if 'error' in analysis:
                await interaction.followup.send(f"❌ Analysis failed: {analysis['error']}")
                return
            
            embed = discord.Embed(
                title="🔊 Audio Spectrum Analysis",
                description="Analysis of demo audio signal",
                color=0x9932cc
            )
            
            # Basic analysis info
            embed.add_field(
                name="Signal Properties",
                value=(
                    f"• Sample Rate: {analysis['sample_rate']} Hz\n"
                    f"• Window Size: {analysis['window_size']}\n"
                    f"• Frequency Resolution: {analysis['frequency_resolution']:.1f} Hz"
                ),
                inline=True
            )
            
            # Spectral features
            embed.add_field(
                name="Spectral Features",
                value=(
                    f"• Centroid: {analysis['spectral_centroid_hz']:.0f} Hz\n"
                    f"• Rolloff: {analysis['spectral_rolloff_hz']:.0f} Hz\n"
                    f"• Bandwidth: {analysis['spectral_bandwidth_hz']:.0f} Hz"
                ),
                inline=True
            )
            
            # Peak information
            peaks = analysis.get('peak_frequencies', [])
            if peaks:
                peak_info = []
                for i, freq in enumerate(peaks[:5]):  # Show first 5 peaks
                    peak_info.append(f"{freq:.0f} Hz")
                
                embed.add_field(
                    name="Peak Frequencies",
                    value="\n".join(peak_info),
                    inline=True
                )
            
            # Magnitude range
            mag_range = analysis.get('magnitude_db_range', {})
            if mag_range:
                embed.add_field(
                    name="Magnitude Range (dB)",
                    value=(
                        f"• Min: {mag_range.get('min', 0):.1f}\n"
                        f"• Max: {mag_range.get('max', 0):.1f}\n"
                        f"• Mean: {mag_range.get('mean', 0):.1f}"
                    ),
                    inline=True
                )
            
            embed.set_footer(text="This analysis used a synthetic demo signal with 440Hz, 880Hz, and 1760Hz tones plus noise.")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Audio analyze command failed: {e}")
            await interaction.followup.send(f"❌ Error analyzing audio: {e}")
    
    @app_commands.command(name="filter_design", description="Design and test a digital filter")
    @app_commands.describe(
        filter_type="Type of filter to design",
        response="Frequency response type",
        frequency="Cutoff frequency in Hz",
        order="Filter order (1-10)"
    )
    @app_commands.choices(filter_type=[
        app_commands.Choice(name="Butterworth", value="butterworth"),
        app_commands.Choice(name="Chebyshev I", value="chebyshev_i"),
        app_commands.Choice(name="Chebyshev II", value="chebyshev_ii"),
        app_commands.Choice(name="Elliptic", value="elliptic"),
        app_commands.Choice(name="Bessel", value="bessel"),
        app_commands.Choice(name="FIR", value="fir")
    ])
    @app_commands.choices(response=[
        app_commands.Choice(name="Low Pass", value="lowpass"),
        app_commands.Choice(name="High Pass", value="highpass"),
        app_commands.Choice(name="Band Pass", value="bandpass"),
        app_commands.Choice(name="Band Stop", value="bandstop")
    ])
    async def filter_design(
        self,
        interaction: discord.Interaction,
        filter_type: str,
        response: str,
        frequency: float,
        order: Optional[int] = 4
    ):
        """Design a digital filter and show its properties"""
        try:
            await interaction.response.defer()
            
            # Validate parameters
            if not (20 <= frequency <= 20000):
                await interaction.followup.send("❌ Frequency must be between 20 and 20000 Hz.")
                return
            
            if not (1 <= order <= 10):
                await interaction.followup.send("❌ Filter order must be between 1 and 10.")
                return
            
            # Create filter specification
            filter_type_map = {
                "butterworth": FilterType.BUTTERWORTH,
                "chebyshev_i": FilterType.CHEBYSHEV_I,
                "chebyshev_ii": FilterType.CHEBYSHEV_II,
                "elliptic": FilterType.ELLIPTIC,
                "bessel": FilterType.BESSEL,
                "fir": FilterType.FIR
            }
            
            response_map = {
                "lowpass": FilterResponse.LOWPASS,
                "highpass": FilterResponse.HIGHPASS,
                "bandpass": FilterResponse.BANDPASS,
                "bandstop": FilterResponse.BANDSTOP
            }
            
            spec = FilterSpecification(
                filter_type=filter_type_map[filter_type],
                response_type=response_map[response],
                cutoff_frequencies=(frequency,),
                sample_rate=48000,
                order=order,
                ripple_db=0.5,
                attenuation_db=60.0
            )
            
            # Design filter
            designer = ScipyFilterDesigner()
            coefficients = designer.design_filter(spec)
            
            embed = discord.Embed(
                title="🔧 Filter Design",
                description=f"{filter_type.replace('_', ' ').title()} {response.replace('_', ' ').title()} Filter",
                color=0xff6600
            )
            
            embed.add_field(
                name="Specifications",
                value=(
                    f"• Type: {filter_type.replace('_', ' ').title()}\n"
                    f"• Response: {response.replace('_', ' ').title()}\n"
                    f"• Cutoff: {frequency:.0f} Hz\n"
                    f"• Order: {order}"
                ),
                inline=True
            )
            
            embed.add_field(
                name="Coefficients",
                value=(
                    f"• Numerator: {len(coefficients.numerator)} coeffs\n"
                    f"• Denominator: {len(coefficients.denominator)} coeffs\n"
                    f"• Gain: {coefficients.gain:.3f}"
                ),
                inline=True
            )
            
            # Show first few coefficients
            num_preview = coefficients.numerator[:3]
            den_preview = coefficients.denominator[:3]
            
            embed.add_field(
                name="Coefficient Preview",
                value=(
                    f"• Num: [{', '.join(f'{c:.3f}' for c in num_preview)}...]\n"
                    f"• Den: [{', '.join(f'{c:.3f}' for c in den_preview)}...]"
                ),
                inline=True
            )
            
            embed.set_footer(text="Filter designed successfully! Coefficients can be used for real-time processing.")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Filter design command failed: {e}")
            await interaction.followup.send(f"❌ Error designing filter: {e}")

async def setup(bot: commands.AutoShardedBot, service_registry: ServiceRegistry):
    """Setup function for the advanced audio commands cog"""
    await bot.add_cog(AdvancedAudioCommands(bot, service_registry))
