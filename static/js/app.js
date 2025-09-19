/**
 * HYCOM Data Downloader - Main JavaScript Application
 * Handles UI interactions, API calls, and real-time updates
 */

// Global variables
let statusPollingInterval;
let isDownloadRunning = false;

// Initialize application when DOM is ready
$(document).ready(function() {
    console.log('HYCOM Data Downloader initialized');
    initializeApp();
});

/**
 * Initialize the application
 */
function initializeApp() {
    // Load configuration
    loadConfiguration();
    
    // Update download information
    updateDownloadInfo();
    
    // Start status polling
    startStatusPolling();
    
    // Set up event listeners
    setupEventListeners();
    
    // Add initial log entry
    addLogEntry('Application initialized successfully', 'success');
}

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Configuration form submission
    $('#configForm').on('submit', handleConfigSubmit);
    
    // Form input changes
    $('#configForm input, #configForm select').on('change', updateDownloadInfo);
    
    // Download control buttons
    $('#startBtn').on('click', startDownload);
    $('#stopBtn').on('click', stopDownload);
    
    // File management
    $(document).on('click', '.download-file-btn', handleFileDownload);
    $(document).on('click', '.delete-file-btn', handleFileDelete);
    
    // Keyboard shortcuts
    $(document).on('keydown', handleKeyboardShortcuts);
}

/**
 * Handle configuration form submission
 */
function handleConfigSubmit(e) {
    e.preventDefault();
    
    // Validate form
    if (!validateConfiguration()) {
        return;
    }
    
    // Get form data
    const config = getConfigurationData();
    
    // Show loading state
    const submitBtn = $('#configForm button[type="submit"]');
    const originalText = submitBtn.html();
    submitBtn.html('<i class="fas fa-spinner fa-spin"></i> Saving...').prop('disabled', true);
    
    // Send configuration to server
    $.ajax({
        url: '/api/config',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(config)
    })
    .done(function(response) {
        addLogEntry('Configuration saved successfully', 'success');
        updateDownloadInfo();
        showNotification('Configuration saved successfully', 'success');
    })
    .fail(function(xhr) {
        const error = xhr.responseJSON ? xhr.responseJSON.message : 'Failed to save configuration';
        addLogEntry('Error: ' + error, 'error');
        showNotification('Error: ' + error, 'error');
    })
    .always(function() {
        // Restore button state
        submitBtn.html(originalText).prop('disabled', false);
    });
}

/**
 * Validate configuration form
 */
function validateConfiguration() {
    let isValid = true;
    const errors = [];
    
    // Check date range
    const startDate = $('#dateStart').val();
    const endDate = $('#dateEnd').val();
    
    if (!startDate || !endDate) {
        errors.push('Please select both start and end dates');
        isValid = false;
    } else if (new Date(startDate) > new Date(endDate)) {
        errors.push('Start date must be before end date');
        isValid = false;
    }
    
    // Check geographic bounds
    const westLon = parseFloat($('#westLon').val());
    const eastLon = parseFloat($('#eastLon').val());
    const southLat = parseFloat($('#southLat').val());
    const northLat = parseFloat($('#northLat').val());
    
    if (isNaN(westLon) || isNaN(eastLon) || isNaN(southLat) || isNaN(northLat)) {
        errors.push('Please enter valid geographic coordinates');
        isValid = false;
    } else if (westLon >= eastLon) {
        errors.push('West longitude must be less than east longitude');
        isValid = false;
    } else if (southLat >= northLat) {
        errors.push('South latitude must be less than north latitude');
        isValid = false;
    }
    
    // Check variables
    const selectedVars = $('input[type="checkbox"]:checked').length;
    if (selectedVars === 0) {
        errors.push('Please select at least one variable');
        isValid = false;
    }
    
    // Show errors
    if (!isValid) {
        errors.forEach(error => {
            addLogEntry('Validation Error: ' + error, 'error');
        });
        showNotification('Please fix the validation errors', 'error');
    }
    
    return isValid;
}

/**
 * Get configuration data from form
 */
function getConfigurationData() {
    const variables = [];
    $('input[type="checkbox"]:checked').each(function() {
        variables.push($(this).val());
    });
    
    return {
        west_lon: parseFloat($('#westLon').val()),
        east_lon: parseFloat($('#eastLon').val()),
        south_lat: parseFloat($('#southLat').val()),
        north_lat: parseFloat($('#northLat').val()),
        date_start: $('#dateStart').val(),
        date_end: $('#dateEnd').val(),
        variables: variables,
        max_retries: parseInt($('#maxRetries').val()),
        timeout: parseInt($('#timeout').val())
    };
}

