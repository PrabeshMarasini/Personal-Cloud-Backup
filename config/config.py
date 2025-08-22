import os
import yaml
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

class Config:
    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config_path = config_path
        self._config = self._load_config()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration"""
        default_config = {
            'backup': {
                'watched_directories': [
                    os.path.expanduser("~/Documents"),
                    os.path.expanduser("~/Pictures")
                ],
                'exclude_patterns': [
                    '*.tmp', '*.log', '*.cache', '__pycache__/*', 
                    '*.pyc', '.git/*', 'node_modules/*'
                ],
                'compression_level': 6,
                'max_file_size_mb': 100,
                'batch_size': 10,
                'retry_attempts': 3,
                'backup_interval_minutes': 60
            },
            'versioning': {
                'max_versions_per_file': 5,
                'retention_days': 90,
                'cleanup_interval_hours': 24
            },
            'database': {
                'path': 'data/backup.db',
                'backup_db_interval_hours': 6
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/backup.log',
                'max_size_mb': 10,
                'backup_count': 5
            },
            'web': {
                'host': '127.0.0.1',
                'port': 5000,
                'debug': False
            },
            'encryption': {
                'key_derivation_iterations': 100000
            }
        }
        
        # Save default config
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)
        
        return default_config
    
    @property
    def azure_connection_string(self) -> str:
        return os.getenv('AZURE_STORAGE_CONNECTION_STRING', '')
    
    @property
    def azure_container_name(self) -> str:
        return os.getenv('AZURE_CONTAINER_NAME', 'backups')
    
    @property
    def encryption_key(self) -> str:
        return os.getenv('BACKUP_ENCRYPTION_KEY', '')
    
    @property
    def device_id(self) -> str:
        return os.getenv('DEVICE_ID', 'default-device')
    
    @property
    def watched_directories(self) -> List[str]:
        return self._config['backup']['watched_directories']
    
    @property
    def exclude_patterns(self) -> List[str]:
        return self._config['backup']['exclude_patterns']
    
    @property
    def compression_level(self) -> int:
        return self._config['backup']['compression_level']
    
    @property
    def max_file_size_mb(self) -> int:
        return self._config['backup']['max_file_size_mb']
    
    @property
    def batch_size(self) -> int:
        return self._config['backup']['batch_size']
    
    @property
    def retry_attempts(self) -> int:
        return self._config['backup']['retry_attempts']
    
    @property
    def backup_interval_minutes(self) -> int:
        return self._config['backup']['backup_interval_minutes']
    
    @property
    def max_versions_per_file(self) -> int:
        return self._config['versioning']['max_versions_per_file']
    
    @property
    def retention_days(self) -> int:
        return self._config['versioning']['retention_days']
    
    @property
    def cleanup_interval_hours(self) -> int:
        return self._config['versioning']['cleanup_interval_hours']
    
    @property
    def database_path(self) -> str:
        return self._config['database']['path']
    
    @property
    def logging_level(self) -> str:
        return self._config['logging']['level']
    
    @property
    def logging_file(self) -> str:
        return self._config['logging']['file']
    
    @property
    def web_host(self) -> str:
        return self._config['web']['host']
    
    @property
    def web_port(self) -> int:
        return self._config['web']['port']
    
    @property
    def web_debug(self) -> bool:
        return self._config['web']['debug']

# Global config instance
config = Config()