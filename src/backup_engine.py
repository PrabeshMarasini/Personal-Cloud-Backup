import os
import gzip
import fnmatch
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import time
import threading
from pathlib import Path

from .database import DatabaseManager
from .azure_client import AzureStorageManager
from .encryption import EncryptionManager

logger = logging.getLogger(__name__)

class BackupEngine:
    def __init__(self, db_manager: DatabaseManager, 
                 azure_manager: AzureStorageManager,
                 encryption_manager: EncryptionManager,
                 device_id: str,
                 config: Any):
        self.db_manager = db_manager
        self.azure_manager = azure_manager
        self.encryption_manager = encryption_manager
        self.device_id = device_id
        self.config = config
        self._backup_queue = []
        self._backup_lock = threading.Lock()
        self._is_backing_up = False
    
    def should_backup_file(self, file_path: str) -> bool:
        """Check if file should be backed up based on filters"""
        try:
            # Check file size
            file_size = os.path.getsize(file_path)
            max_size_bytes = self.config.max_file_size_mb * 1024 * 1024
            
            if file_size > max_size_bytes:
                logger.debug(f"File too large: {file_path} ({file_size} bytes)")
                return False
            
            # Check exclude patterns
            file_name = os.path.basename(file_path)
            relative_path = os.path.relpath(file_path)
            
            for pattern in self.config.exclude_patterns:
                if fnmatch.fnmatch(file_name, pattern) or fnmatch.fnmatch(relative_path, pattern):
                    logger.debug(f"File excluded by pattern '{pattern}': {file_path}")
                    return False
            
            # Check if file is accessible
            if not os.access(file_path, os.R_OK):
                logger.debug(f"File not readable: {file_path}")
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error checking file {file_path}: {e}")
            return False
    
    def needs_backup(self, file_path: str) -> bool:
        """Check if file needs backup (modified since last backup)"""
        try:
            # Get file modification time
            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
            
            # Get latest backup info
            latest_backup = self.db_manager.get_latest_backup(file_path, self.device_id)
            
            if not latest_backup:
                logger.debug(f"No previous backup found for: {file_path}")
                return True
            
            # Check if file was modified after last backup
            last_backup_time = datetime.fromisoformat(latest_backup['backup_date'])
            
            if file_mtime > last_backup_time:
                logger.debug(f"File modified since last backup: {file_path}")
                return True
            
            # Check if checksum is different (for same modification time)
            current_checksum = self.encryption_manager.generate_file_hash(file_path)
            if current_checksum != latest_backup['checksum']:
                logger.debug(f"File content changed: {file_path}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking backup need for {file_path}: {e}")
            return True  # Default to backing up if we can't determine
    
    def compress_file_data(self, data: bytes) -> bytes:
        """Compress data using gzip"""
        try:
            compressed_data = gzip.compress(data, compresslevel=self.config.compression_level)
            # Handle division by zero for empty files
            if len(data) > 0:
                compression_ratio = len(compressed_data) / len(data)
                logger.debug(f"Compressed {len(data)} bytes to {len(compressed_data)} bytes (ratio: {compression_ratio:.2f})")
            else:
                logger.debug(f"Compressed empty file: 0 bytes to {len(compressed_data)} bytes")
            return compressed_data
        except Exception as e:
            logger.error(f"Compression failed: {e}")
            raise
    
    def backup_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Backup a single file
        Returns backup information or None if failed
        """
        try:
            logger.info(f"Starting backup of: {file_path}")
            
            # Validate file
            if not self.should_backup_file(file_path):
                return None
            
            if not self.needs_backup(file_path):
                logger.debug(f"File doesn't need backup: {file_path}")
                return None
            
            # Read and process file
            with open(file_path, 'rb') as f:
                original_data = f.read()
            
            original_size = len(original_data)
            
            # Warn about large files
            large_file_threshold = getattr(self.config, 'large_file_threshold_mb', 10) * 1024 * 1024
            if original_size > large_file_threshold:
                logger.info(f"Processing large file: {file_path} ({original_size / 1024 / 1024:.1f} MB)")
                logger.info("This may take several minutes depending on your internet connection...")
            
            # Generate checksum
            checksum = self.encryption_manager.generate_data_hash(original_data)
            
            # Compress data
            compressed_data = self.compress_file_data(original_data)
            compressed_size = len(compressed_data)
            
            # Encrypt data
            encrypted_data, salt = self.encryption_manager.encrypt_data(compressed_data)
            encrypted_size = len(encrypted_data)
            
            # Generate blob name
            version = self.db_manager.get_next_version(file_path, self.device_id)
            blob_name = self.azure_manager.generate_blob_name(
                self.device_id, file_path, version
            )
            
            # Prepare metadata
            metadata = {
                'original_filename': os.path.basename(file_path),
                'original_size': str(original_size),
                'compressed_size': str(compressed_size),
                'device_id': self.device_id,
                'backup_version': str(version),
                'checksum': checksum,
                'compression_level': str(self.config.compression_level)
            }
            
            # Upload to Azure with retry and chunking configuration
            chunk_size = getattr(self.config, 'chunk_size_mb', 4) * 1024 * 1024
            max_retries = getattr(self.config, 'retry_attempts', 3)
            
            logger.info(f"Uploading {len(encrypted_data)} bytes to Azure Storage...")
            upload_result = self.azure_manager.upload_blob(
                blob_name=blob_name,
                data=encrypted_data,
                metadata=metadata,
                max_retries=max_retries,
                chunk_size=chunk_size
            )
            
            # Prepare metadata with JSON-serializable values
            # Convert datetime objects to ISO strings
            upload_info_serializable = {}
            for key, value in upload_result.items():
                if isinstance(value, datetime):
                    upload_info_serializable[key] = value.isoformat()
                else:
                    upload_info_serializable[key] = value
            
            # Save to database
            backup_id = self.db_manager.add_backup_record(
                file_path=file_path,
                original_size=original_size,
                compressed_size=compressed_size,
                encrypted_size=encrypted_size,
                blob_name=blob_name,
                checksum=checksum,
                device_id=self.device_id,
                salt=salt.hex(),  # Store salt as hex string
                metadata={
                    'upload_info': upload_info_serializable,
                    'file_mtime': os.path.getmtime(file_path)
                }
            )
            
            backup_info = {
                'backup_id': backup_id,
                'file_path': file_path,
                'version': version,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'encrypted_size': encrypted_size,
                'blob_name': blob_name,
                'checksum': checksum,
                'compression_ratio': compressed_size / original_size if original_size > 0 else 0,
                'backup_time': datetime.now()
            }
            
            logger.info(f"Successfully backed up: {file_path} (version {version})")
            return backup_info
            
        except Exception as e:
            logger.error(f"Failed to backup file {file_path}: {e}")
            # Update sync status with error
            self.db_manager.update_sync_status(
                file_path, self.device_id, 
                datetime.fromtimestamp(os.path.getmtime(file_path)),
                status='error', error_message=str(e)
            )
            return None
    
    def restore_file(self, backup_id: int, restore_path: str) -> bool:
        """
        Restore a file from backup
        
        Args:
            backup_id: Database ID of the backup record
            restore_path: Path where to restore the file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Starting restore of backup ID {backup_id} to {restore_path}")
            
            # Validate restore path
            if not restore_path or not restore_path.strip():
                logger.error("Restore path is empty or invalid")
                return False
            
            restore_path = restore_path.strip()
            logger.info(f"Normalized restore path: '{restore_path}' (length: {len(restore_path)})")
            
            # Get backup record
            backup_record = self.db_manager.get_backup_by_id(backup_id)
            if not backup_record:
                logger.error(f"Backup record not found: {backup_id}")
                return False
            
            logger.info(f"Found backup record for file: {backup_record['file_path']}")
            
            # Download from Azure
            logger.info(f"Downloading blob: {backup_record['blob_name']}")
            encrypted_data = self.azure_manager.download_blob(backup_record['blob_name'])
            
            # Decrypt data
            salt = bytes.fromhex(backup_record['salt'])
            compressed_data = self.encryption_manager.decrypt_data(encrypted_data, salt)
            
            # Decompress data
            original_data = gzip.decompress(compressed_data)
            
            # Verify checksum
            actual_checksum = self.encryption_manager.generate_data_hash(original_data)
            if actual_checksum != backup_record['checksum']:
                logger.error(f"Checksum mismatch during restore: {backup_id}")
                return False
            
            # Ensure parent directory exists
            restore_dir = os.path.dirname(restore_path)
            if restore_dir:
                logger.info(f"Creating directory if needed: {restore_dir}")
                os.makedirs(restore_dir, exist_ok=True)
            
            # Write to restore path
            logger.info(f"Writing {len(original_data)} bytes to: {restore_path}")
            with open(restore_path, 'wb') as f:
                f.write(original_data)
            
            # Verify the file was written correctly
            if os.path.exists(restore_path):
                written_size = os.path.getsize(restore_path)
                logger.info(f"File written successfully: {written_size} bytes")
            else:
                logger.error(f"File was not created at: {restore_path}")
                return False
            
            logger.info(f"Successfully restored backup {backup_id} to {restore_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore backup {backup_id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def backup_directory(self, directory_path: str) -> Dict[str, Any]:
        """
        Backup all files in a directory
        
        Args:
            directory_path: Path to directory to backup
            
        Returns:
            Dictionary with backup results
        """
        results = {
            'successful_backups': [],
            'failed_backups': [],
            'skipped_files': [],
            'total_files': 0,
            'total_size_backed_up': 0,
            'start_time': datetime.now()
        }
        
        try:
            logger.info(f"Starting directory backup: {directory_path}")
            
            # Walk through directory
            for root, dirs, files in os.walk(directory_path):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    results['total_files'] += 1
                    
                    try:
                        backup_result = self.backup_file(file_path)
                        
                        if backup_result:
                            results['successful_backups'].append(backup_result)
                            results['total_size_backed_up'] += backup_result['original_size']
                        else:
                            results['skipped_files'].append(file_path)
                            
                    except Exception as e:
                        logger.error(f"Error backing up {file_path}: {e}")
                        results['failed_backups'].append({
                            'file_path': file_path,
                            'error': str(e)
                        })
            
            results['end_time'] = datetime.now()
            results['duration'] = (results['end_time'] - results['start_time']).total_seconds()
            
            logger.info(f"Directory backup completed: {len(results['successful_backups'])} successful, "
                       f"{len(results['failed_backups'])} failed, {len(results['skipped_files'])} skipped")
            
            return results
            
        except Exception as e:
            logger.error(f"Directory backup failed: {e}")
            results['error'] = str(e)
            return results
    
    def add_to_backup_queue(self, file_paths: List[str]):
        """Add files to backup queue"""
        with self._backup_lock:
            for file_path in file_paths:
                if file_path not in self._backup_queue:
                    self._backup_queue.append(file_path)
            
            logger.debug(f"Added {len(file_paths)} files to backup queue. Queue size: {len(self._backup_queue)}")
    
    def process_backup_queue(self) -> Dict[str, Any]:
        """Process all files in backup queue"""
        if self._is_backing_up:
            logger.info("Backup already in progress, skipping queue processing")
            return {'status': 'already_running'}
        
        with self._backup_lock:
            if not self._backup_queue:
                logger.debug("Backup queue is empty")
                return {'status': 'empty_queue'}
            
            files_to_backup = self._backup_queue.copy()
            self._backup_queue.clear()
            self._is_backing_up = True
        
        try:
            results = {
                'successful_backups': [],
                'failed_backups': [],
                'skipped_files': [],
                'total_files': len(files_to_backup),
                'start_time': datetime.now()
            }
            
            logger.info(f"Processing backup queue with {len(files_to_backup)} files")
            
            batch_count = 0
            for i in range(0, len(files_to_backup), self.config.batch_size):
                batch = files_to_backup[i:i + self.config.batch_size]
                batch_count += 1
                
                logger.info(f"Processing batch {batch_count} ({len(batch)} files)")
                
                for file_path in batch:
                    if not os.path.exists(file_path):
                        logger.warning(f"File no longer exists: {file_path}")
                        results['skipped_files'].append(file_path)
                        continue
                    
                    backup_result = self.backup_file(file_path)
                    
                    if backup_result:
                        results['successful_backups'].append(backup_result)
                    else:
                        results['skipped_files'].append(file_path)
                
                # Small delay between batches to avoid overwhelming system
                if batch_count < len(files_to_backup) // self.config.batch_size:
                    time.sleep(1)
            
            results['end_time'] = datetime.now()
            results['duration'] = (results['end_time'] - results['start_time']).total_seconds()
            results['status'] = 'completed'
            
            logger.info(f"Backup queue processing completed: {len(results['successful_backups'])} successful, "
                       f"{len(results['failed_backups'])} failed, {len(results['skipped_files'])} skipped")
            
            return results
            
        except Exception as e:
            logger.error(f"Backup queue processing failed: {e}")
            return {'status': 'error', 'error': str(e)}
        
        finally:
            self._is_backing_up = False
    
    def cleanup_old_backups(self) -> Dict[str, int]:
        """Clean up old backup versions"""
        try:
            logger.info("Starting cleanup of old backups")
            
            # Database cleanup
            db_cleaned, db_space_freed = self.db_manager.cleanup_old_versions(
                self.config.max_versions_per_file,
                self.config.retention_days,
                self.device_id
            )
            
            # Azure cleanup (remove blobs older than retention period)
            azure_cleaned = self.azure_manager.cleanup_old_blobs(
                prefix=self.device_id,
                older_than_days=self.config.retention_days
            )
            
            results = {
                'database_records_cleaned': db_cleaned,
                'database_space_freed_bytes': db_space_freed,
                'azure_blobs_cleaned': azure_cleaned
            }
            
            logger.info(f"Cleanup completed: {db_cleaned} DB records, {azure_cleaned} Azure blobs")
            return results
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            raise
    
    def get_backup_status(self) -> Dict[str, Any]:
        """Get current backup status"""
        return {
            'is_backing_up': self._is_backing_up,
            'queue_size': len(self._backup_queue),
            'device_id': self.device_id,
            'storage_stats': self.db_manager.get_storage_stats(self.device_id)
        }
    