/**
 * Load configuration from server
 */
function loadConfiguration() {
    $.get('/api/config')
        .done(function(config) {
            // Populate form fields
            $('#westLon').val(config.west_lon);
            $('#eastLon').val(config.east_lon);
            $('#southLat').val(config.south_lat);
            $('#northLat').val(config.north_lat);
            $('#dateStart').val(config.date_start);
            $('#dateEnd').val(config.date_end);
            $('#maxRetries').val(config.max_retries);
            $('#timeout').val(config.timeout);
            
            // Set variables
            $('input[type="checkbox"]').prop('checked', false);
            config.variables.forEach(function(varName) {
                const checkboxId = 'var' + varName.charAt(0).toUpperCase() + varName.slice(1).replace('_', '');
                $('#' + checkboxId).prop('checked', true);
            });
            
            updateDownloadInfo();
            addLogEntry('Configuration loaded from server', 'info');
        })
        .fail(function() {
            addLogEntry('Error loading configuration', 'error');
            showNotification('Failed to load configuration', 'error');
        });
}

/**
 * Update download information display
 */
function updateDownloadInfo() {
    const startDate = $('#dateStart').val();
    const endDate = $('#dateEnd').val();
    const variables = $('input[type="checkbox"]:checked').length;
    const westLon = $('#westLon').val();
    const eastLon = $('#eastLon').val();
    const southLat = $('#southLat').val();
    const northLat = $('#northLat').val();
    
    // Calculate estimated files
    if (startDate && endDate) {
        const start = new Date(startDate);
        const end = new Date(endDate);
        const days = Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1;
        const estimatedFiles = days * variables;
        
        $('#estimatedFiles').text(estimatedFiles.toLocaleString());
        $('#dateRange').text(formatDateRange(startDate, endDate));
    } else {
        $('#estimatedFiles').text('0');
        $('#dateRange').text('Not set');
    }
    
    // Update variables display
    const selectedVars = [];
    $('input[type="checkbox"]:checked').each(function() {
        selectedVars.push($(this).val());
    });
    $('#selectedVars').text(selectedVars.length > 0 ? selectedVars.join(', ') : 'None selected');
    
    // Update geographic area display
    if (westLon && eastLon && southLat && northLat) {
        $('#geoArea').text(`${southLat}°N to ${northLat}°N, ${westLon}°E to ${eastLon}°E`);
    } else {
        $('#geoArea').text('Not set');
    }
}

/**
 * Format date range for display
 */
function formatDateRange(startDate, endDate) {
    const start = new Date(startDate);
    const end = new Date(endDate);
    const days = Math.ceil((end - start) / (1000 * 60 * 60 * 24)) + 1;
    
    return `${startDate} to ${endDate} (${days} days)`;
}

/**
 * Start download process
 */
function startDownload() {
    // Validate configuration first
    if (!validateConfiguration()) {
        return;
    }
    
    // Show confirmation dialog
    const config = getConfigurationData();
    const startDate = new Date(config.date_start);
    const endDate = new Date(config.date_end);
    const days = Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24)) + 1;
    const estimatedFiles = days * config.variables.length;
    
    const message = `Start download?\n\n` +
                   `Date Range: ${config.date_start} to ${config.date_end} (${days} days)\n` +
                   `Variables: ${config.variables.join(', ')}\n` +
                   `Estimated Files: ${estimatedFiles.toLocaleString()}\n` +
                   `Geographic Area: ${config.south_lat}°N to ${config.north_lat}°N, ${config.west_lon}°E to ${config.east_lon}°E`;
    
    if (!confirm(message)) {
        return;
    }
    
    // Start download
    $.post('/api/start_download')
        .done(function(response) {
            addLogEntry('Download started successfully', 'success');
            $('#startBtn').addClass('d-none');
            $('#stopBtn').removeClass('d-none');
            $('#progressContainer').removeClass('d-none');
            isDownloadRunning = true;
            showNotification('Download started', 'success');
        })
        .fail(function(xhr) {
            const error = xhr.responseJSON ? xhr.responseJSON.message : 'Failed to start download';
            addLogEntry('Error: ' + error, 'error');
            showNotification('Error: ' + error, 'error');
        });
}

/**
 * Stop download process
 */
