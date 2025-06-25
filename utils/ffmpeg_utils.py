"""
FFmpeg Utility Functions for BunBot

Provides auto-detection and configuration for FFmpeg executable
to ensure BunBot works out-of-the-box without system configuration.
"""

import os
import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger('utils.ffmpeg_utils')

class FFmpegManager:
    """
    Manages FFmpeg detection and configuration for cross-platform compatibility.
    
    Automatically detects local FFmpeg installations and provides fallback
    to system PATH for maximum compatibility.
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize FFmpeg manager.
        
        Args:
            project_root: Optional project root path, defaults to current working directory
        """
        self.project_root = project_root or Path.cwd()
        self._ffmpeg_path: Optional[str] = None
        self._detection_attempted = False
        
        logger.debug(f"FFmpegManager initialized with project root: {self.project_root}")
    
    def get_ffmpeg_executable(self) -> Optional[str]:
        """
        Get the path to FFmpeg executable.
        
        Returns:
            Path to FFmpeg executable or None if not found
        """
        if not self._detection_attempted:
            self._detect_ffmpeg()
            self._detection_attempted = True
        
        return self._ffmpeg_path
    
    def _detect_ffmpeg(self) -> None:
        """Detect FFmpeg executable using multiple strategies"""
        try:
            # Strategy 1: Local project FFmpeg (highest priority)
            local_path = self._find_local_ffmpeg()
            if local_path:
                self._ffmpeg_path = local_path
                logger.info(f"Found local FFmpeg: {local_path}")
                return
            
            # Strategy 2: System PATH (fallback)
            system_path = self._find_system_ffmpeg()
            if system_path:
                self._ffmpeg_path = system_path
                logger.info(f"Found system FFmpeg: {system_path}")
                return
            
            # Strategy 3: Common installation paths (last resort)
            common_path = self._find_common_ffmpeg()
            if common_path:
                self._ffmpeg_path = common_path
                logger.info(f"Found FFmpeg in common location: {common_path}")
                return
            
            logger.warning("FFmpeg not found in any location")
            
        except Exception as e:
            logger.error(f"Error during FFmpeg detection: {e}")
    
    def _find_local_ffmpeg(self) -> Optional[str]:
        """Find FFmpeg in local project directory"""
        try:
            # Common local paths to check
            local_paths = [
                # Windows
                self.project_root / "ffmpeg-7.1.1-essentials_build" / "bin" / "ffmpeg.exe",
                self.project_root / "ffmpeg" / "bin" / "ffmpeg.exe",
                self.project_root / "bin" / "ffmpeg.exe",
                self.project_root / "ffmpeg.exe",
                
                # Linux/Mac
                self.project_root / "ffmpeg-7.1.1-essentials_build" / "bin" / "ffmpeg",
                self.project_root / "ffmpeg" / "bin" / "ffmpeg",
                self.project_root / "bin" / "ffmpeg",
                self.project_root / "ffmpeg",
            ]
            
            for path in local_paths:
                if path.exists() and path.is_file():
                    # Verify it's executable
                    if self._verify_ffmpeg_executable(str(path)):
                        return str(path.resolve())
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding local FFmpeg: {e}")
            return None
    
    def _find_system_ffmpeg(self) -> Optional[str]:
        """Find FFmpeg in system PATH"""
        try:
            # Use shutil.which for cross-platform PATH search
            ffmpeg_path = shutil.which("ffmpeg")
            
            if ffmpeg_path and self._verify_ffmpeg_executable(ffmpeg_path):
                return ffmpeg_path
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding system FFmpeg: {e}")
            return None
    
    def _find_common_ffmpeg(self) -> Optional[str]:
        """Find FFmpeg in common installation locations"""
        try:
            # Windows common paths
            if os.name == 'nt':
                common_paths = [
                    "C:\\ffmpeg\\bin\\ffmpeg.exe",
                    "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
                    "C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe",
                ]
            else:
                # Linux/Mac common paths
                common_paths = [
                    "/usr/bin/ffmpeg",
                    "/usr/local/bin/ffmpeg",
                    "/opt/ffmpeg/bin/ffmpeg",
                    "/snap/bin/ffmpeg",
                ]
            
            for path in common_paths:
                if os.path.exists(path) and self._verify_ffmpeg_executable(path):
                    return path
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding common FFmpeg locations: {e}")
            return None
    
    def _verify_ffmpeg_executable(self, path: str) -> bool:
        """
        Verify that the given path is a valid FFmpeg executable.
        
        Args:
            path: Path to potential FFmpeg executable
            
        Returns:
            True if valid FFmpeg executable, False otherwise
        """
        try:
            # Check if file exists and is executable
            if not os.path.exists(path):
                return False
            
            # On Windows, check for .exe extension
            if os.name == 'nt' and not path.lower().endswith('.exe'):
                return False
            
            # Try to run ffmpeg -version to verify it works
            import subprocess
            try:
                result = subprocess.run(
                    [path, '-version'], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                
                # Check if output contains FFmpeg identifier
                if result.returncode == 0 and 'ffmpeg version' in result.stdout.lower():
                    return True
                
            except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
                pass
            
            return False
            
        except Exception as e:
            logger.debug(f"Error verifying FFmpeg executable {path}: {e}")
            return False
    
    def get_ffmpeg_info(self) -> dict:
        """
        Get information about the detected FFmpeg installation.
        
        Returns:
            Dictionary with FFmpeg information
        """
        ffmpeg_path = self.get_ffmpeg_executable()
        
        info = {
            'found': ffmpeg_path is not None,
            'path': ffmpeg_path,
            'detection_attempted': self._detection_attempted,
            'project_root': str(self.project_root)
        }
        
        if ffmpeg_path:
            try:
                import subprocess
                result = subprocess.run(
                    [ffmpeg_path, '-version'], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                
                if result.returncode == 0:
                    # Extract version from output
                    version_line = result.stdout.split('\n')[0]
                    info['version'] = version_line
                    info['working'] = True
                else:
                    info['working'] = False
                    info['error'] = result.stderr
                    
            except Exception as e:
                info['working'] = False
                info['error'] = str(e)
        
        return info
    
    def create_ffmpeg_audio_source(self, source, **kwargs):
        """
        Create a Discord FFmpegPCMAudio source using the detected FFmpeg.
        
        Args:
            source: Audio source (URL, file path, etc.)
            **kwargs: Additional arguments for FFmpegPCMAudio
            
        Returns:
            Discord FFmpegPCMAudio instance
            
        Raises:
            RuntimeError: If FFmpeg is not available
        """
        try:
            import discord
            
            ffmpeg_path = self.get_ffmpeg_executable()
            
            if not ffmpeg_path:
                raise RuntimeError(
                    "FFmpeg not found. Please ensure FFmpeg is installed or place it in the project directory."
                )
            
            # Set the executable parameter
            kwargs['executable'] = ffmpeg_path
            
            # Create and return the audio source
            return discord.FFmpegPCMAudio(source, **kwargs)
            
        except ImportError:
            raise RuntimeError("discord.py is not available")
        except Exception as e:
            raise RuntimeError(f"Failed to create FFmpeg audio source: {e}")


# Global FFmpeg manager instance
_global_ffmpeg_manager: Optional[FFmpegManager] = None

def get_ffmpeg_manager() -> FFmpegManager:
    """
    Get the global FFmpeg manager instance.
    
    Returns:
        Global FFmpegManager instance
    """
    global _global_ffmpeg_manager
    
    if _global_ffmpeg_manager is None:
        _global_ffmpeg_manager = FFmpegManager()
    
    return _global_ffmpeg_manager

def get_ffmpeg_executable() -> Optional[str]:
    """
    Convenience function to get FFmpeg executable path.
    
    Returns:
        Path to FFmpeg executable or None if not found
    """
    return get_ffmpeg_manager().get_ffmpeg_executable()

def create_ffmpeg_audio_source(source, **kwargs):
    """
    Convenience function to create FFmpeg audio source.
    
    Args:
        source: Audio source (URL, file path, etc.)
        **kwargs: Additional arguments for FFmpegPCMAudio
        
    Returns:
        Discord FFmpegPCMAudio instance
        
    Raises:
        RuntimeError: If FFmpeg is not available
    """
    return get_ffmpeg_manager().create_ffmpeg_audio_source(source, **kwargs)

def get_ffmpeg_info() -> dict:
    """
    Convenience function to get FFmpeg information.
    
    Returns:
        Dictionary with FFmpeg information
    """
    return get_ffmpeg_manager().get_ffmpeg_info()
