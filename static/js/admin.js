// ============ GLOBAL VARIABLES ============
let currentLicensePage = 1;
const licensesPerPage = 20;
let totalLicenses = 0;
let selectedLicenses = new Set();

// ============ UTILITY FUNCTIONS ============

// Show toast notification
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const icon = document.getElementById('toastIcon');
    const msg = document.getElementById('toastMessage');
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    const colors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        warning: 'bg-yellow-500',
        info: 'bg-blue-500'
    };
    
    // Remove all color classes
    toast.className = toast.className.replace(/bg-(green|red|yellow|blue|gray)-500/g, '');
    
    // Add current color
    toast.classList.add(colors[type] || 'bg-gray-800');
    icon.className = `fas ${icons[type] || 'fa-info-circle'}`;
    msg.textContent = message;
    
    // Show toast
    toast.classList.remove('translate-x-full');
    
    // Hide after 3 seconds
    setTimeout(() => {
        toast.classList.add('translate-x-full');
    }, 3000);
}

// Copy to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Copied to clipboard!', 'success');
    }).catch(err => {
        showToast('Failed to copy', 'error');
        console.error('Copy error:', err);
    });
}

// Format date
function formatDate(dateString) {
    if (!dateString) return 'Never';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Calculate days left
function calculateDaysLeft(expiresAt) {
    if (!expiresAt) return null;
    const now = new Date();
    const expiry = new Date(expiresAt);
    const diff = expiry - now;
    return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
}

// ============ AUTH FUNCTIONS ============

// Logout
async function logout() {
    const { isConfirmed } = await Swal.fire({
        title: 'Logout?',
        text: 'Are you sure you want to logout?',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Yes, logout',
        cancelButtonText: 'Cancel',
        confirmButtonColor: '#ef4444'
    });
    
    if (isConfirmed) {
        try {
            const response = await fetch('/api/admin/logout', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                window.location.href = '/login';
            } else {
                showToast('Logout failed', 'error');
            }
        } catch (error) {
            console.error('Logout error:', error);
            showToast('Connection error', 'error');
        }
    }
}

// ============ DASHBOARD FUNCTIONS ============

// Load dashboard stats
async function loadDashboard() {
    try {
        const response = await fetch('/api/admin/stats');
        const data = await response.json();
        
        if (data.success) {
            // Update stats
            document.getElementById('totalLicenses').textContent = data.data.total_licenses;
            document.getElementById('activeLicenses').textContent = data.data.active_licenses;
            document.getElementById('expiredLicenses').textContent = data.data.expired_licenses;
            document.getElementById('inactiveLicenses').textContent = data.data.inactive_licenses;
            document.getElementById('bannedLicenses').textContent = data.data.banned_licenses;
            document.getElementById('customKeys').textContent = data.data.custom_keys;
            document.getElementById('serverKeys').textContent = data.data.active_server_keys;
            document.getElementById('apiKeys').textContent = data.data.active_api_keys;
            document.getElementById('todayLicenses').textContent = data.data.today_licenses;
            
            // Load recent activity
            await loadRecentActivity();
        }
    } catch (error) {
        console.error('Dashboard error:', error);
    }
}

// Load recent activity
async function loadRecentActivity() {
    try {
        const response = await fetch('/api/admin/activity?limit=10');
        const data = await response.json();
        
        if (data.success) {
            const container = document.getElementById('recentActivity');
            container.innerHTML = '';
            
            if (data.data.length === 0) {
                container.innerHTML = '<p class="text-gray-500 text-center py-4">No activity yet</p>';
                return;
            }
            
            data.data.forEach(log => {
                const icon = getActivityIcon(log.action);
                const color = getActivityColor(log.action);
                
                const item = `
                    <div class="flex items-start space-x-3">
                        <div class="${color} w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0">
                            <i class="${icon} text-white text-sm"></i>
                        </div>
                        <div class="flex-1">
                            <div class="flex justify-between">
                                <p class="font-medium text-gray-800">${formatAction(log.action)}</p>
                                <span class="text-xs text-gray-500">${formatDate(log.created_at)}</span>
                            </div>
                            <p class="text-sm text-gray-600">by ${log.username}</p>
                            ${log.details ? `<p class="text-xs text-gray-500 mt-1">${JSON.stringify(log.details)}</p>` : ''}
                        </div>
                    </div>
                `;
                container.innerHTML += item;
            });
        }
    } catch (error) {
        console.error('Activity error:', error);
    }
}

function getActivityIcon(action) {
    switch(action) {
        case 'LOGIN': return 'fas fa-sign-in-alt';
        case 'LOGOUT': return 'fas fa-sign-out-alt';
        case 'CREATE_LICENSE': return 'fas fa-plus-circle';
        case 'DELETE_LICENSE': return 'fas fa-trash-alt';
        case 'RESET_LICENSE': return 'fas fa-redo';
        case 'EXTEND_LICENSE': return 'fas fa-calendar-plus';
        case 'BAN_LICENSE': return 'fas fa-ban';
        case 'CREATE_SERVER_KEY': return 'fas fa-key';
        case 'CREATE_API_KEY': return 'fas fa-code';
        default: return 'fas fa-info-circle';
    }
}

function getActivityColor(action) {
    switch(action) {
        case 'LOGIN': return 'bg-green-500';
        case 'CREATE_LICENSE': return 'bg-blue-500';
        case 'CREATE_SERVER_KEY': return 'bg-purple-500';
        case 'CREATE_API_KEY': return 'bg-orange-500';
        case 'DELETE_LICENSE': return 'bg-red-500';
        case 'RESET_LICENSE': return 'bg-yellow-500';
        default: return 'bg-gray-500';
    }
}

function formatAction(action) {
    return action.replace(/_/g, ' ');
}

// ============ LICENSE FUNCTIONS ============

// Load licenses
async function loadLicenses() {
    try {
        const search = document.getElementById('searchLicense').value;
        const status = document.getElementById('filterStatus').value;
        
        let url = `/api/admin/licenses?page=${currentLicensePage}&limit=${licensesPerPage}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (status) url += `&status=${status}`;
        
        const tbody = document.getElementById('licenseTableBody');
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="px-6 py-8 text-center text-gray-500">
                    <div class="flex justify-center">
                        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                    </div>
                    <p class="mt-2">Loading licenses...</p>
                </td>
            </tr>
        `;
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.success) {
            totalLicenses = data.pagination.total;
            
            tbody.innerHTML = '';
            selectedLicenses.clear();
            
            if (data.data.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="7" class="px-6 py-8 text-center text-gray-500">
                            <i class="fas fa-inbox text-4xl mb-2 text-gray-300"></i>
                            <p>No licenses found</p>
                            <button onclick="showCreateLicenseModal()" class="mt-4 px-4 py-2 btn-primary rounded-lg">
                                <i class="fas fa-plus mr-2"></i> Create your first license
                            </button>
                        </td>
                    </tr>
                `;
                updateLicensePagination();
                updateLicenseCount();
                return;
            }
            
            data.data.forEach(license => {
                const statusClass = `status-${license.status}`;
                const daysLeft = license.days_left !== null ? license.days_left : calculateDaysLeft(license.expires_at);
                
                const row = `
                    <tr class="hover:bg-gray-50">
                        <td class="px-6 py-4">
                            <input type="checkbox" class="license-checkbox rounded border-gray-300" value="${license.id}">
                        </td>
                        <td class="px-6 py-4">
                            <div class="license-key text-sm font-mono">${license.license_key}</div>
                            <div class="flex items-center space-x-2 mt-1">
                                <span class="text-xs text-gray-500">ID: ${license.id}</span>
                                ${license.is_custom_key ? '<span class="custom-key-badge text-xs px-2 py-1 rounded">Custom</span>' : ''}
                            </div>
                        </td>
                        <td class="px-6 py-4">
                            <div class="font-medium">${license.product}</div>
                            <div class="text-xs text-gray-500">Devices: ${license.max_devices}</div>
                        </td>
                        <td class="px-6 py-4">
                            <div>${license.owner || '-'}</div>
                        </td>
                        <td class="px-6 py-4">
                            <span class="status-badge ${statusClass}">${license.status}</span>
                            ${license.hwid_lock ? '<i class="fas fa-lock text-xs text-gray-400 ml-1" title="HWID Locked"></i>' : ''}
                            ${license.ip_lock ? '<i class="fas fa-globe text-xs text-gray-400 ml-1" title="IP Locked"></i>' : ''}
                        </td>
                        <td class="px-6 py-4">
                            <div>${license.expires_at ? formatDate(license.expires_at) : 'Never'}</div>
                            ${daysLeft !== null ? `<div class="text-xs ${daysLeft < 7 ? 'text-red-600 font-bold' : 'text-gray-500'}">(${daysLeft} days left)</div>` : ''}
                        </td>
                        <td class="px-6 py-4">
                            <div class="flex space-x-1">
                                <button onclick="showLicenseDetails(${license.id})" class="p-1 text-blue-500 hover:text-blue-700" title="View">
                                    <i class="fas fa-eye"></i>
                                </button>
                                <button onclick="showLicenseActions(${license.id})" class="p-1 text-purple-500 hover:text-purple-700" title="Actions">
                                    <i class="fas fa-cog"></i>
                                </button>
                                <button onclick="deleteLicense(${license.id})" class="p-1 text-red-500 hover:text-red-700" title="Delete">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
                tbody.innerHTML += row;
            });
            
            // Add checkbox event listeners
            document.querySelectorAll('.license-checkbox').forEach(checkbox => {
                checkbox.addEventListener('change', function() {
                    if (this.checked) {
                        selectedLicenses.add(this.value);
                    } else {
                        selectedLicenses.delete(this.value);
                    }
                    updateSelectAll();
                });
            });
            
            updateLicensePagination();
            updateLicenseCount();
        }
    } catch (error) {
        console.error('Load licenses error:', error);
        const tbody = document.getElementById('licenseTableBody');
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="px-6 py-8 text-center text-red-500">
                    <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                    <p>Error loading licenses</p>
                </td>
            </tr>
        `;
    }
}

function updateSelectAll() {
    const selectAll = document.getElementById('selectAll');
    const checkboxes = document.querySelectorAll('.license-checkbox');
    const checkedCount = document.querySelectorAll('.license-checkbox:checked').length;
    
    selectAll.checked = checkedCount === checkboxes.length && checkboxes.length > 0;
    selectAll.indeterminate = checkedCount > 0 && checkedCount < checkboxes.length;
}

function updateLicensePagination() {
    const totalPages = Math.ceil(totalLicenses / licensesPerPage);
    document.getElementById('currentLicensePage').textContent = currentLicensePage;
    document.getElementById('prevLicenseBtn').disabled = currentLicensePage === 1;
    document.getElementById('nextLicenseBtn').disabled = currentLicensePage === totalPages || totalPages === 0;
}

function updateLicenseCount() {
    const start = (currentLicensePage - 1) * licensesPerPage + 1;
    const end = Math.min(currentLicensePage * licensesPerPage, totalLicenses);
    document.getElementById('licenseCount').textContent = `Showing ${start}-${end} of ${totalLicenses} licenses`;
}

function prevLicensePage() {
    if (currentLicensePage > 1) {
        currentLicensePage--;
        loadLicenses();
    }
}

function nextLicensePage() {
    const totalPages = Math.ceil(totalLicenses / licensesPerPage);
    if (currentLicensePage < totalPages) {
        currentLicensePage++;
        loadLicenses();
    }
}

// ============ LICENSE MODALS ============

// Show create license modal
function showCreateLicenseModal() {
    Swal.fire({
        title: 'Create License',
        html: `
            <div class="text-left space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Product Name *</label>
                    <input type="text" id="product" class="swal2-input" placeholder="Enter product name" required>
                </div>
                
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Status</label>
                        <select id="status" class="swal2-input">
                            <option value="active">Active</option>
                            <option value="inactive">Inactive</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Days *</label>
                        <input type="number" id="days" class="swal2-input" value="30" min="1" required>
                    </div>
                </div>
                
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Max Devices</label>
                        <input type="number" id="maxDevices" class="swal2-input" value="1" min="1">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Auto Renew</label>
                        <select id="autoRenew" class="swal2-input">
                            <option value="false">No</option>
                            <option value="true">Yes</option>
                        </select>
                    </div>
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Owner (Optional)</label>
                    <input type="text" id="owner" class="swal2-input" placeholder="License owner name">
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Notes (Optional)</label>
                    <textarea id="notes" class="swal2-textarea" rows="2" placeholder="Additional notes"></textarea>
                </div>
            </div>
        `,
        showCancelButton: true,
        confirmButtonText: 'Create License',
        cancelButtonText: 'Cancel',
        confirmButtonColor: '#3b82f6',
        preConfirm: () => {
            const product = document.getElementById('product').value.trim();
            const days = document.getElementById('days').value;
            
            if (!product) {
                Swal.showValidationMessage('Product name is required');
                return false;
            }
            
            if (!days || days < 1) {
                Swal.showValidationMessage('Days must be at least 1');
                return false;
            }
            
            return {
                product: product,
                status: document.getElementById('status').value,
                custom_days: parseInt(days),
                max_devices: parseInt(document.getElementById('maxDevices').value),
                auto_renew: document.getElementById('autoRenew').value === 'true',
                owner: document.getElementById('owner').value.trim(),
                notes: document.getElementById('notes').value.trim()
            };
        }
    }).then(async (result) => {
        if (result.isConfirmed) {
            try {
                const response = await fetch('/api/admin/licenses/create', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(result.value)
                });
                
                const data = await response.json();
                
                if (data.success) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Success!',
                        html: `
                            <p>License created successfully!</p>
                            <div class="mt-4 p-3 bg-gray-100 rounded">
                                <p class="font-mono text-sm">${data.license_key}</p>
                                <p class="text-xs text-gray-600 mt-1">Expires: ${data.expires_at}</p>
                            </div>
                            <button onclick="copyToClipboard('${data.license_key}')" class="mt-3 px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition">
                                <i class="fas fa-copy mr-2"></i> Copy License Key
                            </button>
                        `
                    });
                    
                    // Reload data
                    await loadLicenses();
                    await loadDashboard();
                } else {
                    Swal.fire('Error!', data.message, 'error');
                }
            } catch (error) {
                console.error('Create license error:', error);
                Swal.fire('Error!', 'Connection error', 'error');
            }
        }
    });
}

// Show create custom license modal
function showCreateCustomLicenseModal() {
    Swal.fire({
        title: 'Create Custom License',
        html: `
            <div class="text-left space-y-4">
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Custom License Key *</label>
                    <input type="text" id="customKey" class="swal2-input" placeholder="CUSTOM-KEY-123" required>
                    <p class="text-xs text-gray-500 mt-1">Uppercase letters, numbers, and hyphens only (10-50 characters)</p>
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Product Name *</label>
                    <input type="text" id="product" class="swal2-input" placeholder="Enter product name" required>
                </div>
                
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Status</label>
                        <select id="status" class="swal2-input">
                            <option value="active">Active</option>
                            <option value="inactive">Inactive</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Days *</label>
                        <input type="number" id="days" class="swal2-input" value="30" min="1" required>
                    </div>
                </div>
                
                <div>
                    <label class="block text-sm font-medium text-gray-700 mb-1">Owner (Optional)</label>
                    <input type="text" id="owner" class="swal2-input" placeholder="License owner name">
                </div>
            </div>
        `,
        showCancelButton: true,
        confirmButtonText: 'Create Custom License',
        cancelButtonText: 'Cancel',
        confirmButtonColor: '#8b5cf6',
        preConfirm: () => {
            const customKey = document.getElementById('customKey').value.trim().toUpperCase();
            const product = document.getElementById('product').value.trim();
            const days = document.getElementById('days').value;
            
            if (!customKey) {
                Swal.showValidationMessage('Custom license key is required');
                return false;
            }
            
            if (!/^[A-Z0-9-]{10,50}$/.test(customKey)) {
                Swal.showValidationMessage('Invalid license key format. Use uppercase letters, numbers, and hyphens (10-50 characters)');
                return false;
            }
            
            if (!product) {
                Swal.showValidationMessage('Product name is required');
                return false;
            }
            
            if (!days || days < 1) {
                Swal.showValidationMessage('Days must be at least 1');
                return false;
            }
            
            return {
                custom_key: customKey,
                product: product,
                status: document.getElementById('status').value,
                custom_days: parseInt(days),
                owner: document.getElementById('owner').value.trim()
            };
        }
    }).then(async (result) => {
        if (result.isConfirmed) {
            try {
                const response = await fetch('/api/admin/licenses/create', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(result.value)
                });
                
                const data = await response.json();
                
                if (data.success) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Success!',
                        html: `
                            <p>Custom license created successfully!</p>
                            <div class="mt-4 p-3 bg-gray-100 rounded">
                                <p class="font-mono text-sm">${data.license_key}</p>
                                <p class="text-xs text-gray-600 mt-1">Expires: ${data.expires_at}</p>
                                <p class="text-xs text-purple-600 mt-1">✓ Custom License Key</p>
                            </div>
                            <button onclick="copyToClipboard('${data.license_key}')" class="mt-3 px-4 py-2 bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 transition">
                                <i class="fas fa-copy mr-2"></i> Copy License Key
                            </button>
                        `
                    });
                    
                    // Reload data
                    await loadLicenses();
                    await loadDashboard();
                } else {
                    Swal.fire('Error!', data.message, 'error');
                }
            } catch (error) {
                console.error('Create custom license error:', error);
                Swal.fire('Error!', 'Connection error', 'error');
            }
        }
    });
}

// Show license details
async function showLicenseDetails(licenseId) {
    try {
        const response = await fetch(`/api/admin/licenses/${licenseId}`);
        const data = await response.json();
        
        if (data.success) {
            const license = data.license;
            const activations = data.activations;
            
            let statusColor = '';
            switch(license.status) {
                case 'active': statusColor = 'text-green-600'; break;
                case 'inactive': statusColor = 'text-yellow-600'; break;
                case 'expired': statusColor = 'text-red-600'; break;
                case 'banned': statusColor = 'text-gray-600'; break;
            }
            
            let activationsHtml = '';
            if (activations.length > 0) {
                activationsHtml = `
                    <div class="mt-4">
                        <p class="font-medium text-gray-700 mb-2">Activations (${activations.length}/${license.max_devices})</p>
                        <div class="max-h-40 overflow-y-auto space-y-2">
                            ${activations.map(act => `
                                <div class="p-2 bg-gray-50 rounded">
                                    <div class="flex justify-between">
                                        <span class="font-mono text-sm">${act.hwid}</span>
                                        <span class="text-xs ${act.is_active ? 'text-green-600' : 'text-gray-400'}">
                                            ${act.is_active ? 'Active' : 'Inactive'}
                                        </span>
                                    </div>
                                    <div class="text-xs text-gray-500">
                                        IP: ${act.ip_address || 'N/A'} | 
                                        Last: ${formatDate(act.last_check)}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            }
            
            Swal.fire({
                title: 'License Details',
                html: `
                    <div class="text-left space-y-4">
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <p class="text-sm text-gray-600">License Key</p>
                                <p class="font-mono font-bold">${license.license_key}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">Status</p>
                                <p class="font-bold ${statusColor}">${license.status.toUpperCase()}</p>
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <p class="text-sm text-gray-600">Product</p>
                                <p class="font-medium">${license.product}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">Owner</p>
                                <p class="font-medium">${license.owner || '-'}</p>
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <p class="text-sm text-gray-600">Created</p>
                                <p>${formatDate(license.created_at)}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">Expires</p>
                                <p>${license.expires_at ? formatDate(license.expires_at) : 'Never'}</p>
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <p class="text-sm text-gray-600">Max Devices</p>
                                <p>${license.max_devices}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">Total Activations</p>
                                <p>${license.total_activations}</p>
                            </div>
                        </div>
                        
                        ${license.hwid_lock ? `
                            <div>
                                <p class="text-sm text-gray-600">HWID Lock</p>
                                <p class="font-mono text-sm">${license.hwid_lock}</p>
                            </div>
                        ` : ''}
                        
                        ${license.notes ? `
                            <div>
                                <p class="text-sm text-gray-600">Notes</p>
                                <p class="text-sm whitespace-pre-wrap">${license.notes}</p>
                            </div>
                        ` : ''}
                        
                        ${activationsHtml}
                    </div>
                `,
                showCancelButton: true,
                confirmButtonText: 'Close',
                cancelButtonText: 'Actions',
                confirmButtonColor: '#3b82f6',
                showCloseButton: true,
                width: '600px'
            }).then((result) => {
                if (result.dismiss === Swal.DismissReason.cancel) {
                    showLicenseActions(licenseId);
                }
            });
        }
    } catch (error) {
        console.error('License details error:', error);
        showToast('Error loading license details', 'error');
    }
}

// Show license actions
function showLicenseActions(licenseId) {
    Swal.fire({
        title: 'License Actions',
        html: `
            <div class="text-left space-y-3">
                <button onclick="extendLicense(${licenseId})" class="w-full text-left p-3 bg-blue-50 hover:bg-blue-100 rounded-lg transition flex items-center">
                    <i class="fas fa-calendar-plus text-blue-600 mr-3"></i>
                    <div>
                        <p class="font-medium">Extend License</p>
                        <p class="text-sm text-gray-600">Add more days to this license</p>
                    </div>
                </button>
                
                <button onclick="resetLicense(${licenseId})" class="w-full text-left p-3 bg-yellow-50 hover:bg-yellow-100 rounded-lg transition flex items-center">
                    <i class="fas fa-redo text-yellow-600 mr-3"></i>
                    <div>
                        <p class="font-medium">Reset License</p>
                        <p class="text-sm text-gray-600">Clear all activations and reset counter</p>
                    </div>
                </button>
                
                <button onclick="banLicense(${licenseId})" class="w-full text-left p-3 bg-red-50 hover:bg-red-100 rounded-lg transition flex items-center">
                    <i class="fas fa-ban text-red-600 mr-3"></i>
                    <div>
                        <p class="font-medium">Ban License</p>
                        <p class="text-sm text-gray-600">Permanently disable this license</p>
                    </div>
                </button>
            </div>
        `,
        showConfirmButton: false,
        showCloseButton: true,
        width: '400px'
    });
}

// Extend license
async function extendLicense(licenseId) {
    const { value: days } = await Swal.fire({
        title: 'Extend License',
        input: 'number',
        inputLabel: 'Number of days to add',
        inputValue: 30,
        inputAttributes: {
            min: 1,
            step: 1
        },
        showCancelButton: true,
        confirmButtonText: 'Extend',
        cancelButtonText: 'Cancel',
        inputValidator: (value) => {
            if (!value || value < 1) {
                return 'Please enter a valid number of days';
            }
        }
    });
    
    if (days) {
        try {
            const response = await fetch(`/api/admin/licenses/${licenseId}/extend`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ days: parseInt(days) })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast(`License extended by ${days} days`, 'success');
                await loadLicenses();
                await loadDashboard();
            } else {
                showToast(data.message, 'error');
            }
        } catch (error) {
            console.error('Extend license error:', error);
            showToast('Connection error', 'error');
        }
    }
}

// Reset license
async function resetLicense(licenseId) {
    const { isConfirmed } = await Swal.fire({
        title: 'Reset License?',
        text: 'This will clear all device activations and reset the activation counter.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Yes, reset it',
        cancelButtonText: 'Cancel',
        confirmButtonColor: '#f59e0b',
        reverseButtons: true
    });
    
    if (isConfirmed) {
        try {
            const response = await fetch(`/api/admin/licenses/${licenseId}/reset`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast('License reset successfully', 'success');
                await loadLicenses();
                await loadDashboard();
            } else {
                showToast(data.message, 'error');
            }
        } catch (error) {
            console.error('Reset license error:', error);
            showToast('Connection error', 'error');
        }
    }
}

// Ban license
async function banLicense(licenseId) {
    const { value: reason } = await Swal.fire({
        title: 'Ban License',
        input: 'text',
        inputLabel: 'Reason for banning',
        inputPlaceholder: 'Enter reason...',
        showCancelButton: true,
        confirmButtonText: 'Ban License',
        cancelButtonText: 'Cancel',
        confirmButtonColor: '#ef4444',
        inputValidator: (value) => {
            if (!value) {
                return 'Please enter a reason';
            }
        }
    });
    
    if (reason) {
        try {
            const response = await fetch(`/api/admin/licenses/${licenseId}/ban`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ reason: reason })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast('License banned successfully', 'success');
                await loadLicenses();
                await loadDashboard();
            } else {
                showToast(data.message, 'error');
            }
        } catch (error) {
            console.error('Ban license error:', error);
            showToast('Connection error', 'error');
        }
    }
}

// Delete license
async function deleteLicense(licenseId) {
    const { isConfirmed } = await Swal.fire({
        title: 'Delete License?',
        text: 'This action cannot be undone. All activations will be deleted.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Yes, delete it',
        cancelButtonText: 'Cancel',
        confirmButtonColor: '#ef4444',
        reverseButtons: true
    });
    
    if (isConfirmed) {
        try {
            const response = await fetch(`/api/admin/licenses/${licenseId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast('License deleted successfully', 'success');
                await loadLicenses();
                await loadDashboard();
            } else {
                showToast(data.message, 'error');
            }
        } catch (error) {
            console.error('Delete license error:', error);
            showToast('Connection error', 'error');
        }
    }
}

