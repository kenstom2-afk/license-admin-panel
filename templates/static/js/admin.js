// Global variables
let currentPage = 1;
const licensesPerPage = 10;
let totalLicenses = 0;
let selectedLicenses = new Set();

// Toast notification
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
    
    // Auto remove after 3 seconds
    setTimeout(() => {
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
    const { value: confirm } = await Swal.fire({
        title: 'Đăng xuất?',
        text: 'Bạn có chắc chắn muốn đăng xuất?',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Đăng xuất',
        cancelButtonText: 'Hủy',
        confirmButtonColor: '#ef4444'
    });
    
    if (confirm) {
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

// Load stats
async function loadStats() {
    try {
        const response = await fetch('/api/admin/stats');
        const result = await response.json();
        
        if (result.success) {
            const data = result.data;
            document.getElementById('totalLicenses').textContent = data.total_licenses;
            document.getElementById('activeLicenses').textContent = data.active_licenses;
            document.getElementById('expiredLicenses').textContent = data.expired_licenses;
            document.getElementById('todayLicenses').textContent = data.today_licenses;
            document.getElementById('expiringSoon').textContent = data.expiring_soon;
            document.getElementById('activeApiKeys').textContent = data.active_api_keys;
            
            // Update server status
            const statusElement = document.getElementById('serverStatus');
            if (statusElement) {
                statusElement.innerHTML = `
                    <div class="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                    <span class="text-sm font-medium">Online</span>
                `;
            }
        }
    } catch (error) {
        console.error('Error loading stats:', error);
        const statusElement = document.getElementById('serverStatus');
        if (statusElement) {
            statusElement.innerHTML = `
                <div class="w-2 h-2 bg-red-400 rounded-full animate-pulse"></div>
                <span class="text-sm font-medium">Offline</span>
            `;
        }
    }
}

// Load licenses
async function loadLicenses() {
    try {
        const search = document.getElementById('searchLicense').value;
        const status = document.getElementById('filterStatus').value;
        
        let url = `/api/admin/licenses?page=${currentPage}&limit=${licensesPerPage}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (status) url += `&status=${status}`;
        
        const tbody = document.getElementById('licenseTableBody');
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="px-4 py-8 text-center text-gray-500">
                    <div class="flex justify-center">
                        <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                    </div>
                    <p class="mt-2">Đang tải dữ liệu...</p>
                </td>
            </tr>
        `;
        
        const response = await fetch(url);
        const result = await response.json();
        
        if (result.success) {
            const licenses = result.data;
            totalLicenses = licenses.length;
            
            tbody.innerHTML = '';
            selectedLicenses.clear();
            
            if (licenses.length === 0) {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="7" class="px-4 py-8 text-center text-gray-500">
                            <i class="fas fa-inbox text-4xl mb-2 text-gray-300"></i>
                            <p>Không tìm thấy license nào</p>
                        </td>
                    </tr>
                `;
                updatePagination();
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
                    case 'banned':
                        statusBadge = 'Banned';
                        statusColor = 'bg-gray-100 text-gray-800';
                        break;
                }
                
                const expiresText = license.expires_at ? 
                    new Date(license.expires_at).toLocaleDateString('vi-VN') : 
                    'Không hết hạn';
                
                const daysLeft = license.days_left !== null ? 
                    `<span class="text-xs ${license.days_left < 7 ? 'text-red-600 font-bold' : 'text-gray-500'}">
                        (còn ${license.days_left} ngày)
                    </span>` : '';
                
                const row = `
                    <tr class="hover:bg-gray-50" data-license-id="${license.id}">
                        <td class="px-4 py-3">
                            <input type="checkbox" class="license-checkbox rounded" value="${license.id}">
                        </td>
                        <td class="px-4 py-3">
                            <div class="font-mono text-sm font-medium text-gray-900">${license.license_key}</div>
                            <div class="text-xs text-gray-500">ID: ${license.id}</div>
                        </td>
                        <td class="px-4 py-3">
                            <div class="text-sm text-gray-900 font-medium">${license.product}</div>
                            <div class="text-xs text-gray-500">Devices: ${license.max_devices}</div>
                        </td>
                        <td class="px-4 py-3">
                            <div class="text-sm text-gray-900">${license.owner || '-'}</div>
                        </td>
                        <td class="px-4 py-3">
                            <span class="px-2 py-1 text-xs font-medium ${statusColor} rounded-full">${statusBadge}</span>
                            ${license.hwid_lock ? '<i class="fas fa-lock text-xs text-gray-400 ml-1" title="HWID Locked"></i>' : ''}
                        </td>
                        <td class="px-4 py-3">
                            <div class="text-sm">${expiresText}</div>
                            ${daysLeft}
                        </td>
                        <td class="px-4 py-3 whitespace-nowrap">
                            <div class="flex space-x-1">
                                <button onclick="showLicenseDetails(${license.id})" class="px-2 py-1 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition text-xs" title="Chi tiết">
                                    <i class="fas fa-eye"></i>
                                </button>
                                <button onclick="editLicense(${license.id})" class="px-2 py-1 bg-yellow-100 text-yellow-700 rounded hover:bg-yellow-200 transition text-xs" title="Sửa">
                                    <i class="fas fa-edit"></i>
                                </button>
                                <button onclick="showLicenseActions(${license.id})" class="px-2 py-1 bg-purple-100 text-purple-700 rounded hover:bg-purple-200 transition text-xs" title="Hành động">
                                    <i class="fas fa-cog"></i>
                                </button>
                                <button onclick="deleteLicense(${license.id})" class="px-2 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200 transition text-xs" title="Xóa">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </td>
                    </tr>
                `;
                tbody.innerHTML += row;
            });
            
            // Add event listeners for checkboxes
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
            
            updatePagination();
            updateLicenseCount();
        } else {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" class="px-4 py-8 text-center text-red-500">
                        <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                        <p>Lỗi khi tải dữ liệu</p>
                    </td>
                </tr>
            `;
        }
    } catch (error) {
        console.error('Error loading licenses:', error);
        const tbody = document.getElementById('licenseTableBody');
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="px-4 py-8 text-center text-red-500">
                    <i class="fas fa-wifi-slash text-2xl mb-2"></i>
                    <p>Lỗi kết nối server</p>
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

function updatePagination() {
    const totalPages = Math.ceil(totalLicenses / licensesPerPage);
    const currentPageElement = document.getElementById('currentPage');
    const prevButton = document.getElementById('prevPage');
    const nextButton = document.getElementById('nextPage');
    
    currentPageElement.textContent = currentPage;
    prevButton.disabled = currentPage === 1;
    nextButton.disabled = currentPage === totalPages || totalPages === 0;
}

function changePage(delta) {
    const newPage = currentPage + delta;
    const totalPages = Math.ceil(totalLicenses / licensesPerPage);
    
    if (newPage >= 1 && newPage <= totalPages) {
        currentPage = newPage;
        loadLicenses();
    }
}

function updateLicenseCount() {
    const element = document.getElementById('licenseCount');
    const start = (currentPage - 1) * licensesPerPage + 1;
    const end = Math.min(currentPage * licensesPerPage, totalLicenses);
    element.textContent = `Hiển thị ${start}-${end} của ${totalLicenses} license`;
}

// License actions modals
function showCreateLicenseModal() {
    Swal.fire({
        title: 'Tạo License mới',
        html: `
            <div class="text-left">
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Sản phẩm *</label>
                    <input type="text" id="product" class="swal2-input" placeholder="Tên sản phẩm" required>
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Chủ sở hữu</label>
                    <input type="text" id="owner" class="swal2-input" placeholder="Tên chủ sở hữu">
                </div>
                <div class="grid grid-cols-2 gap-4 mb-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Trạng thái</label>
                        <select id="status" class="swal2-input">
                            <option value="active">Active</option>
                            <option value="inactive">Inactive</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Số ngày *</label>
                        <input type="number" id="custom_days" class="swal2-input" value="30" min="1" required>
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-4 mb-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Max Devices</label>
                        <input type="number" id="max_devices" class="swal2-input" value="1" min="1">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Auto Renew</label>
                        <select id="auto_renew" class="swal2-input">
                            <option value="false">Không</option>
                            <option value="true">Có</option>
                        </select>
                    </div>
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">License Key tùy chỉnh</label>
                    <input type="text" id="custom_key" class="swal2-input" placeholder="Để trống để tự động tạo">
                    <p class="text-xs text-gray-500 mt-1">Format: chữ hoa, số và dấu gạch ngang, 8-50 ký tự</p>
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">HWID Lock</label>
                    <input type="text" id="hwid_lock" class="swal2-input" placeholder="HWID1,HWID2,... (để trống nếu không lock)">
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">IP Lock</label>
                    <input type="text" id="ip_lock" class="swal2-input" placeholder="IP1,IP2,... (để trống nếu không lock)">
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Ghi chú</label>
                    <textarea id="notes" class="swal2-textarea" rows="3" placeholder="Ghi chú..."></textarea>
                </div>
            </div>
        `,
        showCancelButton: true,
        confirmButtonText: 'Tạo License',
        cancelButtonText: 'Hủy',
        confirmButtonColor: '#3b82f6',
        preConfirm: () => {
            const product = document.getElementById('product').value.trim();
            const custom_days = document.getElementById('custom_days').value;
            
            if (!product) {
                Swal.showValidationMessage('Vui lòng nhập tên sản phẩm');
                return false;
            }
            
            if (!custom_days || custom_days < 1) {
                Swal.showValidationMessage('Số ngày phải lớn hơn 0');
                return false;
            }
            
            return {
                product: product,
                owner: document.getElementById('owner').value.trim(),
                status: document.getElementById('status').value,
                custom_days: parseInt(custom_days),
                max_devices: parseInt(document.getElementById('max_devices').value),
                auto_renew: document.getElementById('auto_renew').value === 'true',
                custom_key: document.getElementById('custom_key').value.trim(),
                hwid_lock: document.getElementById('hwid_lock').value.trim(),
                ip_lock: document.getElementById('ip_lock').value.trim(),
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
                        title: 'Thành công!',
                        html: `
                            <p>Đã tạo license thành công!</p>
                            <div class="mt-4 p-3 bg-gray-100 rounded">
                                <p class="font-mono text-sm break-all">${data.license_key}</p>
                                <p class="text-xs text-gray-600 mt-1">Hết hạn: ${data.expires_at}</p>
                            </div>
                            <button onclick="copyToClipboard('${data.license_key}')" class="mt-3 px-3 py-1 bg-blue-100 text-blue-700 rounded text-sm">
                                <i class="fas fa-copy mr-1"></i> Sao chép
                            </button>
                        `
                    });
                    
                    // Reload licenses list
                    await loadLicenses();
                    await loadStats();
                } else {
                    Swal.fire('Lỗi!', data.message || 'Không thể tạo license', 'error');
                }
            } catch (error) {
                console.error('Create license error:', error);
                Swal.fire('Lỗi!', 'Lỗi kết nối đến server', 'error');
            }
        }
    });
}

async function showLicenseDetails(licenseId) {
    try {
        // Get license details
        const response = await fetch(`/api/admin/licenses`);
        const result = await response.json();
        
        if (result.success) {
            const license = result.data.find(l => l.id === licenseId);
            if (!license) {
                showToast('Không tìm thấy license', 'error');
                return;
            }
            
            // Get activations
            const activationsRes = await fetch(`/api/admin/licenses/activations/${licenseId}`);
            const activationsResult = await activationsRes.json();
            const activations = activationsResult.success ? activationsResult.data : [];
            
            let statusColor = '';
            switch(license.status) {
                case 'active': statusColor = 'text-green-600'; break;
                case 'inactive': statusColor = 'text-yellow-600'; break;
                case 'expired': statusColor = 'text-red-600'; break;
                case 'banned': statusColor = 'text-gray-600'; break;
            }
            
            Swal.fire({
                title: 'Chi tiết License',
                html: `
                    <div class="text-left space-y-4">
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <p class="text-sm text-gray-600">License Key</p>
                                <p class="font-mono font-bold">${license.license_key}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">Trạng thái</p>
                                <p class="font-bold ${statusColor}">${license.status.toUpperCase()}</p>
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <p class="text-sm text-gray-600">Sản phẩm</p>
                                <p class="font-medium">${license.product}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">Chủ sở hữu</p>
                                <p class="font-medium">${license.owner || '-'}</p>
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <p class="text-sm text-gray-600">Ngày tạo</p>
                                <p>${new Date(license.created_at).toLocaleString('vi-VN')}</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">Hết hạn</p>
                                <p>${license.expires_at ? new Date(license.expires_at).toLocaleString('vi-VN') : 'Không hết hạn'}</p>
                            </div>
                        </div>
                        
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <p class="text-sm text-gray-600">Số ngày</p>
                                <p>${license.custom_days} ngày (24h/ngày)</p>
                            </div>
                            <div>
                                <p class="text-sm text-gray-600">Max Devices</p>
                                <p>${license.max_devices}</p>
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
                                <p class="text-sm text-gray-600">Ghi chú</p>
                                <p class="text-sm whitespace-pre-wrap">${license.notes}</p>
                            </div>
                        ` : ''}
                        
                        <div>
                            <p class="text-sm text-gray-600 font-medium mb-2">Activations (${activations.length}/${license.max_devices})</p>
                            ${activations.length > 0 ? `
                                <div class="max-h-40 overflow-y-auto">
                                    ${activations.map(act => `
                                        <div class="mb-2 p-2 bg-gray-50 rounded">
                                            <div class="flex justify-between text-sm">
                                                <span class="font-mono">${act.hwid}</span>
                                                <span class="${act.is_active ? 'text-green-600' : 'text-gray-400'}">
                                                    ${act.is_active ? 'Active' : 'Inactive'}
                                                </span>
                                            </div>
                                            <div class="text-xs text-gray-500">
                                                IP: ${act.ip_address || 'N/A'} | 
                                                Last: ${act.last_check ? new Date(act.last_check).toLocaleString('vi-VN') : 'N/A'}
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            ` : '<p class="text-sm text-gray-500">Chưa có activation nào</p>'}
                        </div>
                    </div>
                `,
                showCancelButton: true,
                confirmButtonText: 'Đóng',
                cancelButtonText: 'Hành động',
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
        showToast('Lỗi khi lấy thông tin license', 'error');
    }
}

async function editLicense(licenseId) {
    try {
        const response = await fetch(`/api/admin/licenses`);
        const result = await response.json();
        
        if (result.success) {
            const license = result.data.find(l => l.id === licenseId);
            if (!license) {
                showToast('Không tìm thấy license', 'error');
                return;
            }
            
            Swal.fire({
                title: 'Chỉnh sửa License',
                html: `
                    <div class="text-left">
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-1">License Key</label>
                            <input type="text" value="${license.license_key}" class="swal2-input" readonly>
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-1">Sản phẩm *</label>
                            <input type="text" id="product" class="swal2-input" value="${license.product}" required>
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-1">Chủ sở hữu</label>
                            <input type="text" id="owner" class="swal2-input" value="${license.owner || ''}">
                        </div>
                        <div class="grid grid-cols-2 gap-4 mb-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Trạng thái</label>
                                <select id="status" class="swal2-input">
                                    <option value="active" ${license.status === 'active' ? 'selected' : ''}>Active</option>
                                    <option value="inactive" ${license.status === 'inactive' ? 'selected' : ''}>Inactive</option>
                                    <option value="expired" ${license.status === 'expired' ? 'selected' : ''}>Expired</option>
                                    <option value="banned" ${license.status === 'banned' ? 'selected' : ''}>Banned</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Số ngày</label>
                                <input type="number" id="custom_days" class="swal2-input" value="${license.custom_days}" min="1">
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-4 mb-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Max Devices</label>
                                <input type="number" id="max_devices" class="swal2-input" value="${license.max_devices}" min="1">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700 mb-1">Auto Renew</label>
                                <select id="auto_renew" class="swal2-input">
                                    <option value="false" ${!license.auto_renew ? 'selected' : ''}>Không</option>
                                    <option value="true" ${license.auto_renew ? 'selected' : ''}>Có</option>
                                </select>
                            </div>
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-1">HWID Lock</label>
                            <input type="text" id="hwid_lock" class="swal2-input" value="${license.hwid_lock || ''}" placeholder="HWID1,HWID2,...">
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-1">IP Lock</label>
                            <input type="text" id="ip_lock" class="swal2-input" value="${license.ip_lock || ''}" placeholder="IP1,IP2,...">
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-1">Ghi chú</label>
                            <textarea id="notes" class="swal2-textarea" rows="3">${license.notes || ''}</textarea>
                        </div>
                    </div>
                `,
                showCancelButton: true,
                confirmButtonText: 'Cập nhật',
                cancelButtonText: 'Hủy',
                confirmButtonColor: '#3b82f6',
                preConfirm: () => {
                    const product = document.getElementById('product').value.trim();
                    if (!product) {
                        Swal.showValidationMessage('Vui lòng nhập tên sản phẩm');
                        return false;
                    }
                    
                    return {
                        product: product,
                        owner: document.getElementById('owner').value.trim(),
                        status: document.getElementById('status').value,
                        custom_days: parseInt(document.getElementById('custom_days').value),
                        max_devices: parseInt(document.getElementById('max_devices').value),
                        auto_renew: document.getElementById('auto_renew').value === 'true',
                        hwid_lock: document.getElementById('hwid_lock').value.trim(),
                        ip_lock: document.getElementById('ip_lock').value.trim(),
                        notes: document.getElementById('notes').value.trim()
                    };
                }
            }).then(async (result) => {
                if (result.isConfirmed) {
                    try {
                        const updateRes = await fetch(`/api/admin/licenses/update/${licenseId}`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify(result.value)
                        });
                        
                        const data = await updateRes.json();
                        
                        if (data.success) {
                            showToast('Đã cập nhật license thành công', 'success');
                            await loadLicenses();
                        } else {
                            Swal.fire('Lỗi!', data.message || 'Không thể cập nhật license', 'error');
                        }
                    } catch (error) {
                        console.error('Update license error:', error);
                        Swal.fire('Lỗi!', 'Lỗi kết nối đến server', 'error');
                    }
                }
            });
        }
    } catch (error) {
        console.error('Edit license error:', error);
        showToast('Lỗi khi lấy thông tin license', 'error');
    }
}

function showLicenseActions(licenseId) {
    Swal.fire({
        title: 'Hành động với License',
        html: `
            <div class="text-left space-y-3">
                <button onclick="extendLicense(${licenseId})" class="w-full text-left p-3 bg-blue-50 hover:bg-blue-100 rounded-lg transition">
                    <i class="fas fa-calendar-plus text-blue-600 mr-2"></i>
                    <span class="font-medium">Gia hạn thêm ngày</span>
                    <p class="text-sm text-gray-600 mt-1">Thêm số ngày sử dụng cho license</p>
                </button>
                
                <button onclick="resetLicense(${licenseId})" class="w-full text-left p-3 bg-yellow-50 hover:bg-yellow-100 rounded-lg transition">
                    <i class="fas fa-redo text-yellow-600 mr-2"></i>
                    <span class="font-medium">Reset License</span>
                    <p class="text-sm text-gray-600 mt-1">Xóa tất cả activations, reset về trạng thái ban đầu</p>
                </button>
                
                <button onclick="banLicense(${licenseId})" class="w-full text-left p-3 bg-red-50 hover:bg-red-100 rounded-lg transition">
                    <i class="fas fa-ban text-red-600 mr-2"></i>
                    <span class="font-medium">Khóa License</span>
                    <p class="text-sm text-gray-600 mt-1">Khóa license vĩnh viễn (ban)</p>
                </button>
                
                <button onclick="showLicenseActivations(${licenseId})" class="w-full text-left p-3 bg-purple-50 hover:bg-purple-100 rounded-lg transition">
                    <i class="fas fa-list text-purple-600 mr-2"></i>
                    <span class="font-medium">Xem Activations</span>
                    <p class="text-sm text-gray-600 mt-1">Xem danh sách các thiết bị đã kích hoạt</p>
                </button>
            </div>
        `,
        showConfirmButton: false,
        showCloseButton: true,
        width: '500px'
    });
}

async function extendLicense(licenseId) {
    const { value: days } = await Swal.fire({
        title: 'Gia hạn License',
        input: 'number',
        inputLabel: 'Số ngày muốn thêm',
        inputValue: 30,
        inputAttributes: {
            min: 1,
            step: 1
        },
        showCancelButton: true,
        confirmButtonText: 'Gia hạn',
        cancelButtonText: 'Hủy',
        inputValidator: (value) => {
            if (!value || value < 1) {
                return 'Vui lòng nhập số ngày hợp lệ';
            }
        }
    });
    
    if (days) {
        try {
            const response = await fetch(`/api/admin/licenses/extend/${licenseId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ days: parseInt(days) })
            });
            
            const data = await response.json();
            
            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Thành công!',
                    html: `
                        <p>Đã gia hạn license thêm ${days} ngày</p>
                        <p class="text-sm text-gray-600 mt-2">Hết hạn mới: ${data.new_expiry}</p>
                    `
                });
                await loadLicenses();
            } else {
                Swal.fire('Lỗi!', data.message || 'Không thể gia hạn license', 'error');
            }
        } catch (error) {
            console.error('Extend license error:', error);
            Swal.fire('Lỗi!', 'Lỗi kết nối đến server', 'error');
        }
    }
}

async function resetLicense(licenseId) {
    const { value: confirm } = await Swal.fire({
        title: 'Reset License?',
        text: 'Tất cả activations sẽ bị xóa. License sẽ được reset về trạng thái ban đầu.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Reset',
        cancelButtonText: 'Hủy',
        confirmButtonColor: '#f59e0b',
        reverseButtons: true
    });
    
    if (confirm) {
        try {
            const response = await fetch(`/api/admin/licenses/reset/${licenseId}`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast('Đã reset license thành công', 'success');
                await loadLicenses();
            } else {
                Swal.fire('Lỗi!', data.message || 'Không thể reset license', 'error');
            }
        } catch (error) {
            console.error('Reset license error:', error);
            Swal.fire('Lỗi!', 'Lỗi kết nối đến server', 'error');
        }
    }
}

async function banLicense(licenseId) {
    const { value: reason } = await Swal.fire({
        title: 'Khóa License',
        input: 'text',
        inputLabel: 'Lý do khóa',
        inputPlaceholder: 'Nhập lý do khóa license...',
        showCancelButton: true,
        confirmButtonText: 'Khóa',
        cancelButtonText: 'Hủy',
        confirmButtonColor: '#ef4444',
        inputValidator: (value) => {
            if (!value) {
                return 'Vui lòng nhập lý do khóa';
            }
        }
    });
    
    if (reason) {
        try {
            const response = await fetch(`/api/admin/licenses/ban/${licenseId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ reason: reason })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast('Đã khóa license thành công', 'success');
                await loadLicenses();
            } else {
                Swal.fire('Lỗi!', data.message || 'Không thể khóa license', 'error');
            }
        } catch (error) {
            console.error('Ban license error:', error);
            Swal.fire('Lỗi!', 'Lỗi kết nối đến server', 'error');
        }
    }
}

async function showLicenseActivations(licenseId) {
    try {
        const response = await fetch(`/api/admin/licenses/activations/${licenseId}`);
        const result = await response.json();
        
        if (result.success) {
            const activations = result.data;
            
            if (activations.length === 0) {
                Swal.fire({
                    icon: 'info',
                    title: 'Chưa có activation',
                    text: 'License này chưa được kích hoạt trên thiết bị nào.'
                });
                return;
            }
            
            let activationsHtml = '<div class="max-h-60 overflow-y-auto">';
            activations.forEach(act => {
                activationsHtml += `
                    <div class="mb-3 p-3 bg-gray-50 rounded-lg">
                        <div class="flex justify-between items-start">
                            <div>
                                <p class="font-mono text-sm font-medium">${act.hwid}</p>
                                <p class="text-xs text-gray-600 mt-1">
                                    IP: ${act.ip_address || 'N/A'} | 
                                    Device: ${act.device_name || 'N/A'}
                                </p>
                                <p class="text-xs text-gray-500">
                                    Activated: ${new Date(act.activated_at).toLocaleString('vi-VN')}
                                </p>
                            </div>
                            <span class="px-2 py-1 text-xs rounded-full ${act.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}">
                                ${act.is_active ? 'Active' : 'Inactive'}
                            </span>
                        </div>
                    </div>
                `;
            });
            activationsHtml += '</div>';
            
            Swal.fire({
                title: 'Danh sách Activations',
                html: activationsHtml,
                showConfirmButton: false,
                showCloseButton: true,
                width: '600px'
            });
        }
    } catch (error) {
        console.error('Activations error:', error);
        showToast('Lỗi khi lấy danh sách activations', 'error');
    }
}

async function deleteLicense(licenseId) {
    const { value: confirm } = await Swal.fire({
        title: 'Xóa License?',
        text: 'Hành động này không thể hoàn tác. License và tất cả activations sẽ bị xóa vĩnh viễn.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Xóa',
        cancelButtonText: 'Hủy',
        confirmButtonColor: '#ef4444',
        reverseButtons: true
    });
    
    if (confirm) {
        try {
            const response = await fetch(`/api/admin/licenses/delete/${licenseId}`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast('Đã xóa license thành công', 'success');
                await loadLicenses();
                await loadStats();
            } else {
                Swal.fire('Lỗi!', data.message || 'Không thể xóa license', 'error');
            }
        } catch (error) {
            console.error('Delete license error:', error);
            Swal.fire('Lỗi!', 'Lỗi kết nối đến server', 'error');
        }
    }
}

// Bulk actions
function showBulkActions() {
    if (selectedLicenses.size === 0) {
        showToast('Vui lòng chọn ít nhất một license', 'warning');
        return;
    }
    
    Swal.fire({
        title: 'Hành động hàng loạt',
        html: `
            <div class="text-left space-y-3">
                <button onclick="bulkAction('activate')" class="w-full text-left p-3 bg-green-50 hover:bg-green-100 rounded-lg transition">
                    <i class="fas fa-play text-green-600 mr-2"></i>
                    <span class="font-medium">Kích hoạt</span>
                    <p class="text-sm text-gray-600 mt-1">Kích hoạt ${selectedLicenses.size} license đã chọn</p>
                </button>
                
                <button onclick="bulkAction('deactivate')" class="w-full text-left p-3 bg-yellow-50 hover:bg-yellow-100 rounded-lg transition">
                    <i class="fas fa-pause text-yellow-600 mr-2"></i>
                    <span class="font-medium">Vô hiệu hóa</span>
                    <p class="text-sm text-gray-600 mt-1">Vô hiệu hóa ${selectedLicenses.size} license đã chọn</p>
                </button>
                
                <button onclick="bulkAction('ban')" class="w-full text-left p-3 bg-red-50 hover:bg-red-100 rounded-lg transition">
                    <i class="fas fa-ban text-red-600 mr-2"></i>
                    <span class="font-medium">Khóa</span>
                    <p class="text-sm text-gray-600 mt-1">Khóa ${selectedLicenses.size} license đã chọn</p>
                </button>
                
                <button onclick="bulkAction('delete')" class="w-full text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition border border-red-200">
                    <i class="fas fa-trash text-red-600 mr-2"></i>
                    <span class="font-medium text-red-600">Xóa vĩnh viễn</span>
                    <p class="text-sm text-gray-600 mt-1">Xóa ${selectedLicenses.size} license đã chọn</p>
                </button>
            </div>
        `,
        showConfirmButton: false,
        showCloseButton: true,
        width: '500px'
    });
}

async function bulkAction(action) {
    const actionNames = {
        'activate': 'kích hoạt',
        'deactivate': 'vô hiệu hóa',
        'ban': 'khóa',
        'delete': 'xóa'
    };
    
    const { value: confirm } = await Swal.fire({
        title: `Xác nhận ${actionNames[action]}`,
        text: `Bạn có chắc chắn muốn ${actionNames[action]} ${selectedLicenses.size} license đã chọn?`,
        icon: action === 'delete' ? 'warning' : 'question',
        showCancelButton: true,
        confirmButtonText: action === 'delete' ? 'Xóa vĩnh viễn' : `Đồng ý ${actionNames[action]}`,
        cancelButtonText: 'Hủy',
        confirmButtonColor: action === 'delete' ? '#ef4444' : '#3b82f6',
        reverseButtons: true
    });
    
    if (confirm) {
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
                await loadStats();
            } else {
                Swal.fire('Lỗi!', data.message || `Không thể ${actionNames[action]} license`, 'error');
            }
        } catch (error) {
            console.error('Bulk action error:', error);
            Swal.fire('Lỗi!', 'Lỗi kết nối đến server', 'error');
        }
    }
}

// API Key management
async function showCreateApiKeyModal() {
    const { value: name } = await Swal.fire({
        title: 'Tạo API Key mới',
        input: 'text',
        inputLabel: 'Tên API Key',
        inputPlaceholder: 'Nhập tên cho API Key này...',
        showCancelButton: true,
        confirmButtonText: 'Tạo',
        cancelButtonText: 'Hủy',
        confirmButtonColor: '#10b981',
        inputValidator: (value) => {
            if (!value) {
                return 'Vui lòng nhập tên API Key';
            }
        }
    });
    
    if (name) {
        try {
            const response = await fetch('/api/admin/apikeys/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name: name })
            });
            
            const data = await response.json();
            
            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Thành công!',
                    html: `
                        <p>Đã tạo API Key thành công!</p>
                        <div class="mt-4 p-3 bg-gray-100 rounded">
                            <p class="font-mono text-sm break-all">${data.api_key}</p>
                            <p class="text-xs text-gray-600 mt-2">⚠️ Lưu lại ngay vì sẽ không hiển thị lại lần sau!</p>
                        </div>
                        <button onclick="copyToClipboard('${data.api_key}')" class="mt-3 px-4 py-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition">
                            <i class="fas fa-copy mr-2"></i> Sao chép API Key
                        </button>
                    `,
                    width: '600px'
                });
                
                // Load API keys list
                await loadApiKeys();
                await loadStats();
            } else {
                Swal.fire('Lỗi!', data.message || 'Không thể tạo API Key', 'error');
            }
        } catch (error) {
            console.error('Create API key error:', error);
            Swal.fire('Lỗi!', 'Lỗi kết nối đến server', 'error');
        }
    }
}

