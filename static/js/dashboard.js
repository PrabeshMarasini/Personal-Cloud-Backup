// Dashboard functionality for Personal Backup System

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