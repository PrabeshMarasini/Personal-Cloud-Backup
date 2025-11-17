import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import logging
import json

logger = logging.getLogger(__name__)

def serialize_for_json(obj: Any) -> Any:
    """Convert objects to JSON-serializable format"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Create database and tables if they don't exist"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    original_size INTEGER NOT NULL,
                    compressed_size INTEGER NOT NULL,
                    encrypted_size INTEGER NOT NULL,
                    blob_name TEXT NOT NULL,
                    backup_date DATETIME NOT NULL,
                    checksum TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    device_id TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    metadata TEXT,
                    is_deleted BOOLEAN DEFAULT FALSE,
                    UNIQUE(file_path, version, device_id)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS sync_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    last_modified DATETIME NOT NULL,
                    last_backup DATETIME,
                    status TEXT DEFAULT 'pending',
                    error_message TEXT,
                    device_id TEXT NOT NULL,
                    UNIQUE(file_path, device_id)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cleanup_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cleanup_date DATETIME NOT NULL,
                    files_cleaned INTEGER DEFAULT 0,
                    space_freed_bytes INTEGER DEFAULT 0,
                    errors_count INTEGER DEFAULT 0
                )
            ''')
            
            # Create indexes for better performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_backups_file_path ON backups(file_path)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_backups_backup_date ON backups(backup_date)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_backups_device_id ON backups(device_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_sync_status_file_path ON sync_status(file_path)')
            
            conn.commit()
            logger.info("Database initialized successfully")
    
    def add_backup_record(self, file_path: str, original_size: int, compressed_size: int,
                         encrypted_size: int, blob_name: str, checksum: str, 
                         device_id: str, salt: str, metadata: Dict = None) -> int:
        """Add a new backup record"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get next version number
                version = self.get_next_version(file_path, device_id)
                
                # Insert backup record
                cursor = conn.execute('''
                    INSERT INTO backups 
                    (file_path, original_size, compressed_size, encrypted_size, blob_name, 
                     backup_date, checksum, version, device_id, salt, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (file_path, original_size, compressed_size, encrypted_size, blob_name,
                      datetime.now().isoformat(), checksum, version, device_id, salt,
                      json.dumps(serialize_for_json(metadata)) if metadata else None))
                
                backup_id = cursor.lastrowid
                
                # Update sync status
                conn.execute('''
                    INSERT OR REPLACE INTO sync_status 
                    (file_path, last_modified, last_backup, status, device_id)
                    VALUES (?, ?, ?, 'completed', ?)
                ''', (file_path, datetime.now().isoformat(), 
                      datetime.now().isoformat(), device_id))
                
                conn.commit()
                logger.info(f"Added backup record for {file_path}, version {version}")
                return backup_id
                
        except Exception as e:
            logger.error(f"Failed to add backup record: {e}")
            raise
    
    def get_next_version(self, file_path: str, device_id: str) -> int:
        """Get the next version number for a file"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT MAX(version) FROM backups 
                WHERE file_path = ? AND device_id = ? AND is_deleted = FALSE
            ''', (file_path, device_id))
            
            result = cursor.fetchone()
            return (result[0] or 0) + 1
    
    def get_file_versions(self, file_path: str, device_id: str) -> List[Dict[str, Any]]:
        """Get all versions of a file"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM backups 
                WHERE file_path = ? AND device_id = ? AND is_deleted = FALSE
                ORDER BY version DESC
            ''', (file_path, device_id))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_latest_backup(self, file_path: str, device_id: str) -> Optional[Dict[str, Any]]:
        """Get the latest backup for a file"""
        versions = self.get_file_versions(file_path, device_id)
        return versions[0] if versions else None
    
    def get_backup_by_id(self, backup_id: int) -> Optional[Dict[str, Any]]:
        """Get backup record by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT * FROM backups WHERE id = ? AND is_deleted = FALSE
            ''', (backup_id,))
            
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def get_files_needing_backup(self, device_id: str) -> List[str]:
        """Get files that need backup (modified after last backup)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT file_path FROM sync_status 
                WHERE device_id = ? AND (
                    status = 'pending' OR 
                    last_modified > last_backup OR
                    last_backup IS NULL
                )
            ''', (device_id,))
            
            return [row[0] for row in cursor.fetchall()]
    
    def update_sync_status(self, file_path: str, device_id: str, 
                          last_modified: datetime, status: str = 'pending',
                          error_message: str = None):
        """Update sync status for a file"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO sync_status 
                    (file_path, last_modified, status, error_message, device_id)
                    VALUES (?, ?, ?, ?, ?)
                ''', (file_path, last_modified.isoformat(), status, error_message, device_id))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to update sync status: {e}")
            raise
    
    def cleanup_old_versions(self, max_versions: int, retention_days: int, device_id: str) -> Tuple[int, int]:
        """Clean up old backup versions"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get files with more than max_versions
                cursor = conn.execute('''
                    SELECT file_path, COUNT(*) as version_count 
                    FROM backups 
                    WHERE device_id = ? AND is_deleted = FALSE
                    GROUP BY file_path 
                    HAVING version_count > ?
                ''', (device_id, max_versions))
                
                files_to_clean = cursor.fetchall()
                cleaned_count = 0
                space_freed = 0
                
                for file_path, version_count in files_to_clean:
                    # Keep only the latest max_versions
                    cursor = conn.execute('''
                        SELECT id, encrypted_size FROM backups 
                        WHERE file_path = ? AND device_id = ? AND is_deleted = FALSE
                        ORDER BY version DESC 
                        LIMIT -1 OFFSET ?
                    ''', (file_path, device_id, max_versions))
                    
                    old_versions = cursor.fetchall()
                    
                    for backup_id, encrypted_size in old_versions:
                        conn.execute('UPDATE backups SET is_deleted = TRUE WHERE id = ?', (backup_id,))
                        cleaned_count += 1
                        space_freed += encrypted_size
                
                # Also clean up versions older than retention_days
                cutoff_date = (datetime.now() - timedelta(days=retention_days)).isoformat()
                cursor = conn.execute('''
                    SELECT id, encrypted_size FROM backups 
                    WHERE device_id = ? AND backup_date < ? AND is_deleted = FALSE
                ''', (device_id, cutoff_date))
                
                old_backups = cursor.fetchall()
                for backup_id, encrypted_size in old_backups:
                    conn.execute('UPDATE backups SET is_deleted = TRUE WHERE id = ?', (backup_id,))
                    cleaned_count += 1
                    space_freed += encrypted_size
                
                # Log cleanup
                conn.execute('''
                    INSERT INTO cleanup_log (cleanup_date, files_cleaned, space_freed_bytes)
                    VALUES (?, ?, ?)
                ''', (datetime.now().isoformat(), cleaned_count, space_freed))
                
                conn.commit()
                logger.info(f"Cleaned up {cleaned_count} old versions, freed {space_freed} bytes")
                
                return cleaned_count, space_freed
                
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            raise
    
    def get_storage_stats(self, device_id: str) -> Dict[str, Any]:
        """Get storage statistics"""
        with sqlite3.connect(self.db_path) as conn:
            # Total storage used
            cursor = conn.execute('''
                SELECT 
                    COUNT(*) as total_files,
                    SUM(original_size) as total_original_size,
                    SUM(encrypted_size) as total_encrypted_size,
                    AVG(CASE WHEN original_size > 0 THEN compressed_size * 1.0 / original_size ELSE 0 END) as avg_compression_ratio
                FROM backups 
                WHERE device_id = ? AND is_deleted = FALSE
            ''', (device_id,))
            
            stats = cursor.fetchone()
            
            # Files by date
            cursor = conn.execute('''
                SELECT DATE(backup_date) as date, COUNT(*) as count
                FROM backups 
                WHERE device_id = ? AND is_deleted = FALSE
                GROUP BY DATE(backup_date)
                ORDER BY date DESC
                LIMIT 30
            ''', (device_id,))
            
            daily_stats = cursor.fetchall()
            
            return {
                'total_files': stats[0] or 0,
                'total_original_size': stats[1] or 0,
                'total_encrypted_size': stats[2] or 0,
                'avg_compression_ratio': stats[3] or 0,
                'daily_backup_counts': dict(daily_stats)
            }
    
    def search_backups(self, query: str, device_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search backups by file path"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT DISTINCT file_path, MAX(backup_date) as latest_backup
                FROM backups 
                WHERE file_path LIKE ? AND device_id = ? AND is_deleted = FALSE
                GROUP BY file_path
                ORDER BY latest_backup DESC
                LIMIT ?
            ''', (f'%{query}%', device_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_storage_stats(self, device_id: str) -> Dict[str, Any]:
        """Get storage statistics for a device"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get overall statistics
                cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as total_files,
                        COUNT(DISTINCT file_path) as unique_files,
                        SUM(original_size) as total_original_size,
                        SUM(compressed_size) as total_compressed_size,
                        SUM(encrypted_size) as total_encrypted_size,
                        AVG(compressed_size * 1.0 / original_size) as avg_compression_ratio
                    FROM backups 
                    WHERE device_id = ? AND is_deleted = FALSE
                ''', (device_id,))
                
                stats = dict(cursor.fetchone())
                
                # Handle null values
                for key, value in stats.items():
                    if value is None:
                        stats[key] = 0
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {
                'total_files': 0,
                'unique_files': 0,
                'total_original_size': 0,
                'total_compressed_size': 0,
                'total_encrypted_size': 0,
                'avg_compression_ratio': 0
            }

def create_database_manager(db_path: str = None) -> DatabaseManager:
    """Factory function to create database manager"""
    if not db_path:
        from config.config import config
        db_path = config.database_path
    
    return DatabaseManager(db_path)