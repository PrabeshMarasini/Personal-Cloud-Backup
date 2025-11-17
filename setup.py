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
    """Create basic HTML templates"""
    templates = {
        'templates/base.html': '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Personal Backup System</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">Backup System</a>
            <div class="navbar-nav">
                <a class="nav-link" href="/">Dashboard</a>
                <a class="nav-link" href="/files">Files</a>
                <a class="nav-link" href="/settings">Settings</a>
            </div>
        </div>
    </nav>
    
    <div class="container mt-4">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% block content %}{% endblock %}
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>''',
        
        'templates/dashboard.html': '''{% extends "base.html" %}

{% block content %}
<h1>Backup Dashboard</h1>

<div class="row">
    <div class="col-md-3">
        <div class="card text-white bg-primary">
            <div class="card-body">
                <h5>Total Files</h5>
                <h3>{{ data.storage_stats.total_files or 0 }}</h3>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card text-white bg-success">
            <div class="card-body">
                <h5>Storage Used</h5>
                <h3>{{ "%.1f"|format((data.storage_stats.total_encrypted_size or 0) / 1024 / 1024) }} MB</h3>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card text-white bg-info">
            <div class="card-body">
                <h5>Monitoring</h5>
                <h3>{{ "Active" if data.monitoring_stats.is_monitoring else "Stopped" }}</h3>
            </div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card text-white bg-warning">
            <div class="card-body">
                <h5>Queue Size</h5>
                <h3>{{ data.backup_status.queue_size or 0 }}</h3>
            </div>
        </div>
    </div>
</div>

<div class="mt-4">
    <h3>Recent Backups</h3>
    <div class="table-responsive">
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>File Path</th>
                    <th>Last Backup</th>
                </tr>
            </thead>
            <tbody>
                {% for backup in data.recent_backups %}
                <tr>
                    <td>{{ backup.file_path }}</td>
                    <td>{{ backup.latest_backup }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<div class="mt-4">
    <button class="btn btn-primary" onclick="processBackupQueue()">Process Backup Queue</button>
    <button class="btn btn-secondary" onclick="runCleanup()">Run Cleanup</button>
</div>

<script>
function processBackupQueue() {
    fetch('/api/backup/process', {method: 'POST'})
        .then(response => response.json())
        .then(data => {
            alert('Backup processing completed: ' + (data.successful_backups?.length || 0) + ' files backed up');
            location.reload();
        })
        .catch(error => alert('Error: ' + error));
}

function runCleanup() {
    fetch('/api/cleanup', {method: 'POST'})
        .then(response => response.json())
        .then(data => {
            alert('Cleanup completed: ' + (data.database_records_cleaned || 0) + ' records cleaned');
            location.reload();
        })
        .catch(error => alert('Error: ' + error));
}
</script>
{% endblock %}''',
        
        'templates/files.html': '''{% extends "base.html" %}

{% block content %}
<h1>Backed Up Files</h1>

<div class="mb-3">
    <form method="GET" class="d-flex">
        <input type="text" class="form-control me-2" name="search" placeholder="Search files..." value="{{ search_query or '' }}">
        <button class="btn btn-outline-secondary" type="submit">Search</button>
    </form>
</div>

<div class="table-responsive">
    <table class="table table-striped">
        <thead>
            <tr>
                <th>File Path</th>
                <th>Last Backup</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for file in files %}
            <tr>
                <td>{{ file.file_path }}</td>
                <td>{{ file.latest_backup }}</td>
                <td>
                    <a href="/file/{{ file.file_path | urlencode }}/versions" class="btn btn-sm btn-primary">View Versions</a>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}''',
        
        'templates/error.html': '''{% extends "base.html" %}

{% block content %}
<div class="text-center">
    <h1 class="display-4 text-danger">Error</h1>
    <p class="lead">{{ error }}</p>
    <a href="/" class="btn btn-primary">Go to Dashboard</a>
</div>
{% endblock %}'''
    }
    
    for file_path, content in templates.items():
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Created template: {file_path}")

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