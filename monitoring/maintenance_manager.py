"""
Maintenance Management System for BunBot
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

from core import StateManager, EventBus, ConfigurationManager
from .interfaces import IMaintenanceManager, IAlertManager, AlertMessage, AlertSeverity

logger = logging.getLogger('discord.monitoring.maintenance_manager')

class MaintenanceManager(IMaintenanceManager):
    """
    Maintenance management service for BunBot.
    
    Handles scheduling, announcing, and managing maintenance windows
    with comprehensive guild communication and status tracking.
    """
    
    def __init__(self, state_manager: StateManager, event_bus: EventBus, 
                 config_manager: ConfigurationManager, alert_manager: IAlertManager,
                 database_connection=None):
        self.state_manager = state_manager
        self.event_bus = event_bus
        self.config_manager = config_manager
        self.alert_manager = alert_manager
        self.db = database_connection
        
        # Active maintenance tracking
        self._active_maintenance: Optional[Dict[str, Any]] = None
        self._maintenance_task: Optional[asyncio.Task] = None
        
        # Maintenance history
        self._maintenance_history: List[Dict[str, Any]] = []
        self._max_history_items = 100
        
        logger.info("MaintenanceManager initialized")
    
    async def schedule_maintenance(self, message: str, duration: timedelta, 
                                 start_time: Optional[datetime] = None) -> int:
        """
        Schedule a maintenance window.
        
        Args:
            message: Maintenance message to announce
            duration: Duration of the maintenance window
            start_time: When to start maintenance (None for immediate)
            
        Returns:
            Maintenance ID for tracking
        """
        try:
            # Set start time to now if not specified
            if start_time is None:
                start_time = datetime.now(timezone.utc)
            
            # Calculate end time
            end_time = start_time + duration
            
            # Create maintenance record
            maintenance_data = {
                'message': message,
                'start_time': start_time,
                'end_time': end_time,
                'status': 'scheduled',
                'created_at': datetime.now(timezone.utc),
                'affected_guilds': None  # None means all guilds
            }
            
            # Store in database if available
            maintenance_id = 1  # Default ID
            if self.db:
                cursor = await self.db.execute(
                    "INSERT INTO maintenance_windows (start_time, end_time, message, status, affected_guilds) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (start_time.isoformat(), end_time.isoformat(), message, 'scheduled', None)
                )
                maintenance_id = cursor.lastrowid
                await self.db.commit()
            
            maintenance_data['id'] = maintenance_id
            
            logger.info(f"Scheduled maintenance {maintenance_id}: {message} "
                       f"(Start: {start_time}, Duration: {duration})")
            
            # Emit maintenance scheduled event
            await self.event_bus.emit_async('maintenance_scheduled',
                                          maintenance_id=maintenance_id,
                                          message=message,
                                          start_time=start_time.isoformat(),
                                          duration_seconds=duration.total_seconds())
            
            # If maintenance is immediate, start it now
            if start_time <= datetime.now(timezone.utc):
                await self.start_maintenance(maintenance_id)
            else:
                # Schedule the maintenance to start later
                delay = (start_time - datetime.now(timezone.utc)).total_seconds()
                asyncio.create_task(self._delayed_maintenance_start(maintenance_id, delay))
                
                # Send pre-announcement
                await self._send_pre_maintenance_announcement(maintenance_data)
            
            return maintenance_id
            
        except Exception as e:
            logger.error(f"Failed to schedule maintenance: {e}")
            return -1
    
    async def start_maintenance(self, maintenance_id: int) -> bool:
        """
        Start a scheduled maintenance window.
        
        Args:
            maintenance_id: ID of the maintenance to start
            
        Returns:
            True if maintenance was started successfully
        """
        try:
            # Get maintenance details
            maintenance_data = await self._get_maintenance_by_id(maintenance_id)
            if not maintenance_data:
                logger.error(f"Maintenance {maintenance_id} not found")
                return False
            
            if maintenance_data['status'] != 'scheduled':
                logger.warning(f"Maintenance {maintenance_id} is not in scheduled status: {maintenance_data['status']}")
                return False
            
            # Update status to active
            maintenance_data['status'] = 'active'
            maintenance_data['actual_start_time'] = datetime.now(timezone.utc)
            
            if self.db:
                await self.db.execute(
                    "UPDATE maintenance_windows SET status = 'active' WHERE id = ?",
                    (maintenance_id,)
                )
                await self.db.commit()
            
            # Set as active maintenance
            self._active_maintenance = maintenance_data
            
            # Send start announcement
            await self._send_maintenance_start_announcement(maintenance_data)
            
            # Schedule automatic end
            duration = maintenance_data['end_time'] - maintenance_data['start_time']
            self._maintenance_task = asyncio.create_task(
                self._auto_end_maintenance(maintenance_id, duration.total_seconds())
            )
            
            logger.info(f"Started maintenance {maintenance_id}: {maintenance_data['message']}")
            
            # Emit maintenance started event
            await self.event_bus.emit_async('maintenance_started',
                                          maintenance_id=maintenance_id,
                                          message=maintenance_data['message'])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start maintenance {maintenance_id}: {e}")
            return False
    
    async def end_maintenance(self, maintenance_id: int, 
                            completion_message: Optional[str] = None) -> bool:
        """
        End a maintenance window.
        
        Args:
            maintenance_id: ID of the maintenance to end
            completion_message: Optional completion message
            
        Returns:
            True if maintenance was ended successfully
        """
        try:
            # Get maintenance details
            maintenance_data = await self._get_maintenance_by_id(maintenance_id)
            if not maintenance_data:
                logger.error(f"Maintenance {maintenance_id} not found")
                return False
            
            if maintenance_data['status'] != 'active':
                logger.warning(f"Maintenance {maintenance_id} is not active: {maintenance_data['status']}")
                return False
            
            # Update status to completed
            maintenance_data['status'] = 'completed'
            maintenance_data['actual_end_time'] = datetime.now(timezone.utc)
            maintenance_data['completion_message'] = completion_message
            
            if self.db:
                await self.db.execute(
                    "UPDATE maintenance_windows SET status = 'completed' WHERE id = ?",
                    (maintenance_id,)
                )
                await self.db.commit()
            
            # Clear active maintenance
            if self._active_maintenance and self._active_maintenance['id'] == maintenance_id:
                self._active_maintenance = None
            
            # Cancel auto-end task if running
            if self._maintenance_task and not self._maintenance_task.done():
                self._maintenance_task.cancel()
                self._maintenance_task = None
            
            # Send completion announcement
            await self._send_maintenance_end_announcement(maintenance_data)
            
            # Add to history
            self._add_to_history(maintenance_data)
            
            logger.info(f"Ended maintenance {maintenance_id}: {maintenance_data['message']}")
            
            # Emit maintenance ended event
            await self.event_bus.emit_async('maintenance_ended',
                                          maintenance_id=maintenance_id,
                                          message=maintenance_data['message'],
                                          completion_message=completion_message)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to end maintenance {maintenance_id}: {e}")
            return False
    
    async def get_active_maintenance(self) -> Optional[Dict[str, Any]]:
        """
        Get currently active maintenance window.
        
        Returns:
            Active maintenance data or None if no maintenance is active
        """
        return self._active_maintenance.copy() if self._active_maintenance else None
    
    async def get_scheduled_maintenances(self) -> List[Dict[str, Any]]:
        """
        Get all scheduled maintenances.
        
        Returns:
            List of scheduled maintenance windows
        """
        if not self.db:
            return []
        
        try:
            cursor = await self.db.execute(
                "SELECT * FROM maintenance_windows WHERE status = 'scheduled' ORDER BY start_time"
            )
            rows = await cursor.fetchall()
            
            maintenances = []
            for row in rows:
                maintenance = {
                    'id': row[0],
                    'start_time': datetime.fromisoformat(row[1]),
                    'end_time': datetime.fromisoformat(row[2]),
                    'message': row[3],
                    'status': row[4],
                    'affected_guilds': row[5]
                }
                maintenances.append(maintenance)
            
            return maintenances
            
        except Exception as e:
            logger.error(f"Failed to get scheduled maintenances: {e}")
            return []
    
    async def cancel_maintenance(self, maintenance_id: int) -> bool:
        """
        Cancel a scheduled maintenance.
        
        Args:
            maintenance_id: ID of the maintenance to cancel
            
        Returns:
            True if maintenance was cancelled successfully
        """
        try:
            # Get maintenance details
            maintenance_data = await self._get_maintenance_by_id(maintenance_id)
            if not maintenance_data:
                logger.error(f"Maintenance {maintenance_id} not found")
                return False
            
            if maintenance_data['status'] not in ['scheduled', 'active']:
                logger.warning(f"Cannot cancel maintenance {maintenance_id} with status: {maintenance_data['status']}")
                return False
            
            # Update status to cancelled
            if self.db:
                await self.db.execute(
                    "UPDATE maintenance_windows SET status = 'cancelled' WHERE id = ?",
                    (maintenance_id,)
                )
                await self.db.commit()
            
            # If this was the active maintenance, clear it
            if self._active_maintenance and self._active_maintenance['id'] == maintenance_id:
                self._active_maintenance = None
                
                # Cancel auto-end task
                if self._maintenance_task and not self._maintenance_task.done():
                    self._maintenance_task.cancel()
                    self._maintenance_task = None
            
            # Send cancellation announcement
            await self._send_maintenance_cancellation_announcement(maintenance_data)
            
            logger.info(f"Cancelled maintenance {maintenance_id}: {maintenance_data['message']}")
            
            # Emit maintenance cancelled event
            await self.event_bus.emit_async('maintenance_cancelled',
                                          maintenance_id=maintenance_id,
                                          message=maintenance_data['message'])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel maintenance {maintenance_id}: {e}")
            return False
    
    async def _get_maintenance_by_id(self, maintenance_id: int) -> Optional[Dict[str, Any]]:
        """Get maintenance data by ID"""
        if not self.db:
            # If no database, check if it's the active maintenance
            if self._active_maintenance and self._active_maintenance['id'] == maintenance_id:
                return self._active_maintenance
            return None
        
        try:
            cursor = await self.db.execute(
                "SELECT * FROM maintenance_windows WHERE id = ?",
                (maintenance_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            return {
                'id': row[0],
                'start_time': datetime.fromisoformat(row[1]),
                'end_time': datetime.fromisoformat(row[2]),
                'message': row[3],
                'status': row[4],
                'affected_guilds': row[5]
            }
            
        except Exception as e:
            logger.error(f"Failed to get maintenance {maintenance_id}: {e}")
            return None
    
    async def _send_pre_maintenance_announcement(self, maintenance_data: Dict[str, Any]) -> None:
        """Send pre-maintenance announcement"""
        try:
            start_time = maintenance_data['start_time']
            time_until = start_time - datetime.now(timezone.utc)
            
            if time_until.total_seconds() > 0:
                time_str = self._format_duration(time_until)
                message = f"🔧 **Scheduled Maintenance Notice**\n\n"
                message += f"**Message**: {maintenance_data['message']}\n"
                message += f"**Starts in**: {time_str}\n"
                message += f"**Start Time**: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                message += f"**Duration**: {self._format_duration(maintenance_data['end_time'] - start_time)}\n\n"
                message += "The bot may be unavailable during this time."
                
                await self.alert_manager.send_maintenance_announcement(message)
                logger.info(f"Sent pre-maintenance announcement for maintenance {maintenance_data['id']}")
            
        except Exception as e:
            logger.error(f"Failed to send pre-maintenance announcement: {e}")
    
    async def _send_maintenance_start_announcement(self, maintenance_data: Dict[str, Any]) -> None:
        """Send maintenance start announcement"""
        try:
            duration = maintenance_data['end_time'] - maintenance_data['start_time']
            message = f"🔧 **Maintenance Started**\n\n"
            message += f"**Message**: {maintenance_data['message']}\n"
            message += f"**Duration**: {self._format_duration(duration)}\n"
            message += f"**Expected End**: {maintenance_data['end_time'].strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
            message += "The bot may experience interruptions during this time."
            
            await self.alert_manager.send_maintenance_announcement(message)
            logger.info(f"Sent maintenance start announcement for maintenance {maintenance_data['id']}")
            
        except Exception as e:
            logger.error(f"Failed to send maintenance start announcement: {e}")
    
    async def _send_maintenance_end_announcement(self, maintenance_data: Dict[str, Any]) -> None:
        """Send maintenance end announcement"""
        try:
            message = f"✅ **Maintenance Completed**\n\n"
            message += f"**Message**: {maintenance_data['message']}\n"
            
            if maintenance_data.get('completion_message'):
                message += f"**Details**: {maintenance_data['completion_message']}\n"
            
            message += "\nBot services have been restored. Thank you for your patience!"
            
            await self.alert_manager.send_maintenance_announcement(message)
            logger.info(f"Sent maintenance end announcement for maintenance {maintenance_data['id']}")
            
        except Exception as e:
            logger.error(f"Failed to send maintenance end announcement: {e}")
    
    async def _send_maintenance_cancellation_announcement(self, maintenance_data: Dict[str, Any]) -> None:
        """Send maintenance cancellation announcement"""
        try:
            message = f"❌ **Maintenance Cancelled**\n\n"
            message += f"**Message**: {maintenance_data['message']}\n"
            message += "\nThe scheduled maintenance has been cancelled."
            
            await self.alert_manager.send_maintenance_announcement(message)
            logger.info(f"Sent maintenance cancellation announcement for maintenance {maintenance_data['id']}")
            
        except Exception as e:
            logger.error(f"Failed to send maintenance cancellation announcement: {e}")
    
    async def _delayed_maintenance_start(self, maintenance_id: int, delay_seconds: float) -> None:
        """Start maintenance after a delay"""
        try:
            await asyncio.sleep(delay_seconds)
            await self.start_maintenance(maintenance_id)
        except asyncio.CancelledError:
            logger.info(f"Delayed start for maintenance {maintenance_id} was cancelled")
        except Exception as e:
            logger.error(f"Error in delayed maintenance start for {maintenance_id}: {e}")
    
    async def _auto_end_maintenance(self, maintenance_id: int, duration_seconds: float) -> None:
        """Automatically end maintenance after duration"""
        try:
            await asyncio.sleep(duration_seconds)
            await self.end_maintenance(maintenance_id, "Maintenance window completed automatically")
        except asyncio.CancelledError:
            logger.info(f"Auto-end for maintenance {maintenance_id} was cancelled")
        except Exception as e:
            logger.error(f"Error in auto-end maintenance for {maintenance_id}: {e}")
    
    def _format_duration(self, duration: timedelta) -> str:
        """Format timedelta as human-readable string"""
        total_seconds = int(duration.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds} seconds"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes} minutes"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            if minutes > 0:
                return f"{hours} hours {minutes} minutes"
            else:
                return f"{hours} hours"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            if hours > 0:
                return f"{days} days {hours} hours"
            else:
                return f"{days} days"
    
    def _add_to_history(self, maintenance_data: Dict[str, Any]) -> None:
        """Add completed maintenance to history"""
        self._maintenance_history.append(maintenance_data.copy())
        
        # Limit history size
        if len(self._maintenance_history) > self._max_history_items:
            self._maintenance_history = self._maintenance_history[-self._max_history_items:]
    
    def get_maintenance_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent maintenance history"""
        return self._maintenance_history[-limit:] if limit else self._maintenance_history
    
    def get_maintenance_stats(self) -> Dict[str, Any]:
        """Get maintenance statistics"""
        total_completed = len(self._maintenance_history)
        
        # Calculate average duration from history
        if self._maintenance_history:
            total_duration = sum(
                (m['actual_end_time'] - m['actual_start_time']).total_seconds()
                for m in self._maintenance_history
                if m.get('actual_start_time') and m.get('actual_end_time')
            )
            avg_duration = total_duration / len(self._maintenance_history) if self._maintenance_history else 0
        else:
            avg_duration = 0
        
        return {
            'total_completed': total_completed,
            'average_duration_seconds': avg_duration,
            'active_maintenance': self._active_maintenance is not None,
            'active_maintenance_id': self._active_maintenance['id'] if self._active_maintenance else None
        }
