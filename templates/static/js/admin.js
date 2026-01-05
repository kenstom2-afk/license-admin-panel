// Toast notification system
let toastTimeout;

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    const icons = {
        success: '✓',
        error: '✗',
        info: 'ℹ',
        warning: '⚠'
    };
    
    const colors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        info: 'bg-blue-500',
        warning: 'bg-yellow-500'
    };
    
    toast.className = `fixed top-4 right-4 ${colors[type] || 'bg-gray-800'} text-white px-6 py-3 rounded-lg shadow-lg z-50 transform transition-transform duration-300`;
    toast.innerHTML = `
        <div class="flex items-center space-x-3">
            <span class="font-bold">${icons[type] || 'ℹ'}</span>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(toast);
    
    // Animate in
    setTimeout(() => {
        toast.style.transform = 'translateX(0)';
    }, 10);
    
    // Remove previous timeout
    if (toastTimeout) clearTimeout(toastTimeout);
    
    // Auto remove after 3 seconds
    toastTimeout = setTimeout(() => {
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    }, 3000);
}

// Logout function
async function logout() {
    if (confirm('Bạn có chắc chắn muốn đăng xuất?')) {
        try {
            const response = await fetch('/api/admin/logout', {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                window.location.href = '/login';
            } else {
                showToast('Lỗi khi đăng xuất', 'error');
            }
        } catch (error) {
            console.error('Logout error:', error);
            showToast('Lỗi kết nối đến server', 'error');
        }
    }
}

// Modal functions
function showCreateLicenseModal() {
    const modal = document.createElement('div');
    modal.id = 'createLicenseModal';
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4';
    modal.innerHTML = `
        <div class="bg-white rounded-xl shadow-lg w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div class="px-6 py-4 border-b border-gray-200 flex justify-between items-center sticky top-0 bg-white">
                <h3 class="text-lg font-bold text-gray-800">Tạo License mới</h3>
                <button onclick="hideCreateLicenseModal()" class="text-gray-400 hover:text-gray-600">
                    <i class="fas fa-times text-xl"></i>
                </button>
            </div>
            <div class="p-6">
                <form id="createLicenseForm">
                    <div class="space-y-4">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Sản phẩm *</label>
                            <input type="text" name="product" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" 
                                   placeholder="Nhập tên sản phẩm" required>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Chủ sở hữu</label>
                            <input type="text" name="owner" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" 
                                   placeholder="Nhập tên chủ sở hữu">
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Trạng thái</label>
                                <select name="status" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                                    <option value="active">Active</option>
                                    <option value="inactive">Inactive</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Số thiết bị tối đa</label>
                                <input type="number" name="max_devices" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" 
                                       value="1" min="1">
                            </div>
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Ngày hết hạn</label>
                            <input type="date" name="expires_at" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
                        </div>
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-1">Ghi chú</label>
                            <textarea name="notes" rows="3" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" 
                                      placeholder="Nhập ghi chú..."></textarea>
                        </div>
                    </div>
                    <div class="mt-6 flex justify-end space-x-3">
                        <button type="button" onclick="hideCreateLicenseModal()" class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition">Hủy</button>
                        <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center">
                            <i class="fas fa-key mr-2"></i> Tạo License
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Add form handler
    setTimeout(() => {
        document.getElementById('createLicenseForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const data = Object.fromEntries(formData.entries());
            
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Đang xử lý...';
            submitBtn.disabled = true;
            
            try {
                const response = await fetch('/api/admin/licenses/create', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    showToast(`Đã tạo license: ${result.license_key}`, 'success');
                    hideCreateLicenseModal();
                    await loadLicenses();
                    await loadStats();
                } else {
                    showToast(result.message || 'Lỗi khi tạo license', 'error');
                }
            } catch (error) {
                console.error('Error creating license:', error);
                showToast('Lỗi kết nối đến server', 'error');
            } finally {
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        });
    }, 100);
}

function hideCreateLicenseModal() {
    const modal = document.getElementById('createLicenseModal');
    if (modal) {
        modal.remove();
    }
}