// Bulk actions
function showBulkActions() {
    if (selectedLicenses.size === 0) {
        showToast('Please select at least one license', 'warning');
        return;
    }
    
    Swal.fire({
        title: 'Bulk Actions',
        html: `
            <div class="text-left space-y-3">
                <button onclick="bulkAction('activate')" class="w-full text-left p-3 bg-green-50 hover:bg-green-100 rounded-lg transition">
                    <i class="fas fa-play text-green-600 mr-2"></i>
                    <span class="font-medium">Activate</span>
                    <p class="text-sm text-gray-600 mt-1">Activate ${selectedLicenses.size} selected licenses</p>
                </button>
                
                <button onclick="bulkAction('deactivate')" class="w-full text-left p-3 bg-yellow-50 hover:bg-yellow-100 rounded-lg transition">
                    <i class="fas fa-pause text-yellow-600 mr-2"></i>
                    <span class="font-medium">Deactivate</span>
                    <p class="text-sm text-gray-600 mt-1">Deactivate ${selectedLicenses.size} selected licenses</p>
                </button>
                
                <button onclick="bulkAction('reset')" class="w-full text-left p-3 bg-blue-50 hover:bg-blue-100 rounded-lg transition">
                    <i class="fas fa-redo text-blue-600 mr-2"></i>
                    <span class="font-medium">Reset</span>
                    <p class="text-sm text-gray-600 mt-1">Reset ${selectedLicenses.size} selected licenses</p>
                </button>
                
                <button onclick="bulkAction('delete')" class="w-full text-left p-3 bg-red-50 hover:bg-red-100 rounded-lg transition border border-red-200">
                    <i class="fas fa-trash text-red-600 mr-2"></i>
                    <span class="font-medium text-red-600">Delete</span>
                    <p class="text-sm text-gray-600 mt-1">Delete ${selectedLicenses.size} selected licenses</p>
                </button>
            </div>
        `,
        showConfirmButton: false,
        showCloseButton: true,
        width: '400px'
    });
}