async function loadApiKeys() {
    try {
        const container = document.getElementById('apiKeysList');
        container.innerHTML = `
            <div class="col-span-3 py-8 text-center text-gray-500">
                <div class="flex justify-center">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
                </div>
                <p class="mt-2">Đang tải API Keys...</p>
            </div>
        `;
        
        const response = await fetch('/api/admin/apikeys');
        const result = await response.json();
        
        if (result.success) {
            const apikeys = result.data;
            container.innerHTML = '';
            
            if (apikeys.length === 0) {
                container.innerHTML = `
                    <div class="col-span-3 py-8 text-center text-gray-500">
                        <i class="fas fa-key text-4xl mb-2 text-gray-300"></i>
                        <p>Chưa có API Key nào</p>
                        <button onclick="showCreateApiKeyModal()" class="mt-4 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition">
                            <i class="fas fa-plus mr-2"></i> Tạo API Key đầu tiên
                        </button>
                    </div>
                `;
                return;
            }
            
            apikeys.forEach(key => {
                const isActive = key.status === 'active';
                const lastUsed = key.last_used ? new Date(key.last_used).toLocaleString('vi-VN') : 'Chưa sử dụng';
                
                const card = `
                    <div class="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                        <div class="p-4">
                            <div class="flex justify-between items-start mb-3">
                                <div>
                                    <h4 class="font-bold text-gray-800">${key.name}</h4>
                                    <div class="flex items-center mt-1">
                                        <div class="w-2 h-2 rounded-full ${isActive ? 'bg-green-500' : 'bg-red-500'} mr-2"></div>
                                        <span class="text-xs ${isActive ? 'text-green-600' : 'text-red-600'}">${isActive ? 'Active' : 'Inactive'}</span>
                                    </div>
                                </div>
                                <div class="flex space-x-1">
                                    <button onclick="updateApiKey(${key.id})" class="p-1 text-blue-500 hover:text-blue-700" title="Sửa">
                                        <i class="fas fa-edit"></i>
                                    </button>
                                    <button onclick="deleteApiKey(${key.id})" class="p-1 text-red-500 hover:text-red-700" title="Xóa">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </div>
                            </div>
                            
                            <div class="mt-4">
                                <div class="flex items-center space-x-2">
                                    <code class="flex-1 px-3 py-2 bg-gray-100 border border-gray-300 rounded text-gray-800 font-mono text-xs break-all">${key.key}</code>
                                    <button onclick="copyToClipboard('${key.key}')" class="px-2 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition" title="Sao chép">
                                        <i class="fas fa-copy"></i>
                                    </button>
                                </div>
                                
                                <div class="mt-4 text-xs text-gray-500 space-y-1">
                                    <div class="flex justify-between">
                                        <span><i class="far fa-calendar mr-1"></i> Ngày tạo:</span>
                                        <span>${new Date(key.created_at).toLocaleDateString('vi-VN')}</span>
                                    </div>
                                    <div class="flex justify-between">
                                        <span><i class="far fa-clock mr-1"></i> Lần cuối:</span>
                                        <span>${lastUsed}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                container.innerHTML += card;
            });
        }
    } catch (error) {
        console.error('Error loading API keys:', error);
        const container = document.getElementById('apiKeysList');
        container.innerHTML = `
            <div class="col-span-3 py-8 text-center text-red-500">
                <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                <p>Lỗi khi tải API Keys</p>
            </div>
        `;
    }
}

async function updateApiKey(keyId) {
    try {
        const response = await fetch('/api/admin/apikeys');
        const result = await response.json();
        
        if (result.success) {
            const apikey = result.data.find(k => k.id === keyId);
            if (!apikey) {
                showToast('Không tìm thấy API Key', 'error');
                return;
            }
            
            const { value: formValues } = await Swal.fire({
                title: 'Chỉnh sửa API Key',
                html: `
                    <div class="text-left">
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-1">Tên API Key</label>
                            <input type="text" id="name" class="swal2-input" value="${apikey.name}" required>
                        </div>
                        <div class="mb-4">
                            <label class="block text-sm font-medium text-gray-700 mb-1">Trạng thái</label>
                            <select id="status" class="swal2-input">
                                <option value="active" ${apikey.status === 'active' ? 'selected' : ''}>Active</option>
                                <option value="inactive" ${apikey.status === 'inactive' ? 'selected' : ''}>Inactive</option>
                            </select>
                        </div>
                    </div>
                `,
                showCancelButton: true,
                confirmButtonText: 'Cập nhật',
                cancelButtonText: 'Hủy',
                confirmButtonColor: '#3b82f6',
                preConfirm: () => {
                    const name = document.getElementById('name').value.trim();
                    if (!name) {
                        Swal.showValidationMessage('Vui lòng nhập tên API Key');
                        return false;
                    }
                    return {
                        name: name,
                        status: document.getElementById('status').value
                    };
                }
            });
            
            if (formValues) {
                const updateRes = await fetch(`/api/admin/apikeys/update/${keyId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formValues)
                });
                
                const data = await updateRes.json();
                
                if (data.success) {
                    showToast('Đã cập nhật API Key thành công', 'success');
                    await loadApiKeys();
                } else {
                    Swal.fire('Lỗi!', data.message || 'Không thể cập nhật API Key', 'error');
                }
            }
        }
    } catch (error) {
        console.error('Update API key error:', error);
        showToast('Lỗi khi cập nhật API Key', 'error');
    }
}

