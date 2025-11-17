# Personal Cloud Backup & Versioning System

A secure, automated backup system that compresses, encrypts, and uploads files to Azure Blob Storage while maintaining version history.

## Features

- **Automated File Monitoring**: Real-time detection of file changes using Watchdog
- **Secure Encryption**: AES encryption with unique keys and salts
- **Compression**: Gzip compression to reduce storage costs
- **Version Management**: Maintain multiple versions with configurable retention
- **Azure Integration**: Reliable cloud storage with hierarchical organization
- **Web Dashboard**: User-friendly interface for monitoring and file restoration
- **Scheduled Operations**: Automatic backups, cleanup, and maintenance
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   File Monitor  │───▶│  Backup Engine  │───▶│  Azure Storage  │
│   (Watchdog)    │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       ▼                       │
         │              ┌─────────────────┐              │
         └─────────────▶│   SQLite DB     │◀─────────────┘
                        │   (Metadata)    │
                        └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  Web Dashboard  │
                        │    (Flask)      │
                        └─────────────────┘
```

## Installation

### Prerequisites

- Python 3.8+
- Azure Storage Account
- Operating System: Windows 10+, macOS 10.15+, or Linux

### Quick Setup

1. **Clone or download the project files**

2. **Run the setup script**:
   ```bash
   python setup.py
   ```

3. **Configure environment variables**:
   - Edit `.env` file with your Azure Storage connection string
   - Set the encryption key (generated during setup)
   - Configure device ID

4. **Customize settings** (optional):
   - Edit `config/settings.yaml` to configure watched directories, exclusion patterns, etc.

5. **Start the system**:
   ```bash
   python main.py
   ```

### Manual Installation

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Create required directories**:
   ```bash
   mkdir -p data logs config templates static
   ```

3. **Set environment variables**:
   ```bash
   export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=..."
   export BACKUP_ENCRYPTION_KEY="your-base64-encoded-key"
   export DEVICE_ID="my-computer"
   ```

4. **Generate encryption key**:
   ```python
   python -c "import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
   ```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `AZURE_STORAGE_CONNECTION_STRING` | Yes | Azure Storage connection string |
| `BACKUP_ENCRYPTION_KEY` | Yes | Base64-encoded encryption key |
| `AZURE_CONTAINER_NAME` | No | Container name (default: 'backups') |
| `DEVICE_ID` | No | Unique device identifier (default: 'default-device') |

### Settings File (`config/settings.yaml`)

```yaml
backup:
  watched_directories:
    - ~/Documents
    - ~/Pictures
  exclude_patterns:
    - "*.tmp"
    - "*.log"
    - ".git/*"
  compression_level: 6
  max_file_size_mb: 100
  backup_interval_minutes: 60

versioning:
  max_versions_per_file: 5
  retention_days: 90

web:
  host: 127.0.0.1
  port: 5000
```

## Usage

### Starting the System

```bash
python main.py
```

The system will:
1. Initialize all components
2. Perform an initial scan of watched directories
3. Start real-time file monitoring
4. Launch the web dashboard at `http://127.0.0.1:5000`

### Web Dashboard

Access the web interface at `http://localhost:5000` to:

- **Monitor System Status**: View backup statistics, queue size, and monitoring status
- **Browse Files**: Search and view all backed-up files
- **View File Versions**: See version history for any file
- **Restore Files**: Download previous versions of files
- **Manual Backup**: Add specific files to the backup queue
- **System Settings**: Configure backup parameters

### API Endpoints

The system provides REST API endpoints for programmatic access:

- `GET /api/status` - System status
- `GET /api/files` - List backed-up files
- `POST /api/backup/process` - Process backup queue
- `POST /api/restore/{backup_id}` - Restore specific file version
- `POST /api/cleanup` - Run cleanup operations

### Command Line Operations

```bash
# Check system health
curl http://localhost:5000/health

# Process backup queue
curl -X POST http://localhost:5000/api/backup/process

# Run cleanup
curl -X POST http://localhost:5000/api/cleanup
```

## How It Works

### File Processing Pipeline

1. **Detection**: Watchdog detects file changes
2. **Filtering**: Apply exclude patterns and size limits
3. **Debouncing**: Wait for file stability (default: 5 seconds)
4. **Queuing**: Add files to backup queue
5. **Processing**: Batch process queued files
6. **Compression**: Gzip compress file data
7. **Encryption**: AES encrypt compressed data with unique salt
8. **Upload**: Store in Azure Blob Storage with metadata
9. **Database**: Record backup information and version

