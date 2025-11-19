// Files page functionality (NiziPos Style)

// Filter files based on search and status
function filterFiles() {
    const searchTerm = document.getElementById('file-search').value.toLowerCase();
    const rows = document.querySelectorAll('.file-row');
    let visibleCount = 0;
    
    rows.forEach(row => {
        const filename = row.getAttribute('data-filename');
        const path = row.getAttribute('data-path');
        const matchesSearch = filename.includes(searchTerm) || path.includes(searchTerm);
        
        if (matchesSearch) {
            row.style.display = '';
            visibleCount++;
        } else {
            row.style.display = 'none';
        }
    });
    
    // Show/hide no results message
    const noResults = document.getElementById('no-results');
    const filesTable = document.querySelector('.bg-white.shadow-md.rounded.mb-6');
    
    if (visibleCount === 0) {
        if (noResults) noResults.style.display = 'block';
        if (filesTable) filesTable.style.display = 'none';
    } else {
        if (noResults) noResults.style.display = 'none';
        if (filesTable) filesTable.style.display = 'block';
    }
    
    // Update file count
    const countBadge = document.querySelector('.bg-blue-100.text-blue-800');
    if (countBadge) {
        countBadge.textContent = `${visibleCount} Files Found`;
    }
}

// Sort files table
function sortFilesTable(columnIndex) {
    const table = document.getElementById('files-table-body');
    if (!table) return;
    
    const rows = Array.from(table.rows);
    const isAscending = table.getAttribute('data-sort-direction') !== 'asc';
    
    rows.sort((a, b) => {
        const aText = a.cells[columnIndex].textContent.trim();
        const bText = b.cells[columnIndex].textContent.trim();
        
        if (isAscending) {
            return aText.localeCompare(bText);
        } else {
            return bText.localeCompare(aText);
        }
    });
    
    // Clear table and re-add sorted rows
    table.innerHTML = '';
    rows.forEach(row => table.appendChild(row));
    
    // Update sort direction
    table.setAttribute('data-sort-direction', isAscending ? 'asc' : 'desc');
    
    showNotification('Table sorted', 'info');
}

// Show notification (same as dashboard)
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

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    // Auto-focus search input
    const searchInput = document.getElementById('file-search');
    if (searchInput) {
        searchInput.focus();
        
        // Initialize filter if there's a search query
        if (searchInput.value) {
            filterFiles();
        }
    }
});