async function deleteApiKey(keyId) {
    const { value: confirm } = await Swal.fire({
        title: 'Xóa API Key?',
        text: 'API Key sẽ bị xóa vĩnh viễn. Các ứng dụng đang sử dụng API Key này sẽ không thể verify license nữa.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Xóa',
        cancelButtonText: 'Hủy',
        confirmButtonColor: '#ef4444',
        reverseButtons: true
    });
    
    if (confirm) {
        try {
            const response = await fetch(`/api/admin/apikeys/delete/${keyId}`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast('Đã xóa API Key thành công', 'success');
                await loadApiKeys();
                await loadStats();
            } else {
                Swal.fire('Lỗi!', data.message || 'Không thể xóa API Key', 'error');
            }
        } catch (error) {
            console.error('Delete API key error:', error);
            Swal.fire('Lỗi!', 'Lỗi kết nối đến server', 'error');
        }
    }
}

// Activity logs
async function loadActivity() {
    try {
        const container = document.getElementById('activityList');
        container.innerHTML = `
            <div class="text-center text-gray-500 py-8">
                <div class="flex justify-center">
                    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
                </div>
                <p class="mt-2">Đang tải hoạt động...</p>
            </div>
        `;
        
        const response = await fetch('/api/admin/activity');
        const result = await response.json();
        
        if (result.success) {
            const activities = result.data;
            container.innerHTML = '';
            
            if (activities.length === 0) {
                container.innerHTML = `
                    <div class="text-center text-gray-500 py-8">
                        <i class="fas fa-history text-4xl mb-2 text-gray-300"></i>
                        <p>Chưa có hoạt động nào</p>
                    </div>
                `;
                return;
            }
            
            activities.forEach(activity => {
                let icon = 'fa-info-circle';
                let color = 'text-blue-500';
                
                switch(activity.action) {
                    case 'LOGIN': icon = 'fa-sign-in-alt'; color = 'text-green-500'; break;
                    case 'LOGOUT': icon = 'fa-sign-out-alt'; color = 'text-gray-500'; break;
                    case 'CREATE_LICENSE': icon = 'fa-plus-circle'; color = 'text-green-500'; break;
                    case 'DELETE_LICENSE': icon = 'fa-trash-alt'; color = 'text-red-500'; break;
                    case 'BAN_LICENSE': icon = 'fa-ban'; color = 'text-red-500'; break;
                    case 'RESET_LICENSE': icon = 'fa-redo'; color = 'text-yellow-500'; break;
                    case 'EXTEND_LICENSE': icon = 'fa-calendar-plus'; color = 'text-blue-500'; break;
                    case 'CHANGE_PASSWORD': icon = 'fa-key'; color = 'text-purple-500'; break;
                }
                
                const details = activity.details ? 
                    `<p class="text-xs text-gray-600 mt-1">${JSON.stringify(activity.details)}</p>` : '';
                
                const item = `
                    <div class="bg-white p-4 rounded-lg shadow-sm border-l-4 ${color}">
                        <div class="flex justify-between items-start">
                            <div class="flex items-start space-x-3">
                                <i class="fas ${icon} ${color} text-lg mt-1"></i>
                                <div>
                                    <p class="font-medium">${activity.action.replace(/_/g, ' ')}</p>
                                    <p class="text-sm text-gray-500">
                                        bởi ${activity.username} • ${new Date(activity.created_at).toLocaleString('vi-VN')}
                                    </p>
                                    ${details}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
                container.innerHTML += item;
            });
        }
    } catch (error) {
        console.error('Error loading activity:', error);
        const container = document.getElementById('activityList');
        container.innerHTML = `
            <div class="text-center text-red-500 py-8">
                <i class="fas fa-exclamation-triangle text-2xl mb-2"></i>
                <p>Lỗi khi tải hoạt động</p>
            </div>
        `;
    }
}

// Change password
function showChangePasswordModal() {
    Swal.fire({
        title: 'Đổi mật khẩu',
        html: `
            <div class="text-left">
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Mật khẩu hiện tại</label>
                    <input type="password" id="current_password" class="swal2-input" required>
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Mật khẩu mới</label>
                    <input type="password" id="new_password" class="swal2-input" required>
                    <p class="text-xs text-gray-500 mt-1">Ít nhất 6 ký tự</p>
                </div>
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700 mb-1">Xác nhận mật khẩu mới</label>
                    <input type="password" id="confirm_password" class="swal2-input" required>
                </div>
            </div>
        `,
        showCancelButton: true,
        confirmButtonText: 'Đổi mật khẩu',
        cancelButtonText: 'Hủy',
        confirmButtonColor: '#3b82f6',
        preConfirm: () => {
            const current = document.getElementById('current_password').value;
            const newPass = document.getElementById('new_password').value;
            const confirm = document.getElementById('confirm_password').value;
            
            if (!current || !newPass || !confirm) {
                Swal.showValidationMessage('Vui lòng nhập đầy đủ thông tin');
                return false;
            }
            
            if (newPass.length < 6) {
                Swal.showValidationMessage('Mật khẩu mới phải có ít nhất 6 ký tự');
                return false;
            }
            
            if (newPass !== confirm) {
                Swal.showValidationMessage('Mật khẩu mới không khớp');
                return false;
            }
            
            return {
                current_password: current,
                new_password: newPass,
                confirm_password: confirm
            };
        }
    }).then(async (result) => {
        if (result.isConfirmed) {
            try {
                const response = await fetch('/api/admin/change-password', {
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
                        title: 'Thành công!',
                        text: data.message,
                        timer: 2000,
                        showConfirmButton: false
                    });
                } else {
                    Swal.fire('Lỗi!', data.message || 'Không thể đổi mật khẩu', 'error');
                }
            } catch (error) {
                console.error('Change password error:', error);
                Swal.fire('Lỗi!', 'Lỗi kết nối đến server', 'error');
            }
        }
    });
}

// Utility functions
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Đã sao chép vào clipboard!', 'success');
    }).catch(err => {
        console.error('Copy failed:', err);
        showToast('Không thể sao chép', 'error');
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    // Set current username
    const username = 'Admin';
    document.getElementById('usernameDisplay').textContent = username;
    document.getElementById('currentUser').textContent = username;
    
    // Auto refresh
    setInterval(loadStats, 30000);
});
