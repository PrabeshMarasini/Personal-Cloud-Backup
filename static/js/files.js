// Files page functionality (NiziPos Style)

let selectedFiles = [];

// Filter files based on search and status
function filterFiles() {
    const searchTerm = document.getElementById('file-search').value.toLowerCase();
    const statusFilter = document.getElementById('status-filter').value;
    const rows = document.querySelectorAll('.file-row');
    let visibleCount = 0;
    
    rows.forEach(row => {
        const filename = row.getAttribute('data-filename');
        const path = row.getAttribute('data-path');
        const matchesSearch = filename.includes(searchTerm) || path.includes(searchTerm);
        const matchesStatus = !statusFilter || row.querySelector('.bg-green-100');
        
        if (matchesSearch && matchesStatus) {
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

// Toggle select all checkboxes
function toggleSelectAll() {
    const selectAll = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('.file-select');
    
    checkboxes.forEach(checkbox => {
        if (checkbox.closest('.file-row').style.display !== 'none') {
            checkbox.checked = selectAll.checked;
        }
    });
    
    updateBulkActions();
}

// Update bulk actions based on selection
function updateBulkActions() {
    const checkboxes = document.querySelectorAll('.file-select:checked');
    selectedFiles = Array.from(checkboxes).map(cb => cb.value);
    
    const bulkActions = document.getElementById('bulk-actions');
    const selectedCount = document.getElementById('selected-count');
    
    if (selectedCount) {
        selectedCount.textContent = selectedFiles.length;
    }
    
    if (selectedFiles.length > 0) {
        if (bulkActions) bulkActions.style.display = 'block';
    } else {
        if (bulkActions) bulkActions.style.display = 'none';
    }
}

// Toggle bulk actions panel
function toggleBulkActions() {
    const bulkActions = document.getElementById('bulk-actions');
    if (bulkActions) {
        bulkActions.style.display = bulkActions.style.display === 'none' ? 'block' : 'none';
    }
}

// Clear all selections
function clearSelection() {
    const checkboxes = document.querySelectorAll('.file-select');
    checkboxes.forEach(cb => cb.checked = false);
    const selectAll = document.getElementById('select-all');
    if (selectAll) selectAll.checked = false;
    updateBulkActions();
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



// Bulk delete files
function bulkDelete() {
    if (selectedFiles.length === 0) {
        showNotification('Please select files to delete', 'error');
        return;
    }
    
    if (confirm(`Are you sure you want to delete ${selectedFiles.length} backup records? This cannot be undone.`)) {
        showNotification(`Bulk delete of ${selectedFiles.length} files started`, 'info');
        // TODO: Implement bulk delete functionality
    }
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