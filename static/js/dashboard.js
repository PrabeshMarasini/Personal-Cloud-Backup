// Dashboard functionality for Personal Backup System (NiziPos Style)

// Auto-refresh dashboard every 30 seconds
setInterval(refreshDashboardStats, 30000);

// Show notification function
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    const bgColor = type === 'success' ? 'bg-green-500' : type === 'error' ? 'bg-red-500' : 'bg-blue-500';
    
    notification.className = `fixed top-4 right-4 ${bgColor} text-white px-6 py-3 rounded shadow-lg z-50 transform translate-x-full transition-transform duration-300`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    // Show notification
    setTimeout(() => {
        notification.classList.remove('translate-x-full');
    }, 100);
    
    // Hide and remove notification
    setTimeout(() => {
        notification.classList.add('translate-x-full');
        setTimeout(() => {
            if (document.body.contains(notification)) {
                document.body.removeChild(notification);
            }
        }, 300);
    }, 4000);
}





// Refresh dashboard statistics
function refreshDashboardStats() {
    axios.get('/api/status')
        .then(response => {
            const data = response.data;
            
            // Update stats with animation
            animateCounter('total-files', data.storage_stats?.total_files || 0);
            animateCounter('queue-size', data.backup_status?.queue_size || 0);
            
            // Update storage
            const storageUsed = (data.storage_stats?.total_encrypted_size || 0) / 1024 / 1024;
            const storageElement = document.getElementById('storage-used');
            if (storageElement) {
                storageElement.textContent = storageUsed.toFixed(1) + ' MB';
            }
            
            // Update monitoring status
            const monitoringStatus = data.monitoring_stats?.is_monitoring ? 'Active' : 'Stopped';
            const monitoringElement = document.getElementById('monitoring-status');
            if (monitoringElement) {
                monitoringElement.textContent = monitoringStatus;
            }
        })
        .catch(error => {
            console.log('Error refreshing stats:', error);
        });
}

// Animate counter numbers
function animateCounter(elementId, targetValue) {
    const element = document.getElementById(elementId);
    if (!element) return;
    
    const currentValue = parseInt(element.textContent) || 0;
    const increment = (targetValue - currentValue) / 20;
    let current = currentValue;
    
    const timer = setInterval(() => {
        current += increment;
        if ((increment > 0 && current >= targetValue) || (increment < 0 && current <= targetValue)) {
            current = targetValue;
            clearInterval(timer);
        }
        element.textContent = Math.round(current);
    }, 50);
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    // Initial stats refresh
    refreshDashboardStats();
});