### Storage Organization

Azure blobs are organized hierarchically:
```
container/
├── device-id/
│   ├── 2024/
│   │   ├── 01/
│   │   │   ├── Documents/
│   │   │   │   └── file.txt/
│   │   │   │       ├── v1_20240115_143022.backup
│   │   │   │       └── v2_20240116_094511.backup
```

### Version Management

- Each file can have multiple versions
- Configurable retention (default: 5 versions, 90 days)
- Automatic cleanup of old versions
- Metadata tracking for each version

## Security

### Encryption

- **Algorithm**: AES-256 via Fernet (symmetric encryption)
- **Key Derivation**: PBKDF2 with 100,000 iterations
- **Unique Salts**: Each file encrypted with unique salt
- **Key Storage**: Encryption keys stored as environment variables

### Data Integrity

- **Checksums**: SHA-256 hashes verify file integrity
- **Verification**: Checksums validated during restore
- **Metadata**: Comprehensive tracking of file properties

### Access Control

- **Local Access**: Web dashboard bound to localhost by default
- **Authentication**: Can be extended with Flask authentication
- **Azure Security**: Leverages Azure Storage security features

## Monitoring & Maintenance

### Logging

- **File Logging**: Detailed logs in `logs/backup.log`
- **Log Rotation**: Automatic log file rotation
- **Log Levels**: Configurable logging levels

### Health Monitoring

- **Health Endpoint**: `/health` for system status
- **Metrics**: Storage usage, backup statistics
- **Error Tracking**: Failed operations logged and tracked

### Scheduled Tasks

- **Backup Processing**: Every 60 minutes (configurable)
- **Cleanup**: Every 24 hours
- **Database Backup**: Every 6 hours

## Deployment

### As a Service (Linux)

```bash
# Copy service file
sudo cp personal-backup.service /etc/systemd/system/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable personal-backup
sudo systemctl start personal-backup

# Check status
sudo systemctl status personal-backup
```

### As a Service (Windows)

Use Windows Task Scheduler or a service wrapper like NSSM.

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
RUN python setup.py

EXPOSE 5000
CMD ["python", "main.py"]
```

## Troubleshooting

### Common Issues

1. **Azure Connection Failed**
   - Verify connection string
   - Check network connectivity
   - Validate Azure Storage account

2. **Encryption Errors**
   - Ensure encryption key is properly set
   - Check key format (should be base64)

3. **File Monitor Not Working**
   - Check directory permissions
   - Verify watched directories exist
   - Review exclude patterns

4. **High Memory Usage**
   - Reduce batch size in configuration
   - Adjust max file size limit
   - Enable more aggressive cleanup

### Debug Mode

Enable debug logging:

```yaml
logging:
  level: DEBUG
```

Or set environment variable:
```bash
export BACKUP_LOG_LEVEL=DEBUG
```

### Performance Tuning

- **Batch Size**: Adjust `batch_size` for your system
- **Compression Level**: Balance speed vs. storage (1-9)
- **Backup Interval**: Reduce frequency for better performance
- **Exclude Patterns**: Add patterns to skip unnecessary files

## Development

### Project Structure

```
personal-backup/
├── main.py                 # Application entry point
├── setup.py               # Setup and installation script
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── config/
│   ├── config.py         # Configuration management
│   └── settings.yaml     # Configuration file
├── src/
│   ├── database.py       # SQLite operations
│   ├── azure_client.py   # Azure Storage operations
│   ├── encryption.py     # Encryption/decryption
│   ├── backup_engine.py  # Core backup logic
│   ├── file_monitor.py   # File system monitoring
│   └── web_dashboard.py  # Web interface
├── templates/            # HTML templates
├── static/              # CSS/JS assets
├── data/               # Database files
└── logs/               # Log files
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Testing

Run tests with:
```bash
python -m pytest tests/
```

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Support

For support and questions:

1. Check the troubleshooting section
2. Review logs in `logs/backup.log`
3. Open an issue on the project repository
4. Check Azure Storage documentation for cloud-related issues

## Changelog

### Version 1.0.0
- Initial release
- Core backup and restore functionality
- Web dashboard
- Azure Blob Storage integration
- File monitoring with Watchdog
- Version management
- Encryption and compression

---

**Note**: This system is designed for personal use. For enterprise deployments, consider additional security measures, authentication, and monitoring solutions.