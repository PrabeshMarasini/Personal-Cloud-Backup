import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Set
import logging
from pathlib import Path
import threading

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from .backup_engine import BackupEngine
from .database import DatabaseManager

logger = logging.getLogger(__name__)

class BackupFileHandler(FileSystemEventHandler):
    def __init__(self, backup_engine: BackupEngine, db_manager: DatabaseManager, 
                 device_id: str, debounce_seconds: int = 5):
        super().__init__()
        self.backup_engine = backup_engine
        self.db_manager = db_manager
        self.device_id = device_id
        self.debounce_seconds = debounce_seconds
        
        # Debouncing mechanism
        self._pending_files: Dict[str, datetime] = {}
        self._pending_lock = threading.Lock()
        self._debounce_timer = None
        
        # Statistics
        self._stats = {
            'files_detected': 0,
            'files_queued': 0,
            'events_processed': 0,
            'last_event_time': None
        }
    
    def _should_process_file(self, file_path: str) -> bool:
        """Check if file should be processed"""
        try:
            # Skip if file doesn't exist
            if not os.path.exists(file_path):
                return False
            
            # Skip directories
            if os.path.isdir(file_path):
                return False
            
            # Skip temporary/system files
            file_name = os.path.basename(file_path)
            if file_name.startswith('.') or file_name.endswith(('.tmp', '.temp', '.swp')):
                return False
            
            # Use backup engine's filters
            return self.backup_engine.should_backup_file(file_path)
            
        except Exception as e:
            logger.warning(f"Error checking file {file_path}: {e}")
            return False
    
    def _add_to_pending(self, file_path: str):
        """Add file to pending list with debouncing"""
        with self._pending_lock:
            self._pending_files[file_path] = datetime.now()
            self._stats['files_detected'] += 1
            
            # Reset debounce timer
            if self._debounce_timer:
                self._debounce_timer.cancel()
            
            self._debounce_timer = threading.Timer(
                self.debounce_seconds, 
                self._process_pending_files
            )
            self._debounce_timer.start()
    
    def _process_pending_files(self):
        """Process files after debounce period"""
        with self._pending_lock:
            if not self._pending_files:
                return
            
            now = datetime.now()
            files_to_process = []
            
            # Get files that have been stable for debounce period
            for file_path, add_time in list(self._pending_files.items()):
                if (now - add_time).total_seconds() >= self.debounce_seconds:
                    if os.path.exists(file_path) and self._should_process_file(file_path):
                        files_to_process.append(file_path)
                        
                        # Update sync status as pending
                        try:
                            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                            self.db_manager.update_sync_status(
                                file_path, self.device_id, file_mtime, 'pending'
                            )
                        except Exception as e:
                            logger.warning(f"Failed to update sync status for {file_path}: {e}")
                    
                    # Remove from pending regardless
                    del self._pending_files[file_path]
            
            if files_to_process:
                logger.info(f"Adding {len(files_to_process)} files to backup queue")
                self.backup_engine.add_to_backup_queue(files_to_process)
                self._stats['files_queued'] += len(files_to_process)
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events"""
        if event.is_directory:
            return
        
        self._stats['events_processed'] += 1
        self._stats['last_event_time'] = datetime.now()
        
        logger.debug(f"File modified: {event.src_path}")
        
        if self._should_process_file(event.src_path):
            self._add_to_pending(event.src_path)
    
    def on_created(self, event: FileSystemEvent):
        """Handle file creation events"""
        if event.is_directory:
            return
        
        self._stats['events_processed'] += 1
        self._stats['last_event_time'] = datetime.now()
        
        logger.debug(f"File created: {event.src_path}")
        
        if self._should_process_file(event.src_path):
            self._add_to_pending(event.src_path)
    
    def on_moved(self, event: FileSystemEvent):
        """Handle file move events"""
        if event.is_directory:
            return
        
        self._stats['events_processed'] += 1
        self._stats['last_event_time'] = datetime.now()
        
        logger.debug(f"File moved: {event.src_path} -> {event.dest_path}")
        
        # Process the destination file
        if hasattr(event, 'dest_path') and self._should_process_file(event.dest_path):
            self._add_to_pending(event.dest_path)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get handler statistics"""
        with self._pending_lock:
            return {
                'files_detected': self._stats['files_detected'],
                'files_queued': self._stats['files_queued'],
                'events_processed': self._stats['events_processed'],
                'pending_files_count': len(self._pending_files),
                'last_event_time': self._stats['last_event_time']
            }
    
    def stop(self):
        """Stop the handler and process remaining files"""
        if self._debounce_timer:
            self._debounce_timer.cancel()
        
        # Process any remaining pending files
        self._process_pending_files()


