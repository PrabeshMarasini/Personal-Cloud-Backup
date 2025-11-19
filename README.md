# Personal Cloud Backup System

Automatically backup your files to Azure Cloud Storage with encryption and version history.

## What It Does

- Watches your folders and backs up files when they change
- Encrypts and compresses files before uploading to Azure
- Keeps multiple versions of your files
- Web interface to view and restore files

## Requirements

- Windows 10 or newer
- Python 3.8+
- Azure Storage Account

## Quick Setup

1. **Install Python dependencies**:
   ```cmd
   pip install -r requirements.txt
   ```

2. **Run setup**:
   ```cmd
   python setup.py
   ```

3. **Edit the `.env` file** with your Azure connection string:
   ```
   AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
   ```

4. **Start the backup system**:
   ```cmd
   python main.py
   ```

5. **Open web interface**: Go to `http://localhost:5000`

## Configuration

Edit `config/settings.yaml` to change what folders to backup:

```yaml
backup:
  watched_directories:
    - C:\Users\YourName\Documents
    - C:\Users\YourName\Pictures
  exclude_patterns:
    - "*.tmp"
    - "*.log"
  max_file_size_mb: 100

versioning:
  max_versions_per_file: 5
  retention_days: 90
```

## Using the Web Interface

- **Dashboard**: See backup status and statistics
- **Files**: Browse all backed up files
- **Versions**: View different versions of each file
- **Restore**: Download previous versions of files

## How to Restore Files

1. Go to the Files page
2. Click "Versions" next to any file
3. Click "Restore" next to the version you want
4. Choose where to save the restored file
5. Click "Restore File"

## Troubleshooting

**Can't connect to Azure?**
- Check your connection string in `.env`
- Make sure your Azure Storage account is active

**Files not backing up?**
- Check the watched directories in `config/settings.yaml`
- Look at logs in the `logs/` folder

**Web interface won't load?**
- Make sure nothing else is using port 5000
- Try `http://127.0.0.1:5000` instead

## File Structure

```
personal-backup/
├── main.py              # Start here
├── setup.py            # Setup script
├── .env                # Your Azure settings
├── config/settings.yaml # Backup configuration
├── data/               # Database files
├── logs/               # Log files
└── src/                # Program files
```