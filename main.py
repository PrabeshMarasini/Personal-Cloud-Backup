#!/usr/bin/env python3
"""
Personal Cloud Backup & Versioning System
Main application entry point
"""

import os
import sys
import logging
import signal
import threading
import time
import schedule
from datetime import datetime
from typing import Optional

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config.config import config
from src.database import create_database_manager
from src.azure_client import create_azure_manager
from src.encryption import create_encryption_manager
from src.backup_engine import BackupEngine
from src.file_monitoring import create_file_monitor
from src.web_dashboard import create_web_app, run_web_app

# Setup logging
def setup_logging():
    """Configure logging system"""
    os.makedirs(os.path.dirname(config.logging_file), exist_ok=True)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler
    file_handler = logging.FileHandler(config.logging_file)
    file_handler.setLevel(getattr(logging, config.logging_level))
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.logging_level))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Reduce Azure SDK logging
    logging.getLogger('azure').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

class BackupSystem:
    def __init__(self):
        self.db_manager: Optional = None
        self.azure_manager: Optional = None
        self.encryption_manager: Optional = None
        self.backup_engine: Optional = None
        self.file_monitor: Optional = None
        self.web_app: Optional = None
        
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.web_thread: Optional[threading.Thread] = None
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown()
        sys.exit(0)
    
    def initialize(self) -> bool:
        """Initialize all system components"""
        try:
            logger.info("Initializing backup system...")
            
            # Validate configuration
            if not config.azure_connection_string:
                logger.error("Azure connection string not configured")
                return False
            
            if not config.encryption_key:
                logger.error("Encryption key not configured")
                return False
            
            # Initialize managers
            logger.info("Initializing database manager...")
            self.db_manager = create_database_manager()
            
            logger.info("Initializing Azure storage manager...")
            self.azure_manager = create_azure_manager()
            
            logger.info("Testing Azure connection...")
            if not self.azure_manager.test_connection():
                logger.error("Azure connection test failed")
                return False
            
            logger.info("Initializing encryption manager...")
            self.encryption_manager = create_encryption_manager()
            
            logger.info("Initializing backup engine...")
            self.backup_engine = BackupEngine(
                db_manager=self.db_manager,
                azure_manager=self.azure_manager,
                encryption_manager=self.encryption_manager,
                device_id=config.device_id,
                config=config
            )
            
            logger.info("Initializing file monitor...")
            self.file_monitor = create_file_monitor(
                backup_engine=self.backup_engine,
                db_manager=self.db_manager,
                device_id=config.device_id
            )
            
            logger.info("Initializing web dashboard...")
            self.web_app = create_web_app(
                db_manager=self.db_manager,
                azure_manager=self.azure_manager,
                backup_engine=self.backup_engine,
                file_monitor=self.file_monitor,
                device_id=config.device_id
            )
            
            logger.info("System initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"System initialization failed: {e}")
            return False
    
    def start(self) -> bool:
        """Start the backup system"""
        try:
            if not self.initialize():
                return False
            
            logger.info("Starting backup system...")
            
            # Perform initial scan
            logger.info("Performing initial file scan...")
            scan_results = self.file_monitor.perform_initial_scan()
            logger.info(f"Initial scan completed: {scan_results.get('files_needing_backup', 0)} files need backup")
            
            # Start file monitoring
            if not self.file_monitor.start_monitoring():
                logger.error("Failed to start file monitoring")
                return False
            
            # Setup scheduled tasks
            self._setup_scheduler()
            
            # Set running flag BEFORE starting threads
            self.is_running = True
            
            # Start scheduler in background thread
            self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=False)
            self.scheduler_thread.start()
            
            # Start web dashboard in background thread
            self.web_thread = threading.Thread(
                target=lambda: run_web_app(
                    self.web_app, 
                    config.web_host, 
                    config.web_port, 
                    config.web_debug
                ),
                daemon=True
            )
            self.web_thread.start()
            logger.info(f"Backup system started successfully!")
            logger.info(f"Web dashboard available at http://{config.web_host}:{config.web_port}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start backup system: {e}")
            return False
    
    def _setup_scheduler(self):
        """Setup scheduled tasks"""
        # Schedule regular backup queue processing
        schedule.every(config.backup_interval_minutes).minutes.do(
            self._scheduled_backup_process
        )
        
        # Schedule cleanup
        schedule.every(config.cleanup_interval_hours).hours.do(
            self._scheduled_cleanup
        )
        
        # Schedule database backup
        schedule.every(6).hours.do(self._scheduled_db_backup)
        
        logger.info("Scheduled tasks configured")
    
    def _run_scheduler(self):
        """Run scheduled tasks"""
        logger.info("Scheduler started")
        
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)
        
        logger.info("Scheduler stopped")
    
    def _scheduled_backup_process(self):
        """Process backup queue on schedule"""
        try:
            logger.info("Running scheduled backup process...")
            results = self.backup_engine.process_backup_queue()
            
            if results.get('status') == 'completed':
                successful = len(results.get('successful_backups', []))
                if successful > 0:
                    logger.info(f"Scheduled backup completed: {successful} files backed up")
            
        except Exception as e:
            logger.error(f"Scheduled backup process failed: {e}")
    
    def _scheduled_cleanup(self):
        """Run cleanup on schedule"""
        try:
            logger.info("Running scheduled cleanup...")
            results = self.backup_engine.cleanup_old_backups()
            
            db_cleaned = results.get('database_records_cleaned', 0)
            azure_cleaned = results.get('azure_blobs_cleaned', 0)
            
            if db_cleaned > 0 or azure_cleaned > 0:
                logger.info(f"Scheduled cleanup completed: {db_cleaned} DB records, {azure_cleaned} Azure blobs")
            
        except Exception as e:
            logger.error(f"Scheduled cleanup failed: {e}")
    
    def _scheduled_db_backup(self):
        """Backup the database file"""
        try:
            import shutil
            
            db_path = config.database_path
            backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            shutil.copy2(db_path, backup_path)
            logger.info(f"Database backed up to: {backup_path}")
            
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
    
    def run(self):
        """Run the main application loop"""
        if not self.start():
            logger.error("Failed to start backup system")
            return False
        
        try:
            logger.info("Backup system is running. Press Ctrl+C to stop.")
            
            # Keep main thread alive
            while self.is_running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        finally:
            self.shutdown()
        
        return True
    
    def shutdown(self):
        """Shutdown the backup system"""
        if not self.is_running:
            return
        
        logger.info("Shutting down backup system...")
        self.is_running = False
        
        try:
            # Stop file monitoring
            if self.file_monitor:
                self.file_monitor.stop_monitoring()
            
            # Process any remaining backup queue
            if self.backup_engine:
                logger.info("Processing final backup queue...")
                self.backup_engine.process_backup_queue()
            
            # Wait for threads to finish
            if self.scheduler_thread and self.scheduler_thread.is_alive():
                logger.info("Waiting for scheduler thread to finish...")
                self.scheduler_thread.join(timeout=5)
            
            if self.web_thread and self.web_thread.is_alive():
                logger.info("Waiting for web thread to finish...")
                self.web_thread.join(timeout=5)
            
            logger.info("Backup system shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


def main():
    """Main entry point"""
    print("Personal Cloud Backup & Versioning System")
    print("=========================================")
    
    # Setup logging first
    setup_logging()
    
    logger.info("Starting Personal Cloud Backup System")
    
    # Check required environment variables
    required_env_vars = ['AZURE_STORAGE_CONNECTION_STRING', 'BACKUP_ENCRYPTION_KEY']
    missing_vars = []
    
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.error("Please set the following environment variables:")
        logger.error("  AZURE_STORAGE_CONNECTION_STRING - Your Azure Storage connection string")
        logger.error("  BACKUP_ENCRYPTION_KEY - Encryption key for file encryption")
        logger.error("  AZURE_CONTAINER_NAME (optional) - Azure container name (default: 'backups')")
        logger.error("  DEVICE_ID (optional) - Unique device identifier (default: 'default-device')")
        sys.exit(1)
    
    # Create and run backup system
    backup_system = BackupSystem()
    
    try:
        success = backup_system.run()
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()