function stopDownload() {
    if (!confirm('Are you sure you want to stop the download?')) {
        return;
    }
    
    $.post('/api/stop_download')
        .done(function(response) {
            addLogEntry('Download stopped by user', 'warning');
            $('#startBtn').removeClass('d-none');
            $('#stopBtn').addClass('d-none');
            isDownloadRunning = false;
            showNotification('Download stopped', 'warning');
        })
        .fail(function(xhr) {
            const error = xhr.responseJSON ? xhr.responseJSON.message : 'Failed to stop download';
            addLogEntry('Error: ' + error, 'error');
            showNotification('Error: ' + error, 'error');
        });
}

/**
 * Start polling for status updates
 */
function startStatusPolling() {
    // Clear any existing interval
    if (statusPollingInterval) {
        clearInterval(statusPollingInterval);
    }
    
    // Poll every 2 seconds
    statusPollingInterval = setInterval(function() {
        $.get('/api/status')
            .done(function(status) {
                updateStatus(status);
            })
            .fail(function() {
                // Silently fail to avoid spam
            });
    }, 2000);
}

/**
 * Update status display
 */
function updateStatus(status) {
    const statusAlert = $('#statusAlert');
    const statusText = $('#statusText');
    const progressBar = $('#progressBar');
    const progressText = $('#progressText');
    const fileCount = $('#fileCount');
    const currentFile = $('#currentFile');
    
    // Update status text and alert type
    let statusMessage = status.status_message || 'Ready';
    let alertClass = 'alert-info';
    let icon = 'fas fa-info-circle';
    
    if (status.is_running) {
        alertClass = 'alert-info';
        icon = 'fas fa-spinner fa-spin';
        statusMessage = statusMessage || 'Downloading...';
    } else if (status.error) {
        alertClass = 'alert-danger';
        icon = 'fas fa-exclamation-triangle';
        statusMessage = status.error;
    } else if (status.end_time) {
        alertClass = 'alert-success';
        icon = 'fas fa-check-circle';
        statusMessage = statusMessage || 'Download completed';
    }
    
    statusAlert.removeClass('alert-info alert-success alert-danger alert-warning')
              .addClass(alertClass);
    statusText.html(`<i class="${icon}"></i> ${statusMessage}`);
    
    // Update progress
    if (status.total_files > 0) {
        const progress = (status.progress / status.total_files) * 100;
        progressBar.css('width', progress + '%');
        progressText.text(Math.round(progress) + '%');
        fileCount.text(`${status.progress.toLocaleString()} / ${status.total_files.toLocaleString()} files`);
    }
    
    // Update current file
    if (status.current_file) {
        currentFile.text('Current: ' + status.current_file);
    } else {
        currentFile.text('Ready');
    }
    
    // Update button states
    if (status.is_running) {
        $('#startBtn').addClass('d-none');
        $('#stopBtn').removeClass('d-none');
        $('#progressContainer').removeClass('d-none');
        isDownloadRunning = true;
    } else {
        $('#startBtn').removeClass('d-none');
        $('#stopBtn').addClass('d-none');
        isDownloadRunning = false;
    }
    
    // Update running state
    isDownloadRunning = status.is_running;
}

/**
 * Show files panel
 */
function showFiles() {
    $('#filesPanel').removeClass('d-none').addClass('fade-in');
    loadFiles();
}

/**
 * Hide files panel
 */
function hideFiles() {
    $('#filesPanel').addClass('d-none');
}

/**
 * Load files list
 */
function loadFiles() {
    $('#filesList').html(`
        <div class="text-center">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">Loading files...</p>
        </div>
    `);
    
    $.get('/api/files')
        .done(function(response) {
            displayFiles(response.files);
        })
        .fail(function() {
            $('#filesList').html('<div class="alert alert-danger">Failed to load files</div>');
        });
}

/**
 * Display files in table
 */
