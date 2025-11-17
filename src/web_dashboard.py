import os
import json
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
            return jsonify({
                'storage_stats': db_manager.get_storage_stats(device_id),
                'monitoring_stats': file_monitor.get_monitoring_stats(),
                'backup_status': backup_engine.get_backup_status(),
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
    
    @app.route('/restore/<int:backup_id>')
    def restore_file_page(backup_id):
        """Show restore file page"""
        try:
            backup_record = db_manager.get_backup_by_id(backup_id)
            
            if not backup_record:
                flash(f"Backup record not found: {backup_id}", 'error')
                return redirect(url_for('files_list'))
            
            return render_template('restore.html', backup=backup_record)
            
        except Exception as e:
            logger.error(f"Restore page error: {e}")
            flash(f"Error loading restore page: {e}", 'error')
            return redirect(url_for('files_list'))
    
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
    
    @app.route('/api/backup/process', methods=['POST'])
    def api_process_backup_queue():
        """Process backup queue via API"""
        try:
            results = backup_engine.process_backup_queue()
            return jsonify(results)
            
        except Exception as e:
            logger.error(f"Process backup queue error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/settings', methods=['GET', 'POST'])
    def settings():
        """Settings page"""
        if request.method == 'GET':
            # Load current configuration
            from config.config import config
            
            settings_data = {
                'watched_directories': config.watched_directories,
                'exclude_patterns': config.exclude_patterns,
                'compression_level': config.compression_level,
                'max_file_size_mb': config.max_file_size_mb,
                'max_versions_per_file': config.max_versions_per_file,
                'retention_days': config.retention_days,
                'backup_interval_minutes': config.backup_interval_minutes
            }
            
            return render_template('settings.html', settings=settings_data)
        
        try:
            # Handle settings update
            data = request.get_json() or {}
            
            # Update configuration (this is simplified - in production you'd want
            # to validate and properly save configuration changes)
            flash('Settings updated successfully', 'success')
            
            return jsonify({'message': 'Settings updated'})
            
        except Exception as e:
            logger.error(f"Settings update error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/cleanup', methods=['POST'])
    def api_cleanup():
        """Run cleanup via API"""
        try:
            results = backup_engine.cleanup_old_backups()
            return jsonify(results)
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
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
    
    return app


def run_web_app(app: Flask, host: str = '127.0.0.1', port: int = 5000, debug: bool = False):
    """Run the Flask web application"""
    logger.info(f"Starting web dashboard on {host}:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)