function showCreateApiKeyModal() {
    const modal = document.createElement('div');
    modal.id = 'createApiKeyModal';
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4';
    modal.innerHTML = `
        <div class="bg-white rounded-xl shadow-lg w-full max-w-md">
            <div class="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
                <h3 class="text-lg font-bold text-gray-800">Tạo API Key mới</h3>
                <button onclick="hideCreateApiKeyModal()" class="text-gray-400 hover:text-gray-600">
                    <i class="fas fa-times text-xl"></i>
                </button>
            </div>
            <div class="p-6">
                <form id="createApiKeyForm">
                    <div class="mb-6">
                        <label class="block text-sm font-medium text-gray-700 mb-1">Tên API Key *</label>
                        <input type="text" name="name" class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500" 
                               placeholder="Nhập tên API Key" required>
                    </div>
                    <div id="newApiKey" class="hidden mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
                        <label class="block text-sm font-medium text-green-700 mb-1">API Key mới đã được tạo:</label>
                        <div class="flex items-center space-x-2 mt-2">
                            <code class="flex-1 px-3 py-2 bg-white border border-green-300 rounded text-green-800 font-mono text-sm break-all" id="generatedApiKey"></code>
                            <button type="button" onclick="copyApiKey()" class="px-3 py-2 bg-green-100 text-green-700 rounded hover:bg-green-200 transition">
                                <i class="fas fa-copy"></i>
                            </button>
                        </div>
                        <p class="text-xs text-green-600 mt-2">⚠️ Lưu lại ngay vì sẽ không hiển thị lại lần sau!</p>
                    </div>
                    <div class="flex justify-end space-x-3">
                        <button type="button" onclick="hideCreateApiKeyModal()" class="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition">Đóng</button>
                        <button type="submit" class="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition flex items-center">
                            <i class="fas fa-plus mr-2"></i> Tạo API Key
                        </button>
                    </div>
                </form>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Add form handler
    setTimeout(() => {
        document.getElementById('createApiKeyForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const data = Object.fromEntries(formData.entries());
            
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i> Đang xử lý...';
            submitBtn.disabled = true;
            
            try {
                const response = await fetch('/api/admin/apikeys/create', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    // Show the generated API key
                    document.getElementById('generatedApiKey').textContent = result.api_key;
                    document.getElementById('newApiKey').classList.remove('hidden');
                    showToast('Đã tạo API Key mới!', 'success');
                    
                    // Disable the submit button
                    submitBtn.disabled = true;
                    submitBtn.innerHTML = '<i class="fas fa-check mr-2"></i> Đã tạo';
                    
                    // Reload API keys list
                    await loadApiKeys();
                } else {
                    showToast(result.message || 'Lỗi khi tạo API Key', 'error');
                    submitBtn.innerHTML = originalText;
                    submitBtn.disabled = false;
                }
            } catch (error) {
                console.error('Error creating API key:', error);
                showToast('Lỗi kết nối đến server', 'error');
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        });
    }, 100);
}

function hideCreateApiKeyModal() {
    const modal = document.getElementById('createApiKeyModal');
    if (modal) {
        modal.remove();
    }
}

function copyApiKey() {
    const apiKeyElement = document.getElementById('generatedApiKey');
    const apiKey = apiKeyElement.textContent;
    
    navigator.clipboard.writeText(apiKey).then(() => {
        showToast('Đã sao chép API Key!', 'success');
    }).catch(err => {
        console.error('Copy failed:', err);
        showToast('Không thể sao chép', 'error');
    });
}

// Data loading functions
async function loadStats() {
    try {
        const response = await fetch('/api/admin/stats');
        const result = await response.json();
        
        if (result.success) {
            const data = result.data;
            document.getElementById('totalLicenses').textContent = data.total_licenses;
            document.getElementById('activeLicenses').textContent = data.active_licenses;
            document.getElementById('inactiveLicenses').textContent = data.inactive_licenses;
            document.getElementById('expiredLicenses').textContent = data.expired_licenses;
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function loadLicenses() {
    try {
        const tbody = document.getElementById('licenseTableBody');
        tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-8 text-center text-gray-500">Đang tải...</td></tr>';
        
        const response = await fetch('/api/admin/licenses');
        const result = await response.json();
        
        if (result.success) {
            const licenses = result.data;
            tbody.innerHTML = '';
            
            if (licenses.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-8 text-center text-gray-500">Chưa có license nào</td></tr>';
                return;
            }
            
            licenses.forEach(license => {
                let statusBadge = '';
                let statusColor = '';
                
                switch(license.status) {
                    case 'active':
                        statusBadge = 'Active';
                        statusColor = 'bg-green-100 text-green-800';
                        break;
                    case 'inactive':
                        statusBadge = 'Inactive';
                        statusColor = 'bg-yellow-100 text-yellow-800';
                        break;
                    case 'expired':
                        statusBadge = 'Expired';
                        statusColor = 'bg-red-100 text-red-800';
                        break;
                    default:
                        statusBadge = license.status;
                        statusColor = 'bg-gray-100 text-gray-800';
                }
                
                const expiresText = license.expires_at ? 
                    new Date(license.expires_at).toLocaleDateString('vi-VN') : 
                    'Không hết hạn';
                
                const row = `
                    <tr class="hover:bg-gray-50">
                        <td class="px-4 py-3 whitespace-nowrap">
                            <div class="font-mono text-sm font-medium text-gray-900">${license.license_key}</div>
                            <div class="text-xs text-gray-500">ID: ${license.id}</div>
                        </td>
                        <td class="px-4 py-3">
                            <div class="text-sm text-gray-900">${license.product}</div>
                        </td>
                        <td class="px-4 py-3">
                            <div class="text-sm text-gray-900">${license.owner || '-'}</div>
                        </td>
                        <td class="px-4 py-3">
                            <span class="px-2 py-1 text-xs font-medium ${statusColor} rounded-full">${statusBadge}</span>
                            <div class="text-xs text-gray-500 mt-1">Hết hạn: ${expiresText}</div>
                        </td>
                        <td class="px-4 py-3 whitespace-nowrap">
                            <button onclick="deleteLicense(${license.id})" class="px-3 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200 transition text-sm">
                                <i class="fas fa-trash mr-1"></i> Xóa
                            </button>
                        </td>
                    </tr>
                `;
                tbody.innerHTML += row;
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-8 text-center text-red-500">Lỗi khi tải dữ liệu</td></tr>';
        }
    } catch (error) {
        console.error('Error loading licenses:', error);
        const tbody = document.getElementById('licenseTableBody');
        tbody.innerHTML = '<tr><td colspan="5" class="px-4 py-8 text-center text-red-500">Lỗi kết nối server</td></tr>';
    }
}

async function loadApiKeys() {
    try {
        const container = document.getElementById('apiKeysList');
        container.innerHTML = '<div class="text-center text-gray-500 py-4">Đang tải...</div>';
        
        const response = await fetch('/api/admin/apikeys');
        const result = await response.json();
        
        if (result.success) {
            const apikeys = result.data;
            container.innerHTML = '';
            
            if (apikeys.length === 0) {
                container.innerHTML = '<div class="text-center text-gray-500 py-4">Chưa có API Key nào</div>';
                return;
            }
            
            apikeys.forEach(key => {
                const isActive = key.status === 'active';
                const card = `
                    <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition">
                        <div class="flex justify-between items-start mb-2">
                            <div>
                                <h4 class="font-medium text-gray-800">${key.name}</h4>
                                <div class="flex items-center mt-1">
                                    <div class="w-2 h-2 rounded-full ${isActive ? 'bg-green-500' : 'bg-red-500'} mr-2"></div>
                                    <span class="text-xs ${isActive ? 'text-green-600' : 'text-red-600'}">${key.status}</span>
                                </div>
                            </div>
                            <button onclick="deleteApiKey(${key.id})" class="text-red-500 hover:text-red-700 transition">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                        <div class="mt-3">
                            <div class="flex items-center space-x-2">
                                <code class="flex-1 px-3 py-2 bg-white border border-gray-300 rounded text-gray-800 font-mono text-xs break-all">${key.key}</code>
                                <button onclick="copyToClipboard('${key.key}')" class="px-2 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition">
                                    <i class="fas fa-copy"></i>
                                </button>
                            </div>
                            <div class="text-xs text-gray-500 mt-2">
                                <i class="far fa-clock mr-1"></i> ${new Date(key.created_at).toLocaleString('vi-VN')}
                            </div>
                        </div>
                    </div>
                `;
                container.innerHTML += card;
            });
        } else {
            container.innerHTML = '<div class="text-center text-red-500 py-4">Lỗi khi tải dữ liệu</div>';
        }
    } catch (error) {
        console.error('Error loading API keys:', error);
        const container = document.getElementById('apiKeysList');
        container.innerHTML = '<div class="text-center text-red-500 py-4">Lỗi kết nối server</div>';
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Đã sao chép vào clipboard!', 'success');
    }).catch(err => {
        console.error('Copy failed:', err);
        showToast('Không thể sao chép', 'error');
    });
}

async function refreshData() {
    try {
        showToast('Đang làm mới dữ liệu...', 'info');
        await Promise.all([
            loadStats(),
            loadLicenses(),
            loadApiKeys()
        ]);
        showToast('Đã làm mới dữ liệu!', 'success');
    } catch (error) {
        console.error('Refresh error:', error);
        showToast('Lỗi khi làm mới dữ liệu', 'error');
    }
}

// Delete functions
async function deleteLicense(id) {
    if (!confirm('Bạn có chắc chắn muốn xóa license này?')) return;
    
    try {
        const response = await fetch(`/api/admin/licenses/delete/${id}`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('Đã xóa license!', 'success');
            await refreshData();
        } else {
            showToast(result.message || 'Lỗi khi xóa license', 'error');
        }
    } catch (error) {
        console.error('Error deleting license:', error);
        showToast('Lỗi kết nối đến server', 'error');
    }
}

async function deleteApiKey(id) {
    if (!confirm('Bạn có chắc chắn muốn xóa API Key này?')) return;
    
    try {
        const response = await fetch(`/api/admin/apikeys/delete/${id}`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('Đã xóa API Key!', 'success');
            await loadApiKeys();
        } else {
            showToast(result.message || 'Lỗi khi xóa API Key', 'error');
        }
    } catch (error) {
        console.error('Error deleting API key:', error);
        showToast('Lỗi kết nối đến server', 'error');
    }
}

// Utility functions
function exportLicenses() {
    showToast('Tính năng đang phát triển!', 'info');
}

function showSystemInfo() {
    fetch('/api/admin/debug')
        .then(response => response.json())
        .then(data => {
            alert(`Thông tin hệ thống:\n\n` +
                  `Trạng thái: ${data.status}\n` +
                  `Thời gian server: ${new Date(data.server_time).toLocaleString('vi-VN')}\n` +
                  `Phiên bản: ${data.version}\n` +
                  `Môi trường: ${data.environment || 'development'}`);
        })
        .catch(error => {
            console.error('Error getting system info:', error);
            showToast('Lỗi khi lấy thông tin hệ thống', 'error');
        });
}

// Initialize
document.addEventListener('DOMContentLoaded', async function() {
    // Check authentication
    try {
        await fetch('/api/admin/stats');
    } catch (error) {
        window.location.href = '/login';
        return;
    }
    
    // Load initial data
    await refreshData();
    
    // Auto refresh stats every 30 seconds
    setInterval(loadStats, 30000);
    
    // Server status check
    setInterval(async () => {
        try {
            await fetch('/api/admin/debug');
            const statusElement = document.getElementById('serverStatus');
            if (statusElement) {
                statusElement.innerHTML = '<i class="fas fa-circle text-xs mr-1"></i> Online';
                statusElement.className = 'px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800';
            }
        } catch (error) {
            const statusElement = document.getElementById('serverStatus');
            if (statusElement) {
                statusElement.innerHTML = '<i class="fas fa-circle text-xs mr-1"></i> Offline';
                statusElement.className = 'px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800';
            }
        }
    }, 10000);
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.key === 'F5' || (e.ctrlKey && e.key === 'r')) {
            e.preventDefault();
            refreshData();
        }
        if (e.key === 'Escape') {
            hideCreateLicenseModal();
            hideCreateApiKeyModal();
        }
    });
});