async function bulkAction(action) {
    const actionNames = {
        'activate': 'activate',
        'deactivate': 'deactivate',
        'reset': 'reset',
        'delete': 'delete'
    };
    
    const { isConfirmed } = await Swal.fire({
        title: `Confirm ${actionNames[action]}`,
        text: `Are you sure you want to ${actionNames[action]} ${selectedLicenses.size} licenses?`,
        icon: action === 'delete' ? 'warning' : 'question',
        showCancelButton: true,
        confirmButtonText: action === 'delete' ? 'Delete Permanently' : `Yes, ${actionNames[action]}`,
        cancelButtonText: 'Cancel',
        confirmButtonColor: action === 'delete' ? '#ef4444' : '#3b82f6',
        reverseButtons: true
    });
    
    if (isConfirmed) {
        try {
            const response = await fetch('/api/admin/licenses/bulk', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    action: action,
                    license_ids: Array.from(selectedLicenses)
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast(data.message, 'success');
                
                // Clear selection
                selectedLicenses.clear();
                document.getElementById('selectAll').checked = false;
                document.querySelectorAll('.license-checkbox').forEach(cb => cb.checked = false);
                
                // Reload data
                await loadLicenses();
                await loadDashboard();
            } else {
                showToast(data.message, 'error');
            }
        } catch (error) {
            console.error('Bulk action error:', error);
            showToast('Connection error', 'error');
        }
    }
}

