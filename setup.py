#!/usr/bin/env python3
"""
Setup script for Personal Cloud Backup System
"""

import os
import sys
from pathlib import Path

def setup_directories():
    """Create necessary directories"""
    directories = [
        'data',
        'logs',
        'config',
        'templates',
        'static',
        'static/css',
        'static/js',
        'temp'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"Created directory: {directory}")

def generate_encryption_key():
    """Generate and display encryption key"""
    import base64
    key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    print(f"\nGenerated encryption key: {key}")
    print("Add this to your .env file as BACKUP_ENCRYPTION_KEY")
    return key

def create_env_file():
    """Create .env file from template"""
    if os.path.exists('.env'):
        print(".env file already exists, skipping creation")
        return
    
    if os.path.exists('.env.example'):
        import shutil
        shutil.copy('.env.example', '.env')
        print("Created .env file from template")
        print("Please edit .env file with your configuration")
    else:
        print("No .env.example found, please create .env manually")

def install_requirements():
    """Install Python requirements"""
    try:
        import subprocess
        result = subprocess.run([
            sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'
        ], check=True, capture_output=True, text=True)
        print("Requirements installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"Failed to install requirements: {e}")
        print("Please run: pip install -r requirements.txt")

def create_service_file():
    """Create systemd service file for Linux"""
    if sys.platform != 'linux':
        return
    
    current_dir = os.getcwd()
    python_path = sys.executable
    
    service_content = f"""[Unit]
Description=Personal Cloud Backup System
After=network.target

[Service]
Type=simple
User={os.getenv('USER', 'backup')}
WorkingDirectory={current_dir}
ExecStart={python_path} main.py
Restart=always
RestartSec=10
Environment=PYTHONPATH={current_dir}
EnvironmentFile={current_dir}/.env

[Install]
WantedBy=multi-user.target
"""
    
    service_path = 'personal-backup.service'
    with open(service_path, 'w') as f:
        f.write(service_content)
    
    print(f"Created systemd service file: {service_path}")
    print("To install the service:")
    print(f"  sudo cp {service_path} /etc/systemd/system/")
    print("  sudo systemctl daemon-reload")
    print("  sudo systemctl enable personal-backup")
    print("  sudo systemctl start personal-backup")

def create_basic_templates():
    """Create basic HTML templates and static assets"""
    import shutil
    
    # Check if templates already exist (they should after extraction)
    template_files = [
        'templates/base.html',
        'templates/dashboard.html', 
        'templates/files.html',
        'templates/error.html',
        'templates/file_versions.html',
        'templates/restore.html',
        'templates/manual_backup.html',
        'templates/settings.html'
    ]
    
    static_files = [
        'static/css/main.css',
        'static/js/dashboard.js',
        'static/js/settings.js'
    ]
    
    # Only create templates if they don't exist
    missing_templates = [f for f in template_files if not os.path.exists(f)]
    missing_static = [f for f in static_files if not os.path.exists(f)]
    
    if missing_templates:
        print(f"Warning: Missing template files: {missing_templates}")
        print("Templates should be extracted from setup.py to separate files")
    else:
        print("All template files found")
        
    if missing_static:
        print(f"Warning: Missing static files: {missing_static}")
        print("Static assets should be extracted from templates to separate files")
    else:
        print("All static files found")
    
    # Ensure directories exist
    for template_file in template_files:
        os.makedirs(os.path.dirname(template_file), exist_ok=True)
    
    for static_file in static_files:
        os.makedirs(os.path.dirname(static_file), exist_ok=True)

def main():
    """Main setup function"""
    print("Setting up Personal Cloud Backup System...")
    print("=" * 50)
    
    # Create directories
    setup_directories()
    
    # Create basic templates
    create_basic_templates()
    
    # Generate encryption key
    encryption_key = generate_encryption_key()
    
    # Create .env file
    create_env_file()
    
    # Install requirements
    if input("\nInstall Python requirements? (y/n): ").lower() == 'y':
        install_requirements()
    
    # Create service file for Linux
    if sys.platform == 'linux':
        if input("Create systemd service file? (y/n): ").lower() == 'y':
            create_service_file()
    
    print("\nSetup completed!")
    print("\nNext steps:")
    print("1. Edit .env file with your Azure Storage connection string")
    print("2. Set BACKUP_ENCRYPTION_KEY in .env to the generated key above")
    print("3. Configure watched directories in config/settings.yaml")
    print("4. Run: python main.py")
    print("\nWeb dashboard will be available at: http://127.0.0.1:5000")

if __name__ == "__main__":
    main()