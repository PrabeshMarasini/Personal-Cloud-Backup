import os
import io
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, BinaryIO
import logging
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import AzureError, ResourceNotFoundError

logger = logging.getLogger(__name__)

class AzureStorageManager:
    def __init__(self, connection_string: str, container_name: str):
        self.connection_string = connection_string
        self.container_name = container_name
        self.blob_service_client = None
        self.container_client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Azure blob service client"""
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                self.connection_string
            )
            self.container_client = self.blob_service_client.get_container_client(
                self.container_name
            )
            
            # Create container if it doesn't exist
            try:
                self.container_client.create_container()
                logger.info(f"Created container: {self.container_name}")
            except ResourceNotFoundError:
                pass  # Container already exists
            except Exception as e:
                logger.warning(f"Container creation warning: {e}")
                
        except Exception as e:
            logger.error(f"Failed to initialize Azure client: {e}")
            raise
    
    def upload_blob(self, blob_name: str, data: bytes, 
                   metadata: Dict[str, str] = None, 
                   overwrite: bool = True) -> Dict[str, Any]:
        """
        Upload data as blob to Azure Storage
        
        Args:
            blob_name: Name of the blob
            data: Binary data to upload
            metadata: Optional metadata dictionary
            overwrite: Whether to overwrite existing blob
            
        Returns:
            Dict with upload information
        """
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Upload with metadata
            upload_result = blob_client.upload_blob(
                data, 
                overwrite=overwrite,
                metadata=metadata or {}
            )
            
            # Get blob properties for return info
            properties = blob_client.get_blob_properties()
            
            logger.info(f"Successfully uploaded blob: {blob_name} ({len(data)} bytes)")
            
            return {
                'blob_name': blob_name,
                'size': len(data),
                'etag': upload_result['etag'],
                'last_modified': properties.last_modified,
                'url': blob_client.url,
                'metadata': properties.metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to upload blob {blob_name}: {e}")
            raise
    
    def download_blob(self, blob_name: str) -> bytes:
        """Download blob data"""
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_data = blob_client.download_blob().readall()
            
            logger.info(f"Successfully downloaded blob: {blob_name} ({len(blob_data)} bytes)")
            return blob_data
            
        except ResourceNotFoundError:
            logger.error(f"Blob not found: {blob_name}")
            raise
        except Exception as e:
            logger.error(f"Failed to download blob {blob_name}: {e}")
            raise
    
    def download_blob_to_stream(self, blob_name: str, stream: BinaryIO) -> int:
        """Download blob data to a stream"""
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_data = blob_client.download_blob()
            
            bytes_written = 0
            for chunk in blob_data.chunks():
                stream.write(chunk)
                bytes_written += len(chunk)
            
            logger.info(f"Downloaded blob {blob_name} to stream ({bytes_written} bytes)")
            return bytes_written
            
        except Exception as e:
            logger.error(f"Failed to download blob {blob_name} to stream: {e}")
            raise
    
    def get_blob_properties(self, blob_name: str) -> Dict[str, Any]:
        """Get blob properties and metadata"""
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            properties = blob_client.get_blob_properties()
            
            return {
                'name': blob_name,
                'size': properties.size,
                'last_modified': properties.last_modified,
                'etag': properties.etag,
                'content_type': properties.content_settings.content_type,
                'metadata': properties.metadata or {},
                'creation_time': properties.creation_time,
                'blob_type': properties.blob_type
            }
            
        except ResourceNotFoundError:
            logger.error(f"Blob not found: {blob_name}")
            return None
        except Exception as e:
            logger.error(f"Failed to get blob properties {blob_name}: {e}")
            raise
    
    def delete_blob(self, blob_name: str) -> bool:
        """Delete a blob"""
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_client.delete_blob()
            
            logger.info(f"Successfully deleted blob: {blob_name}")
            return True
            
        except ResourceNotFoundError:
            logger.warning(f"Blob not found for deletion: {blob_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete blob {blob_name}: {e}")
            raise
    
    def list_blobs(self, prefix: str = None, limit: int = None) -> List[Dict[str, Any]]:
        """List blobs in container with optional prefix filter"""
        try:
            blobs = []
            blob_list = self.container_client.list_blobs(
                name_starts_with=prefix
            )
            
            for blob in blob_list:
                blobs.append({
                    'name': blob.name,
                    'size': blob.size,
                    'last_modified': blob.last_modified,
                    'etag': blob.etag,
                    'content_type': blob.content_settings.content_type if blob.content_settings else None,
                    'metadata': blob.metadata or {}
                })
                
                if limit and len(blobs) >= limit:
                    break
            
            logger.info(f"Listed {len(blobs)} blobs with prefix '{prefix or 'all'}'")
            return blobs
            
        except Exception as e:
            logger.error(f"Failed to list blobs: {e}")
            raise
    
    def blob_exists(self, blob_name: str) -> bool:
        """Check if blob exists"""
        try:
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_client.get_blob_properties()
            return True
        except ResourceNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking blob existence {blob_name}: {e}")
            raise
    
    def generate_blob_name(self, device_id: str, file_path: str, 
                          version: int, timestamp: datetime = None) -> str:
        """Generate standardized blob name"""
        if timestamp is None:
            timestamp = datetime.now()
        
        # Sanitize file path for blob name
        sanitized_path = file_path.replace('\\', '/').replace(':', '_').lstrip('/')
        
        # Create hierarchical structure: device_id/year/month/file_path/version_timestamp
        blob_name = f"{device_id}/{timestamp.year}/{timestamp.month:02d}/{sanitized_path}/v{version}_{timestamp.strftime('%Y%m%d_%H%M%S')}.backup"
        
        return blob_name
    
    def get_storage_usage(self, prefix: str = None) -> Dict[str, Any]:
        """Get storage usage statistics"""
        try:
            total_size = 0
            total_count = 0
            
            blob_list = self.container_client.list_blobs(
                name_starts_with=prefix
            )
            
            for blob in blob_list:
                total_size += blob.size
                total_count += 1
            
            return {
                'total_blobs': total_count,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'total_size_gb': round(total_size / (1024 * 1024 * 1024), 2)
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage usage: {e}")
            raise
    
    def cleanup_old_blobs(self, prefix: str, older_than_days: int) -> int:
        """Delete blobs older than specified days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=older_than_days)
            deleted_count = 0
            
            blob_list = self.container_client.list_blobs(
                name_starts_with=prefix
            )
            
            for blob in blob_list:
                if blob.last_modified < cutoff_date:
                    try:
                        self.delete_blob(blob.name)
                        deleted_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to delete old blob {blob.name}: {e}")
            
            logger.info(f"Cleaned up {deleted_count} old blobs")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old blobs: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test Azure storage connection"""
        try:
            # Try to get container properties
            properties = self.container_client.get_container_properties()
            logger.info(f"Azure connection test successful. Container: {properties.name}")
            return True
        except Exception as e:
            logger.error(f"Azure connection test failed: {e}")
            return False


def create_azure_manager(connection_string: str = None, container_name: str = None) -> AzureStorageManager:
    """Factory function to create Azure storage manager"""
    if not connection_string or not container_name:
        from config.config import config
        connection_string = connection_string or config.azure_connection_string
        container_name = container_name or config.azure_container_name
    
    if not connection_string:
        raise ValueError("Azure connection string not provided")
    if not container_name:
        raise ValueError("Azure container name not provided")
    
    return AzureStorageManager(connection_string, container_name)