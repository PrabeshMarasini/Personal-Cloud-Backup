import os
import json
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
import tempfile
import logging

from .database import DatabaseManager
from .azure_client import AzureStorageManager
from .backup_engine import BackupEngine
from .file_monitoring import FileMonitor

logger = logging.getLogger(__name__)

class RestoreProgressTracker:
    """Track progress of restore operations"""
    
    def __init__(self):
        self.progress_data = {}
        self.lock = threading.Lock()
    
    def create_progress(self, restore_id: str) -> str:
        """Create a new progress tracker"""
        with self.lock:
            self.progress_data[restore_id] = {
                'percent': 0,
                'step': 'Initializing restore...',
                'message': 'Preparing restore operation...',
                'status': 'running',
                'error': None,
                'created_at': time.time()
            }
        return restore_id
    
    def update_progress(self, restore_id: str, percent: int, step: str, message: str):
        """Update progress for a restore operation"""
        with self.lock:
            if restore_id in self.progress_data:
                self.progress_data[restore_id].update({
                    'percent': percent,
                    'step': step,
                    'message': message,
                    'status': 'running'
                })
                logger.debug(f"Progress updated for {restore_id}: {percent}% - {step}")
            else:
                logger.warning(f"Attempted to update progress for unknown restore ID: {restore_id}")
    
    def complete_progress(self, restore_id: str, success: bool, error: str = None):
        """Mark progress as complete"""
        with self.lock:
            if restore_id in self.progress_data:
                self.progress_data[restore_id].update({
                    'percent': 100 if success else self.progress_data[restore_id]['percent'],
                    'status': 'completed' if success else 'failed',
                    'error': error
                })
    
    def get_progress(self, restore_id: str) -> Dict[str, Any]:
        """Get progress data for a restore operation"""
        with self.lock:
            return self.progress_data.get(restore_id, {})
    
    def cleanup_old_progress(self, max_age_seconds: int = 3600):
        """Clean up old progress data"""
        current_time = time.time()
        with self.lock:
            to_remove = []
            for restore_id, data in self.progress_data.items():
                if current_time - data['created_at'] > max_age_seconds:
                    to_remove.append(restore_id)
            
            for restore_id in to_remove:
                del self.progress_data[restore_id]

# Global progress tracker
progress_tracker = RestoreProgressTracker()