// ============ SERVER KEY FUNCTIONS ============

// Load server keys
async function loadServerKeys() {
    try {
        const container = document.getElementById('serverKeysList');
        container.innerHTML = `
            <div class="col-span-3 text-center py-8">
                <div class="flex justify-center">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
                </div>
                <p class="mt-2 text-gray-500">Loading server keys...</p>
            </div>
        `;
        
        const response = await fetch('/api/admin/server-keys');
        const data = await response.json();
        
        if (data.success) {
            container.innerHTML = '';
            
            if (data.data.length === 0) {
                container.innerHTML = `
                    <div class="col-span-3 text-center py-8">
                        <i class="fas fa-key text-4xl mb-2 text-gray-300"></i>
                        <p class="text-gray-500">No server keys yet</p>
                        <button onclick="showCreateServerKeyModal()" class="mt-4 px-4 py-2 btn-success rounded-lg">
                            <i class="fas fa-plus mr-2"></i> Create Server Key
                        </button>
                    </div>
                `;
                return;
            }
            
            data.data.forEach(key => {
                const card = `
                    <div class="card p-4">
                        <div class="flex justify-between items-start mb-3">
                            <div>
                                <h4 class="font-bold text-gray-800">${key.key_name}</h4>
                                <div class="flex items-center mt-1">
                                    <div class="w-2 h-2 rounded-full ${key.status === 'active' ? 'bg-green-500' : 'bg-red-500'} mr-2"></div>
                                    <span class="text-xs ${key.status === 'active' ? 'text-green-600' : 'text-red-600'}">
                                        ${key.status === 'active' ? 'Active' : 'Inactive'}
                                    </span>
                                </div>
                            </div>
                            <button onclick="deleteServerKey(${key.id})" class="text-red-500 hover:text-red-700">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                        
                        <div class="mt-4">
                            <div class="flex items-center space-x-2">
                                <code class="flex-1 px-3 py-2 bg-gray-100 border border-gray-300 rounded text-gray-800 font-mono text-xs break-all">
                                    ${key.server_key}
                                </code>
                                <button onclick="copyToClipboard('${key.server_key}')" class="px-2 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300">
                                    <i class="fas fa-copy"></i>
                                </button>
                            </div>
                            
                            <div class="mt-4 text-xs text-gray-500 space-y-1">
                                <div class="flex justify-between">
                                    <span><i class="far fa-calendar mr-1"></i> Created:</span>
                                    <span>${formatDate(key.created_at)}</span>
                                </div>
                                <div class="flex justify-between">
                                    <span><i class="far fa-clock mr-1"></i> Last Used:</span>
                                    <span>${formatDate(key.last_used)}</span>
                                </div>
                                <div class="flex justify-between">
                                    <span><i class="fas fa-user-shield mr-1"></i> Permissions:</span>
                                    <span>${key.permissions}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                container.innerHTML += card;
            });
        }
    } catch (error) {
        console.error('Load server keys error:', error);
        const container = document.getElementById('serverKeysList');
        container.innerHTML = `
            <div class="col-span-3 text-center py-8 text-red-500">
                <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                <p>Error loading server keys</p>
            </div>
        `;
    }
}

// Create server key
async function showCreateServerKeyModal() {
    const { value: keyName } = await Swal.fire({
        title: 'Create Server Key',
        input: 'text',
        inputLabel: 'Key Name',
        inputPlaceholder: 'Enter a name for this key...',
        showCancelButton: true,
        confirmButtonText: 'Create Key',
        cancelButtonText: 'Cancel',
        confirmButtonColor: '#10b981',
        inputValidator: (value) => {
            if (!value) {
                return 'Please enter a key name';
            }
        }
    });
    
    if (keyName) {
        try {
            const response = await fetch('/api/admin/server-keys/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ key_name: keyName })
            });
            
            const data = await response.json();
            
            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Success!',
                    html: `
                        <p>Server key created successfully!</p>
                        <div class="mt-4 p-3 bg-gray-100 rounded">
                            <p class="font-mono text-sm break-all">${data.server_key}</p>
                            <p class="text-xs text-gray-600 mt-2">⚠️ Save this key - it won't be shown again!</p>
                        </div>
                        <button onclick="copyToClipboard('${data.server_key}')" class="mt-3 px-4 py-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition">
                            <i class="fas fa-copy mr-2"></i> Copy Server Key
                        </button>
                    `,
                    width: '600px'
                });
                
                // Reload server keys
                await loadServerKeys();
                await loadDashboard();
            } else {
                Swal.fire('Error!', data.message, 'error');
            }
        } catch (error) {
            console.error('Create server key error:', error);
            Swal.fire('Error!', 'Connection error', 'error');
        }
    }
}

// Delete server key
async function deleteServerKey(keyId) {
    const { isConfirmed } = await Swal.fire({
        title: 'Delete Server Key?',
        text: 'Applications using this key will no longer be able to access the server API.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel',
        confirmButtonColor: '#ef4444',
        reverseButtons: true
    });
    
    if (isConfirmed) {
        try {
            const response = await fetch(`/api/admin/server-keys/${keyId}/delete`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast('Server key deleted', 'success');
                await loadServerKeys();
                await loadDashboard();
            } else {
                showToast(data.message, 'error');
            }
        } catch (error) {
            console.error('Delete server key error:', error);
            showToast('Connection error', 'error');
        }
    }
}

// ============ API KEY FUNCTIONS ============

// Load API keys
async function loadApiKeys() {
    try {
        const container = document.getElementById('apiKeysList');
        container.innerHTML = `
            <div class="col-span-3 text-center py-8">
                <div class="flex justify-center">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600"></div>
                </div>
                <p class="mt-2 text-gray-500">Loading API keys...</p>
            </div>
        `;
        
        const response = await fetch('/api/admin/api-keys');
        const data = await response.json();
        
        if (data.success) {
            container.innerHTML = '';
            
            if (data.data.length === 0) {
                container.innerHTML = `
                    <div class="col-span-3 text-center py-8">
                        <i class="fas fa-code text-4xl mb-2 text-gray-300"></i>
                        <p class="text-gray-500">No API keys yet</p>
                        <button onclick="showCreateApiKeyModal()" class="mt-4 px-4 py-2 btn-success rounded-lg">
                            <i class="fas fa-plus mr-2"></i> Create API Key
                        </button>
                    </div>
                `;
                return;
            }
            
            data.data.forEach(key => {
                const card = `
                    <div class="card p-4">
                        <div class="flex justify-between items-start mb-3">
                            <div>
                                <h4 class="font-bold text-gray-800">${key.key_name}</h4>
                                <div class="flex items-center mt-1">
                                    <div class="w-2 h-2 rounded-full ${key.status === 'active' ? 'bg-green-500' : 'bg-red-500'} mr-2"></div>
                                    <span class="text-xs ${key.status === 'active' ? 'text-green-600' : 'text-red-600'}">
                                        ${key.status === 'active' ? 'Active' : 'Inactive'}
                                    </span>
                                </div>
                            </div>
                            <button onclick="deleteApiKey(${key.id})" class="text-red-500 hover:text-red-700">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                        
                        <div class="mt-4">
                            <div class="flex items-center space-x-2">
                                <code class="flex-1 px-3 py-2 bg-gray-100 border border-gray-300 rounded text-gray-800 font-mono text-xs break-all">
                                    ${key.api_key}
                                </code>
                                <button onclick="copyToClipboard('${key.api_key}')" class="px-2 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300">
                                    <i class="fas fa-copy"></i>
                                </button>
                            </div>
                            
                            <div class="mt-4 text-xs text-gray-500 space-y-1">
                                <div class="flex justify-between">
                                    <span><i class="far fa-calendar mr-1"></i> Created:</span>
                                    <span>${formatDate(key.created_at)}</span>
                                </div>
                                <div class="flex justify-between">
                                    <span><i class="far fa-clock mr-1"></i> Last Used:</span>
                                    <span>${formatDate(key.last_used)}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                container.innerHTML += card;
            });
        }
    } catch (error) {
        console.error('Load API keys error:', error);
        const container = document.getElementById('apiKeysList');
        container.innerHTML = `
            <div class="col-span-3 text-center py-8 text-red-500">
                <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                <p>Error loading API keys</p>
            </div>
        `;
    }
}