class FileMonitor:
    def __init__(self, backup_engine: BackupEngine, db_manager: DatabaseManager,
                 device_id: str, watched_directories: List[str],
                 debounce_seconds: int = 5):
        self.backup_engine = backup_engine
        self.db_manager = db_manager
        self.device_id = device_id
        self.watched_directories = watched_directories
        self.debounce_seconds = debounce_seconds
        
        self.observer = Observer()
        self.event_handler = None
        self.is_monitoring = False
        
        # Statistics
        self._start_time = None
        self._monitored_paths: Set[str] = set()
    
    def start_monitoring(self) -> bool:
        """Start monitoring watched directories"""
        try:
            logger.info(f"Starting file monitoring for {len(self.watched_directories)} directories")
            
            # Create event handler
            self.event_handler = BackupFileHandler(
                self.backup_engine, 
                self.db_manager,
                self.device_id,
                self.debounce_seconds
            )
            
            # Add watches for each directory
            for directory in self.watched_directories:
                if os.path.exists(directory) and os.path.isdir(directory):
                    self.observer.schedule(
                        self.event_handler,
                        directory,
                        recursive=True
                    )
                    self._monitored_paths.add(directory)
                    logger.info(f"Added watch for directory: {directory}")
                else:
                    logger.warning(f"Directory does not exist or is not accessible: {directory}")
            
            if not self._monitored_paths:
                logger.error("No valid directories to monitor")
                return False
            
            # Start observer
            self.observer.start()
            self.is_monitoring = True
            self._start_time = datetime.now()
            
            logger.info(f"File monitoring started successfully for {len(self._monitored_paths)} directories")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start file monitoring: {e}")
            return False
    
    def stop_monitoring(self):
        """Stop monitoring"""
        try:
            logger.info("Stopping file monitoring...")
            
            if self.event_handler:
                self.event_handler.stop()
            
            if self.observer.is_alive():
                self.observer.stop()
                self.observer.join(timeout=5)
            
            self.is_monitoring = False
            logger.info("File monitoring stopped")
            
        except Exception as e:
            logger.error(f"Error stopping file monitoring: {e}")
    
    def perform_initial_scan(self) -> Dict[str, Any]:
        """Perform initial scan of watched directories"""
        logger.info("Starting initial file scan...")
        
        results = {
            'total_files_found': 0,
            'files_needing_backup': 0,
            'directories_scanned': 0,
            'scan_start_time': datetime.now(),
            'errors': []
        }
        
        files_to_backup = []
        
        try:
            for directory in self.watched_directories:
                if not os.path.exists(directory):
                    logger.warning(f"Directory does not exist: {directory}")
                    continue
                
                results['directories_scanned'] += 1
                logger.info(f"Scanning directory: {directory}")
                
                for root, dirs, files in os.walk(directory):
                    # Skip hidden directories
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        results['total_files_found'] += 1
                        
                        try:
                            if self.backup_engine.should_backup_file(file_path):
                                if self.backup_engine.needs_backup(file_path):
                                    files_to_backup.append(file_path)
                                    results['files_needing_backup'] += 1
                                    
                                    # Update sync status
                                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                                    self.db_manager.update_sync_status(
                                        file_path, self.device_id, file_mtime, 'pending'
                                    )
                        
                        except Exception as e:
                            error_msg = f"Error processing {file_path}: {e}"
                            logger.warning(error_msg)
                            results['errors'].append(error_msg)
            
            # Add files to backup queue
            if files_to_backup:
                logger.info(f"Adding {len(files_to_backup)} files to backup queue from initial scan")
                self.backup_engine.add_to_backup_queue(files_to_backup)
            
            results['scan_end_time'] = datetime.now()
            results['scan_duration'] = (results['scan_end_time'] - results['scan_start_time']).total_seconds()
            
            logger.info(f"Initial scan completed: {results['total_files_found']} files found, "
                       f"{results['files_needing_backup']} need backup")
            
            return results
            
        except Exception as e:
            logger.error(f"Initial scan failed: {e}")
            results['error'] = str(e)
            return results
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics"""
        stats = {
            'is_monitoring': self.is_monitoring,
            'start_time': self._start_time,
            'monitored_directories': list(self._monitored_paths),
            'monitored_directories_count': len(self._monitored_paths),
            'uptime_seconds': None
        }
        
        if self._start_time:
            stats['uptime_seconds'] = (datetime.now() - self._start_time).total_seconds()
        
        if self.event_handler:
            stats.update(self.event_handler.get_stats())
        
        return stats
    
    def add_directory(self, directory_path: str) -> bool:
        """Add a new directory to monitor"""
        try:
            if not os.path.exists(directory_path) or not os.path.isdir(directory_path):
                logger.error(f"Invalid directory: {directory_path}")
                return False
            
            if directory_path in self._monitored_paths:
                logger.info(f"Directory already being monitored: {directory_path}")
                return True
            
            if self.is_monitoring and self.event_handler:
                self.observer.schedule(
                    self.event_handler,
                    directory_path,
                    recursive=True
                )
                self._monitored_paths.add(directory_path)
                logger.info(f"Added new directory to monitoring: {directory_path}")
                return True
            else:
                logger.error("Cannot add directory: monitoring not active")
                return False
                
        except Exception as e:
            logger.error(f"Failed to add directory {directory_path}: {e}")
            return False
    
    def remove_directory(self, directory_path: str) -> bool:
        """Remove a directory from monitoring"""
        try:
            if directory_path not in self._monitored_paths:
                logger.warning(f"Directory not being monitored: {directory_path}")
                return False
            
            # Note: watchdog doesn't provide a direct way to remove specific watches
            # This would require restarting the observer with the updated list
            logger.warning("Directory removal requires monitor restart")
            return False
            
        except Exception as e:
            logger.error(f"Failed to remove directory {directory_path}: {e}")
            return False
    
    def restart_monitoring(self) -> bool:
        """Restart monitoring (useful for configuration changes)"""
        try:
            logger.info("Restarting file monitoring...")
            
            self.stop_monitoring()
            time.sleep(1)  # Brief pause
            return self.start_monitoring()
            
        except Exception as e:
            logger.error(f"Failed to restart monitoring: {e}")
            return False
    
    def __enter__(self):
        """Context manager entry"""
        self.start_monitoring()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop_monitoring()


def create_file_monitor(backup_engine: BackupEngine, db_manager: DatabaseManager,
                       device_id: str, watched_directories: List[str] = None,
                       debounce_seconds: int = 5) -> FileMonitor:
    """Factory function to create file monitor"""
    if not watched_directories:
        from config.config import config
        watched_directories = config.watched_directories
    
    return FileMonitor(
        backup_engine=backup_engine,
        db_manager=db_manager,
        device_id=device_id,
        watched_directories=watched_directories,
        debounce_seconds=debounce_seconds
    )