def create_web_app(db_manager: DatabaseManager, azure_manager: AzureStorageManager,
                   backup_engine: BackupEngine, file_monitor: FileMonitor,
                   device_id: str) -> Flask:
    """Create and configure Flask web application"""
    
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.secret_key = os.urandom(24)
    
    # Store managers in app config
    app.config['db_manager'] = db_manager
    app.config['azure_manager'] = azure_manager
    app.config['backup_engine'] = backup_engine
    app.config['file_monitor'] = file_monitor
    app.config['device_id'] = device_id
    
    # Custom template filter for datetime formatting
    @app.template_filter('format_datetime')
    def format_datetime(value):
        """Format datetime string to readable format"""
        if not value:
            return 'Never'
        
        try:
            # Parse the datetime string
            if isinstance(value, str):
                # Handle ISO format with microseconds
                if 'T' in value:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                else:
                    dt = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            else:
                dt = value
            
            # Format as date and time
            date_str = dt.strftime('%Y-%m-%d')
            time_str = dt.strftime('%I:%M:%S %p')  # 12-hour format with AM/PM
            
            return f"{date_str}<br><small class='text-gray-400'>{time_str}</small>"
        except Exception as e:
            logger.error(f"Error formatting datetime {value}: {e}")
            return str(value)
    
    # Mark the filter as safe for HTML
    app.jinja_env.filters['format_datetime'] = format_datetime
    
    @app.route('/')
    def dashboard():
        """Main dashboard page"""
        try:
            # Get backup statistics
            storage_stats = db_manager.get_storage_stats(device_id)
            monitoring_stats = file_monitor.get_monitoring_stats()
            backup_status = backup_engine.get_backup_status()
            
            # Get recent backups
            recent_backups = db_manager.search_backups('', device_id, limit=10)
            
            dashboard_data = {
                'storage_stats': storage_stats,
                'monitoring_stats': monitoring_stats,
                'backup_status': backup_status,
                'recent_backups': recent_backups,
                'device_id': device_id
            }
            
            return render_template('dashboard.html', data=dashboard_data)
            
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            flash(f"Error loading dashboard: {e}", 'error')
            return render_template('error.html', error=str(e))
    
    @app.route('/api/status')
    def api_status():
        """Get system status via API"""
        try:
            # Get stats with proper error handling
            try:
                storage_stats = db_manager.get_storage_stats(device_id)
            except Exception:
                storage_stats = {'total_files': 0, 'total_encrypted_size': 0}
            
            try:
                monitoring_stats = file_monitor.get_monitoring_stats()
            except Exception:
                monitoring_stats = {'is_monitoring': False}
            
            try:
                backup_status = backup_engine.get_backup_status()
            except Exception:
                backup_status = {'queue_size': 0}
            
            return jsonify({
                'storage_stats': storage_stats,
                'monitoring_stats': monitoring_stats,
                'backup_status': backup_status,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/files')
    def files_list():
        """List backed up files"""
        try:
            search_query = request.args.get('search', '')
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 50))
            
            # Search files
            if search_query:
                files = db_manager.search_backups(search_query, device_id, limit=per_page)
            else:
                files = db_manager.search_backups('', device_id, limit=per_page)
            
            return render_template('files.html', files=files, search_query=search_query)
            
        except Exception as e:
            logger.error(f"Files list error: {e}")
            flash(f"Error loading files: {e}", 'error')
            return redirect(url_for('dashboard'))
    
    @app.route('/api/files')
    def api_files():
        """Get files list via API"""
        try:
            search_query = request.args.get('search', '')
            limit = int(request.args.get('limit', 50))
            
            files = db_manager.search_backups(search_query, device_id, limit=limit)
            return jsonify({'files': files})
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/file/<path:file_path>/versions')
    def file_versions(file_path):
        """Show versions for a specific file"""
        try:
            versions = db_manager.get_file_versions(file_path, device_id)
            
            if not versions:
                flash(f"No versions found for file: {file_path}", 'warning')
                return redirect(url_for('files_list'))
            
            return render_template('file_versions.html', file_path=file_path, versions=versions)
            
        except Exception as e:
            logger.error(f"File versions error: {e}")
            flash(f"Error loading file versions: {e}", 'error')
            return redirect(url_for('files_list'))
    
    @app.route('/api/file/<path:file_path>/versions')
    def api_file_versions(file_path):
        """Get file versions via API"""
        try:
            versions = db_manager.get_file_versions(file_path, device_id)
            return jsonify({'file_path': file_path, 'versions': versions})
            
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    @app.route('/restore/<int:backup_id>', methods=['GET', 'POST'])
    def restore_file_page(backup_id):
        """Show restore file page or handle restore request"""
        try:
            backup_record = db_manager.get_backup_by_id(backup_id)
            
            if not backup_record:
                flash(f"Backup record not found: {backup_id}", 'error')
                return redirect(url_for('files_list'))
            
            if request.method == 'GET':
                logger.info(f"Backup record file_path: '{backup_record['file_path']}'")
                return render_template('restore.html', backup=backup_record)
            
            # Handle POST request for restore
            logger.info(f"Form data received: {dict(request.form)}")
            restore_path = request.form.get('restore_path')
            overwrite = request.form.get('overwrite') == 'on'
            create_backup = request.form.get('create_backup') == 'on'
            
            logger.info(f"Raw restore_path from form: '{restore_path}'")
            logger.info(f"Restore path type: {type(restore_path)}")
            logger.info(f"Restore path repr: {repr(restore_path)}")
            
            if not restore_path:
                flash('Restore path is required', 'error')
                return render_template('restore.html', backup=backup_record)
            
            # Validate restore path
            restore_dir = os.path.dirname(restore_path)
            if restore_dir and not os.path.exists(restore_dir):
                try:
                    os.makedirs(restore_dir, exist_ok=True)
                except Exception as e:
                    flash(f'Could not create directory {restore_dir}: {e}', 'error')
                    return render_template('restore.html', backup=backup_record)
            
            # Check if file exists and handle overwrite
            if os.path.exists(restore_path) and not overwrite:
                flash('File already exists. Check "Overwrite existing file" to replace it.', 'warning')
                return render_template('restore.html', backup=backup_record)
            
            # Create backup of existing file if requested
            if create_backup and os.path.exists(restore_path):
                backup_path = f"{restore_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                try:
                    import shutil
                    shutil.copy2(restore_path, backup_path)
                    flash(f'Created backup of existing file: {backup_path}', 'info')
                except Exception as e:
                    flash(f'Warning: Could not create backup: {e}', 'warning')
            
            # Debug logging
            logger.info(f"Attempting to restore backup {backup_id} to path: '{restore_path}'")
            logger.info(f"Restore path length: {len(restore_path)}")
            
            # Check if this is an AJAX request (progress tracking)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Start restore in background thread with progress tracking
                restore_id = str(uuid.uuid4())
                progress_tracker.create_progress(restore_id)
                
                def restore_with_progress():
                    def progress_callback(percent, step, message):
                        logger.info(f"Progress update: {percent}% - {step} - {message}")
                        progress_tracker.update_progress(restore_id, percent, step, message)
                        # Add small delay to ensure progress is visible
                        time.sleep(0.2)
                    
                    try:
                        logger.info(f"Starting background restore for backup {backup_id}")
                        success = backup_engine.restore_file(backup_id, restore_path, progress_callback)
                        logger.info(f"Background restore completed: {success}")
                        progress_tracker.complete_progress(restore_id, success)
                    except Exception as e:
                        logger.error(f"Background restore failed: {e}")
                        progress_tracker.complete_progress(restore_id, False, str(e))
                
                # Start restore in background
                thread = threading.Thread(target=restore_with_progress)
                thread.daemon = True
                thread.start()
                
                # Give the thread a moment to start
                time.sleep(0.1)
                
                return jsonify({'restore_id': restore_id})
            
            # Perform the restore (synchronous for non-AJAX requests)
            success = backup_engine.restore_file(backup_id, restore_path)
            
            if success:
                flash(f'File successfully restored to: {restore_path}', 'success')
                return redirect(url_for('files_list'))
            else:
                flash('Restore failed. Please check the logs for details.', 'error')
                return render_template('restore.html', backup=backup_record)
            
        except Exception as e:
            logger.error(f"Restore page error: {e}")
            flash(f"Error during restore: {e}", 'error')
            return render_template('restore.html', backup=backup_record)
    
    @app.route('/api/restore/<int:backup_id>', methods=['POST'])
    def api_restore_file(backup_id):
        """Restore file via API"""
        try:
            data = request.get_json() or {}
            restore_path = data.get('restore_path')
            
            if not restore_path:
                return jsonify({'error': 'Restore path is required'}), 400
            
            # Secure the filename
            restore_path = secure_filename(os.path.basename(restore_path))
            
            # Create temp file for restoration
            with tempfile.NamedTemporaryFile(delete=False, suffix='_restored') as temp_file:
                temp_path = temp_file.name
            
            try:
                success = backup_engine.restore_file(backup_id, temp_path)
                
                if success:
                    # Return file for download
                    backup_record = db_manager.get_backup_by_id(backup_id)
                    original_filename = os.path.basename(backup_record['file_path'])
                    
                    return send_file(
                        temp_path,
                        as_attachment=True,
                        download_name=original_filename,
                        mimetype='application/octet-stream'
                    )
                else:
                    return jsonify({'error': 'Restore failed'}), 500
                    
            finally:
                # Clean up temp file after some delay
                # In production, you might want to use a background task for cleanup
                pass
                
        except Exception as e:
            logger.error(f"Restore API error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/restore/progress/<restore_id>')
    def get_restore_progress(restore_id):
        """Get progress of a restore operation"""
        try:
            progress_data = progress_tracker.get_progress(restore_id)
            if not progress_data:
                logger.warning(f"Progress data not found for restore ID: {restore_id}")
                return jsonify({'error': 'Restore ID not found'}), 404
            
            logger.info(f"Returning progress data for {restore_id}: {progress_data}")
            return jsonify(progress_data)
        except Exception as e:
            logger.error(f"Progress API error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/backup/manual', methods=['GET', 'POST'])
    def manual_backup():
        """Manual backup page"""
        if request.method == 'GET':
            return render_template('manual_backup.html')
        
        try:
            data = request.get_json() or {}
            file_paths = data.get('file_paths', [])
            
            if not file_paths:
                return jsonify({'error': 'No files specified'}), 400
            
            # Validate file paths
            valid_files = []
            for file_path in file_paths:
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    valid_files.append(file_path)
            
            if not valid_files:
                return jsonify({'error': 'No valid files found'}), 400
            
            # Add to backup queue
            backup_engine.add_to_backup_queue(valid_files)
            
            return jsonify({
                'message': f'Added {len(valid_files)} files to backup queue',
                'files_added': len(valid_files)
            })
            
        except Exception as e:
            logger.error(f"Manual backup error: {e}")
            return jsonify({'error': str(e)}), 500
    

    
    @app.route('/api/monitoring/start', methods=['POST'])
    def api_start_monitoring():
        """Start file monitoring via API"""
        try:
            if file_monitor.is_monitoring:
                return jsonify({'message': 'Monitoring already active'})
            
            success = file_monitor.start_monitoring()
            
            if success:
                return jsonify({'message': 'File monitoring started'})
            else:
                return jsonify({'error': 'Failed to start monitoring'}), 500
                
        except Exception as e:
            logger.error(f"Start monitoring error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/monitoring/stop', methods=['POST'])
    def api_stop_monitoring():
        """Stop file monitoring via API"""
        try:
            file_monitor.stop_monitoring()
            return jsonify({'message': 'File monitoring stopped'})
            
        except Exception as e:
            logger.error(f"Stop monitoring error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/scan/initial', methods=['POST'])
    def api_initial_scan():
        """Perform initial scan via API"""
        try:
            results = file_monitor.perform_initial_scan()
            return jsonify(results)
            
        except Exception as e:
            logger.error(f"Initial scan error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/health')
    def health_check():
        """Health check endpoint"""
        try:
            # Basic health checks
            health_status = {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'database': 'ok',
                'azure_storage': 'ok',
                'file_monitoring': 'ok' if file_monitor.is_monitoring else 'stopped'
            }
            
            # Test database connection
            try:
                db_manager.get_storage_stats(device_id)
            except Exception:
                health_status['database'] = 'error'
                health_status['status'] = 'unhealthy'
            
            # Test Azure connection
            try:
                azure_manager.test_connection()
            except Exception:
                health_status['azure_storage'] = 'error'
                health_status['status'] = 'unhealthy'
            
            status_code = 200 if health_status['status'] == 'healthy' else 503
            return jsonify(health_status), status_code
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500
    
    @app.errorhandler(404)
    def not_found(error):
        return render_template('error.html', error="Page not found"), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return render_template('error.html', error="Internal server error"), 500
    
    # Start background cleanup task for old progress data
    def cleanup_progress_data():
        while True:
            try:
                progress_tracker.cleanup_old_progress(3600)  # Clean up data older than 1 hour
                time.sleep(300)  # Run every 5 minutes
            except Exception as e:
                logger.error(f"Progress cleanup error: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    cleanup_thread = threading.Thread(target=cleanup_progress_data)
    cleanup_thread.daemon = True
    cleanup_thread.start()
    
    return app


def run_web_app(app: Flask, host: str = '127.0.0.1', port: int = 5000, debug: bool = False):
    """Run the Flask web application"""
    logger.info(f"Starting web dashboard on {host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)