// Create API key
async function showCreateApiKeyModal() {
    const { value: keyName } = await Swal.fire({
        title: 'Create API Key',
        input: 'text',
        inputLabel: 'Key Name',
        inputPlaceholder: 'Enter a name for this key...',
        showCancelButton: true,
        confirmButtonText: 'Create Key',
        cancelButtonText: 'Cancel',
        confirmButtonColor: '#10b981',
        inputValidator: (value) => {
            if (!value) {
                return 'Please enter a key name';
            }
        }
    });
    
    if (keyName) {
        try {
            const response = await fetch('/api/admin/api-keys/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ key_name: keyName })
            });
            
            const data = await response.json();
            
            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Success!',
                    html: `
                        <p>API key created successfully!</p>
                        <div class="mt-4 p-3 bg-gray-100 rounded">
                            <p class="font-mono text-sm break-all">${data.api_key}</p>
                            <p class="text-xs text-gray-600 mt-2">⚠️ Save this key - it won't be shown again!</p>
                        </div>
                        <button onclick="copyToClipboard('${data.api_key}')" class="mt-3 px-4 py-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition">
                            <i class="fas fa-copy mr-2"></i> Copy API Key
                        </button>
                    `,
                    width: '600px'
                });
                
                // Reload API keys
                await loadApiKeys();
                await loadDashboard();
            } else {
                Swal.fire('Error!', data.message, 'error');
            }
        } catch (error) {
            console.error('Create API key error:', error);
            Swal.fire('Error!', 'Connection error', 'error');
        }
    }
}