function displayFiles(files) {
    if (files.length === 0) {
        $('#filesList').html('<div class="alert alert-info">No files found</div>');
        return;
    }
    
    let html = '<div class="table-responsive"><table class="table table-striped">';
    html += '<thead><tr><th>File Name</th><th>Size</th><th>Created</th><th>Actions</th></tr></thead><tbody>';
    
    files.forEach(function(file) {
        const size = formatFileSize(file.size);
        const created = new Date(file.created).toLocaleString();
        
        html += '<tr>';
        html += `<td><i class="fas fa-file-archive"></i> ${file.name}</td>`;
        html += `<td>${size}</td>`;
        html += `<td>${created}</td>`;
        html += '<td>';
        html += `<button class="btn btn-sm btn-primary me-1 download-file-btn" data-filename="${file.name}">
                    <i class="fas fa-download"></i> Download
                 </button>`;
        html += `<button class="btn btn-sm btn-danger delete-file-btn" data-filename="${file.name}">
                    <i class="fas fa-trash"></i> Delete
                 </button>`;
        html += '</td>';
        html += '</tr>';
    });
    
    html += '</tbody></table></div>';
    $('#filesList').html(html);
}

/**
 * Handle file download
 */
function handleFileDownload(e) {
    const filename = $(e.target).closest('button').data('filename');
    window.open('/api/download/' + encodeURIComponent(filename), '_blank');
    addLogEntry('Downloaded file: ' + filename, 'info');
}

/**
 * Handle file deletion
 */
function handleFileDelete(e) {
    const filename = $(e.target).closest('button').data('filename');
    
    if (confirm('Are you sure you want to delete ' + filename + '?')) {
        $.ajax({
            url: '/api/delete/' + encodeURIComponent(filename),
            method: 'DELETE'
        })
        .done(function() {
            addLogEntry('File deleted: ' + filename, 'info');
            loadFiles();
            showNotification('File deleted successfully', 'success');
        })
        .fail(function(xhr) {
            const error = xhr.responseJSON ? xhr.responseJSON.message : 'Failed to delete file';
            addLogEntry('Error: ' + error, 'error');
            showNotification('Error: ' + error, 'error');
        });
    }
}

/**
 * Format file size for display
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Add log entry
 */
function addLogEntry(message, type) {
    const timestamp = new Date().toLocaleTimeString();
    const icon = getLogIcon(type);
    const color = getLogColor(type);
    
    const logEntry = $(`<div class="log-entry">
        <span class="text-muted">[${timestamp}]</span> 
        <i class="${icon}" style="color: ${color}"></i> ${message}
    </div>`);
    
    $('#logContainer').append(logEntry);
    $('#logContainer').scrollTop($('#logContainer')[0].scrollHeight);
}

/**
 * Get log icon based on type
 */
function getLogIcon(type) {
    switch (type) {
        case 'error': return 'fas fa-exclamation-circle';
        case 'success': return 'fas fa-check-circle';
        case 'warning': return 'fas fa-exclamation-triangle';
        case 'info': return 'fas fa-info-circle';
        default: return 'fas fa-info-circle';
    }
}

/**
 * Get log color based on type
 */
function getLogColor(type) {
    switch (type) {
        case 'error': return '#dc3545';
        case 'success': return '#198754';
        case 'warning': return '#ffc107';
        case 'info': return '#0dcaf0';
        default: return '#6c757d';
    }
}

/**
 * Show notification
 */
function showNotification(message, type) {
    // Create notification element
    const notification = $(`
        <div class="alert alert-${type} alert-dismissible fade show position-fixed" 
             style="top: 20px; right: 20px; z-index: 9999; min-width: 300px;">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `);
    
    // Add to body
    $('body').append(notification);
    
    // Auto remove after 5 seconds
    setTimeout(function() {
        notification.alert('close');
    }, 5000);
}

/**
 * Handle keyboard shortcuts
 */
function handleKeyboardShortcuts(e) {
    // Ctrl+S: Save configuration
    if (e.ctrlKey && e.key === 's') {
        e.preventDefault();
        $('#configForm').submit();
    }
    
    // Ctrl+D: Start download
    if (e.ctrlKey && e.key === 'd') {
        e.preventDefault();
        if (!isDownloadRunning) {
            startDownload();
        }
    }
    
    // Ctrl+Shift+D: Stop download
    if (e.ctrlKey && e.shiftKey && e.key === 'D') {
        e.preventDefault();
        if (isDownloadRunning) {
            stopDownload();
        }
    }
    
    // Ctrl+F: Show files
    if (e.ctrlKey && e.key === 'f') {
        e.preventDefault();
        showFiles();
    }
}

/**
 * Cleanup when page unloads
 */
$(window).on('beforeunload', function() {
    if (statusPollingInterval) {
        clearInterval(statusPollingInterval);
    }
});

// Export functions for global access
window.showFiles = showFiles;
window.hideFiles = hideFiles;
window.startDownload = startDownload;
window.stopDownload = stopDownload;
