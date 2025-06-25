"""
Automated Recovery Manager for BunBot
"""

import logging
import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

from core import StateManager, EventBus, ConfigurationManager
from .interfaces import (
    IRecoveryManager, RecoveryResult, IssueType, HealthStatus
)

logger = logging.getLogger('discord.monitoring.recovery_manager')

class RecoveryManager(IRecoveryManager):
    """
    Automated recovery system for BunBot issues.
    
    Handles automatic recovery from common issues like stream disconnections,
    state desynchronization, and voice client problems. Provides configurable
    retry limits and tracks recovery success rates.
    """
    
    def __init__(self, state_manager: StateManager, event_bus: EventBus, 
                 config_manager: ConfigurationManager):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.config_manager = config_manager
        
        # Recovery attempt tracking
        self._recovery_attempts: Dict[str, int] = {}  # "guild_id:issue_type" -> attempt count
        self._recovery_history: List[RecoveryResult] = []
        self._max_history_items = 1000
        
        # Recovery configuration
        self._max_attempts = 3
        self._backoff_base = 2.0  # seconds
        self._max_backoff = 300.0  # 5 minutes
        self._reset_attempts_after = timedelta(hours=1)
        
        # Track last attempt times for backoff calculation
        self._last_attempt_times: Dict[str, datetime] = {}
        
        # Subscribe to issue detection events
        self.event_bus.subscribe(['issue_detected'], self.handle_issue_detected,
                                handler_id='recovery_manager_issue_handler')
        
        logger.info("RecoveryManager initialized")
    
    async def attempt_recovery(self, guild_id: int, issue_type: IssueType) -> RecoveryResult:
        """
        Attempt to recover from a specific issue.
        
        Args:
            guild_id: Discord guild ID where the issue occurred
            issue_type: Type of issue to recover from
            
        Returns:
            RecoveryResult with success status and details
        """
        start_time = time.time()
        attempt_key = f"{guild_id}:{issue_type.value}"
        
        try:
            logger.info(f"[{guild_id}]: Starting recovery for {issue_type.value}")
            
            # Check if we can attempt recovery
            if not await self.can_attempt_recovery(guild_id, issue_type):
                result = RecoveryResult(
                    guild_id=guild_id,
                    issue_type=issue_type,
                    success=False,
                    message="Maximum recovery attempts exceeded",
                    attempt_number=self._recovery_attempts.get(attempt_key, 0),
                    recovery_time_seconds=time.time() - start_time
                )
                self._add_to_history(result)
                return result
            
            # Increment attempt counter
            current_attempts = self._recovery_attempts.get(attempt_key, 0) + 1
            self._recovery_attempts[attempt_key] = current_attempts
            self._last_attempt_times[attempt_key] = datetime.now(timezone.utc)
            
            # Apply backoff delay if this is a retry
            if current_attempts > 1:
                backoff_delay = min(
                    self._backoff_base ** (current_attempts - 1),
                    self._max_backoff
                )
                logger.info(f"[{guild_id}]: Applying backoff delay: {backoff_delay:.1f}s")
                await asyncio.sleep(backoff_delay)
            
            # Attempt recovery based on issue type
            success = False
            message = ""
            error_details = None
            
            if issue_type == IssueType.STREAM_DISCONNECT:
                success, message, error_details = await self._recover_stream_disconnect(guild_id)
            elif issue_type == IssueType.STATE_DESYNC:
                success, message, error_details = await self._recover_state_desync(guild_id)
            elif issue_type == IssueType.VOICE_CLIENT_LOST:
                success, message, error_details = await self._recover_voice_client_lost(guild_id)
            elif issue_type == IssueType.STREAM_UNAVAILABLE:
                success, message, error_details = await self._recover_stream_unavailable(guild_id)
            elif issue_type == IssueType.PERMISSION_ERROR:
                success, message, error_details = await self._recover_permission_error(guild_id)
            else:
                success, message, error_details = await self._recover_unknown_error(guild_id)
            
            # Create recovery result
            result = RecoveryResult(
                guild_id=guild_id,
                issue_type=issue_type,
                success=success,
                message=message,
                attempt_number=current_attempts,
                recovery_time_seconds=time.time() - start_time,
                error_details=error_details
            )
            
            # Reset attempt counter on success
            if success:
                await self.reset_recovery_attempts(guild_id, issue_type)
                logger.info(f"[{guild_id}]: Recovery successful for {issue_type.value}")
                
                # Emit success event
                await self.event_bus.emit_async('recovery_successful',
                                              guild_id=guild_id,
                                              issue_type=issue_type.value,
                                              attempt_number=current_attempts,
                                              recovery_time=result.recovery_time_seconds)
            else:
                logger.warning(f"[{guild_id}]: Recovery failed for {issue_type.value}: {message}")
                
                # Emit failure event
                await self.event_bus.emit_async('recovery_failed',
                                              guild_id=guild_id,
                                              issue_type=issue_type.value,
                                              attempt_number=current_attempts,
                                              error=message)
            
            # Store result in history
            self._add_to_history(result)
            return result
            
        except Exception as e:
            logger.error(f"[{guild_id}]: Recovery attempt failed with exception: {e}")
            
            result = RecoveryResult(
                guild_id=guild_id,
                issue_type=issue_type,
                success=False,
                message=f"Recovery attempt failed: {e}",
                attempt_number=self._recovery_attempts.get(attempt_key, 0),
                recovery_time_seconds=time.time() - start_time,
                error_details=str(e)
            )
            
            self._add_to_history(result)
            return result
    
    async def can_attempt_recovery(self, guild_id: int, issue_type: IssueType) -> bool:
        """
        Check if recovery can be attempted for the given issue.
        
        Args:
            guild_id: Discord guild ID
            issue_type: Type of issue
            
        Returns:
            True if recovery can be attempted, False if max attempts exceeded
        """
        attempt_key = f"{guild_id}:{issue_type.value}"
        current_attempts = self._recovery_attempts.get(attempt_key, 0)
        
        # Check if we've exceeded max attempts
        if current_attempts >= self._max_attempts:
            # Check if enough time has passed to reset attempts
            last_attempt = self._last_attempt_times.get(attempt_key)
            if last_attempt:
                time_since_last = datetime.now(timezone.utc) - last_attempt
                if time_since_last >= self._reset_attempts_after:
                    # Reset attempts after timeout
                    await self.reset_recovery_attempts(guild_id, issue_type)
                    return True
            return False
        
        return True
    
    async def reset_recovery_attempts(self, guild_id: int, issue_type: IssueType) -> None:
        """
        Reset recovery attempt counter for successful recovery.
        
        Args:
            guild_id: Discord guild ID
            issue_type: Type of issue
        """
        attempt_key = f"{guild_id}:{issue_type.value}"
        if attempt_key in self._recovery_attempts:
            del self._recovery_attempts[attempt_key]
        if attempt_key in self._last_attempt_times:
            del self._last_attempt_times[attempt_key]
        
        logger.debug(f"[{guild_id}]: Reset recovery attempts for {issue_type.value}")
    
    async def get_recovery_history(self, guild_id: int, hours: int = 24) -> List[RecoveryResult]:
        """
        Get recovery attempt history for a guild.
        
        Args:
            guild_id: Discord guild ID
            hours: Number of hours of history to retrieve
            
        Returns:
            List of recovery results for the guild
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        return [
            result for result in self._recovery_history
            if result.guild_id == guild_id and result.timestamp >= cutoff_time
        ]
    
    async def handle_issue_detected(self, event) -> None:
        """
        Handle issue detected events and trigger automatic recovery.
        
        Args:
            event: Issue detection event from health monitor
        """
        try:
            guild_id = event.get_event_data('guild_id')
            issue_type_str = event.get_event_data('issue_type')
            description = event.get_event_data('description', 'No description')
            
            if not guild_id or not issue_type_str:
                logger.warning("Received issue detection event with missing data")
                return
            
            # Convert string to IssueType enum
            try:
                issue_type = IssueType(issue_type_str)
            except ValueError:
                logger.warning(f"Unknown issue type: {issue_type_str}")
                issue_type = IssueType.UNKNOWN_ERROR
            
            logger.info(f"[{guild_id}]: Issue detected: {issue_type.value} - {description}")
            
            # Check if automatic recovery is enabled for this issue type
            if await self._should_auto_recover(guild_id, issue_type):
                # Schedule recovery attempt
                asyncio.create_task(self.attempt_recovery(guild_id, issue_type))
            else:
                logger.info(f"[{guild_id}]: Automatic recovery disabled for {issue_type.value}")
            
        except Exception as e:
            logger.error(f"Error handling issue detection event: {e}")
    
    async def _should_auto_recover(self, guild_id: int, issue_type: IssueType) -> bool:
        """Check if automatic recovery should be attempted for this issue type"""
        # This could be made configurable per guild or issue type
        # For now, enable auto-recovery for all issue types
        return True
    
    async def _recover_stream_disconnect(self, guild_id: int) -> Tuple[bool, str, Optional[str]]:
        """Recover from stream disconnection"""
        try:
            # Get current guild state
            state = self.state_manager.get_guild_state(guild_id, create_if_missing=False)
            if not state:
                return False, "No guild state found", None
            
            # Get the stream URL that was playing
            stream_url = state.current_stream_url
            if not stream_url:
                return False, "No stream URL to restart", None
            
            # Clear current state but preserve the URL
            original_channel = state.text_channel
            self.state_manager.clear_guild_state(guild_id, preserve_custom=True)
            
            # Emit stream restart event that the bot can handle
            await self.event_bus.emit_async('request_stream_restart',
                                          guild_id=guild_id,
                                          stream_url=stream_url,
                                          original_channel_id=original_channel.id if original_channel else None)
            
            # Wait a moment for the restart to take effect
            await asyncio.sleep(2.0)
            
            # Check if restart was successful
            new_state = self.state_manager.get_guild_state(guild_id, create_if_missing=False)
            if new_state and new_state.current_stream_url == stream_url:
                return True, f"Successfully restarted stream: {stream_url}", None
            else:
                return False, f"Stream restart request sent but state not updated", None
            
        except Exception as e:
            return False, f"Failed to recover from stream disconnect: {e}", str(e)
    
    async def _recover_state_desync(self, guild_id: int) -> Tuple[bool, str, Optional[str]]:
        """Recover from state desynchronization"""
        try:
            # Get current state
            state = self.state_manager.get_guild_state(guild_id, create_if_missing=False)
            if not state:
                return True, "No state found - issue resolved", None
            
            # Check for stuck cleanup
            if getattr(state, 'cleaning_up', False):
                # Force clear the cleanup flag
                self.state_manager.update_guild_state(guild_id, {'cleaning_up': False})
                logger.info(f"[{guild_id}]: Cleared stuck cleanup flag")
            
            # Try to synchronize with actual Discord state
            try:
                import bot
                guild = bot.bot.get_guild(guild_id)
                
                if guild:
                    voice_client = guild.voice_client
                    
                    # If no voice client but state thinks there should be one, clear state
                    if not voice_client and state.current_stream_url:
                        self.state_manager.clear_guild_state(guild_id, preserve_custom=True)
                        return True, "Cleared stale state - no voice client found", None
                    
                    # If voice client exists but no stream URL, this might be OK
                    # The voice client could be connecting for a new stream
                    
            except Exception as e:
                logger.debug(f"Could not check Discord state for guild {guild_id}: {e}")
            
            return True, "State desync recovery completed", None
            
        except Exception as e:
            return False, f"Failed to recover from state desync: {e}", str(e)
    
    async def _recover_voice_client_lost(self, guild_id: int) -> Tuple[bool, str, Optional[str]]:
        """Recover from lost voice client"""
        try:
            # This issue usually indicates the voice client disconnected unexpectedly
            # The best recovery is to restart the stream if one was active
            state = self.state_manager.get_guild_state(guild_id, create_if_missing=False)
            
            if state and state.current_stream_url:
                # Treat this as a stream disconnect and attempt restart
                return await self._recover_stream_disconnect(guild_id)
            else:
                # No active stream, just clear any stale state
                self.state_manager.clear_guild_state(guild_id, preserve_custom=True)
                return True, "Cleared state for lost voice client", None
            
        except Exception as e:
            return False, f"Failed to recover from voice client lost: {e}", str(e)
    
    async def _recover_stream_unavailable(self, guild_id: int) -> Tuple[bool, str, Optional[str]]:
        """Recover from stream unavailable"""
        try:
            # For stream unavailable issues, we might want to wait and retry
            # or notify users that the stream is having issues
            
            state = self.state_manager.get_guild_state(guild_id, create_if_missing=False)
            if not state or not state.current_stream_url:
                return True, "No active stream to recover", None
            
            # Test if the stream is available now
            try:
                import urllib.request
                request = urllib.request.Request(state.current_stream_url, method='HEAD')
                response = urllib.request.urlopen(request, timeout=10)
                response.close()
                
                # Stream is accessible, might be a temporary issue
                return True, "Stream is now accessible", None
                
            except Exception:
                # Stream still not accessible
                # For now, just log and don't restart automatically
                # This prevents endless restart loops for permanently down streams
                return False, "Stream still unavailable", "Stream URL not accessible"
            
        except Exception as e:
            return False, f"Failed to recover from stream unavailable: {e}", str(e)
    
    async def _recover_permission_error(self, guild_id: int) -> Tuple[bool, str, Optional[str]]:
        """Recover from permission errors"""
        try:
            # Permission errors usually can't be automatically fixed
            # We can only log and notify
            return False, "Permission errors require manual intervention", "Cannot automatically fix permissions"
            
        except Exception as e:
            return False, f"Failed to handle permission error: {e}", str(e)
    
    async def _recover_unknown_error(self, guild_id: int) -> Tuple[bool, str, Optional[str]]:
        """Recover from unknown errors"""
        try:
            # For unknown errors, try a general state cleanup
            state = self.state_manager.get_guild_state(guild_id, create_if_missing=False)
            
            if state:
                # Clear any stuck cleanup flags
                if getattr(state, 'cleaning_up', False):
                    self.state_manager.update_guild_state(guild_id, {'cleaning_up': False})
                
                # If there's an active stream, try to restart it
                if state.current_stream_url:
                    return await self._recover_stream_disconnect(guild_id)
            
            return True, "General cleanup completed for unknown error", None
            
        except Exception as e:
            return False, f"Failed to recover from unknown error: {e}", str(e)
    
    def _add_to_history(self, result: RecoveryResult) -> None:
        """Add recovery result to history"""
        self._recovery_history.append(result)
        
        # Limit history size
        if len(self._recovery_history) > self._max_history_items:
            self._recovery_history = self._recovery_history[-self._max_history_items:]
    
    def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery statistics"""
        if not self._recovery_history:
            return {
                'total_attempts': 0,
                'success_rate': 0.0,
                'recent_attempts': 0,
                'recent_success_rate': 0.0
            }
        
        total_attempts = len(self._recovery_history)
        successful_attempts = sum(1 for r in self._recovery_history if r.success)
        success_rate = successful_attempts / total_attempts if total_attempts > 0 else 0.0
        
        # Recent stats (last 24 hours)
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_results = [r for r in self._recovery_history if r.timestamp >= recent_cutoff]
        recent_attempts = len(recent_results)
        recent_successful = sum(1 for r in recent_results if r.success)
        recent_success_rate = recent_successful / recent_attempts if recent_attempts > 0 else 0.0
        
        return {
            'total_attempts': total_attempts,
            'successful_attempts': successful_attempts,
            'success_rate': success_rate,
            'recent_attempts': recent_attempts,
            'recent_successful': recent_successful,
            'recent_success_rate': recent_success_rate
        }