// Delete API key
async function deleteApiKey(keyId) {
    const { isConfirmed } = await Swal.fire({
        title: 'Delete API Key?',
        text: 'Applications using this key will no longer be able to verify licenses.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel',
        confirmButtonColor: '#ef4444',
        reverseButtons: true
    });
    
    if (isConfirmed) {
        try {
            const response = await fetch(`/api/admin/api-keys/${keyId}/delete`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast('API key deleted', 'success');
                await loadApiKeys();
                await loadDashboard();
            } else {
                showToast(data.message, 'error');
            }
        } catch (error) {
            console.error('Delete API key error:', error);
            showToast('Connection error', 'error');
        }
    }
}

// ============ ACTIVITY LOGS ============

async function loadActivityLogs() {
    try {
        const container = document.getElementById('activityList');
        container.innerHTML = `
            <div class="text-center text-gray-500 py-8">
                <div class="flex justify-center">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
                </div>
                <p class="mt-2">Loading activity logs...</p>
            </div>
        `;
        
        const response = await fetch('/api/admin/activity?limit=50');
        const data = await response.json();
        
        if (data.success) {
            container.innerHTML = '';
            
            if (data.data.length === 0) {
                container.innerHTML = '<p class="text-gray-500 text-center py-8">No activity yet</p>';
                return;
            }
            
            data.data.forEach(log => {
                const icon = getActivityIcon(log.action);
                const color = getActivityColor(log.action);
                
                const item = `
                    <div class="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg">
                        <div class="${color} w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0">
                            <i class="${icon} text-white text-sm"></i>
                        </div>
                        <div class="flex-1">
                            <div class="flex justify-between">
                                <p class="font-medium text-gray-800">${formatAction(log.action)}</p>
                                <span class="text-xs text-gray-500">${formatDate(log.created_at)}</span>
                            </div>
                            <p class="text-sm text-gray-600">by ${log.username}</p>
                            ${log.details ? `<p class="text-xs text-gray-500 mt-1">${JSON.stringify(log.details)}</p>` : ''}
                        </div>
                    </div>
                `;
                container.innerHTML += item;
            });
        }
    } catch (error) {
        console.error('Activity logs error:', error);
        const container = document.getElementById('activityList');
        container.innerHTML = `
            <div class="text-center text-red-500 py-8">
                <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                <p>Error loading activity logs</p>
            </div>
        `;
    }
}

// ============ UTILITY FUNCTIONS ============

function refreshAllData() {
    const currentTab = document.querySelector('.tab-active').getAttribute('onclick').match(/switchTab\('([^']+)'\)/)[1];
    
    if (currentTab === 'dashboard') {
        loadDashboard();
    } else if (currentTab === 'licenses') {
        loadLicenses();
    } else if (currentTab === 'server-keys') {
        loadServerKeys();
    } else if (currentTab === 'api-keys') {
        loadApiKeys();
    } else if (currentTab === 'activity') {
        loadActivityLogs();
    }
    
    showToast('Data refreshed', 'success');
}

function exportLicenses() {
    alert('Export feature coming soon!');
}

// Select all licenses
document.getElementById('selectAll').addEventListener('change', function(e) {
    const checkboxes = document.querySelectorAll('.license-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.checked = e.target.checked;
        if (e.target.checked) {
            selectedLicenses.add(checkbox.value);
        } else {
            selectedLicenses.delete(checkbox.value);
        }
    });
});
