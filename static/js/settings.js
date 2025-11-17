// Settings page functionality for Personal Backup System

function runCleanup() {
    if (confirm('Are you sure you want to run cleanup? This will remove orphaned database records.')) {
        fetch('/api/cleanup', {method: 'POST'})
            .then(response => response.json())
            .then(data => {
                alert('Cleanup completed: ' + (data.database_records_cleaned || 0) + ' records cleaned');
                location.reload();
            })
            .catch(error => alert('Error: ' + error));
    }
}

function exportBackups() {
    fetch('/api/export', {method: 'GET'})
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = 'backup_list.json';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
        })
        .catch(error => alert('Error exporting backups: ' + error));
}

function resetSystem() {
    if (confirm('WARNING: This will delete all backup records and reset the system. Are you sure?')) {
        if (confirm('This action cannot be undone. Continue?')) {
            fetch('/api/reset', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    alert('System reset completed');
                    location.reload();
                })
                .catch(error => alert('Error: ' + error));
        }
    }
}