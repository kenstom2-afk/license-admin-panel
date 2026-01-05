/**
 * Admin Panel - Server Key & API Manager
 * Frontend JavaScript
 */

class AdminPanel {
    constructor() {
        this.baseUrl = window.location.origin;
        this.token = localStorage.getItem('admin_token');
        this.currentKeyId = null;
        this.keys = [];
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.checkAuth();
    }
    
    bindEvents() {
        // Login
        document.getElementById('loginBtn')?.addEventListener('click', () => this.login());
        document.getElementById('password')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.login();
        });
        
        // Logout
        document.getElementById('logoutBtn')?.addEventListener('click', () => this.logout());
        
        // Refresh
        document.getElementById('refreshBtn')?.addEventListener('click', () => this.loadData());
        
        // Create Key
        document.getElementById('createKeyBtn')?.addEventListener('click', () => this.showCreateModal());
        document.getElementById('createFirstKey')?.addEventListener('click', () => this.showCreateModal());
        document.getElementById('confirmCreate')?.addEventListener('click', () => this.createKey());
        document.getElementById('cancelCreate')?.addEventListener('click', () => this.hideModal('createModal'));
        
        // Search & Filter
        document.getElementById('searchInput')?.addEventListener('input', (e) => {
            this.filterKeys(e.target.value);
        });
        
        document.getElementById('statusFilter')?.addEventListener('change', (e) => {
            this.filterByStatus(e.target.value);
        });
        
        // Close modals
        document.querySelectorAll('.close-modal').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.modal').forEach(modal => {
                    modal.style.display = 'none';
                });
            });
        });
        
        // Click outside modal to close
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.style.display = 'none';
                }
            });
        });
    }
    
    checkAuth() {
        if (this.token) {
            this.verifyToken();
        } else {
            this.showLogin();
        }
    }
    
    showLogin() {
        document.getElementById('loginScreen').style.display = 'block';
        document.getElementById('dashboard').style.display = 'none';
    }
    
    showDashboard() {
        document.getElementById('loginScreen').style.display = 'none';
        document.getElementById('dashboard').style.display = 'block';
        this.loadData();
    }
    
    async login() {
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        const errorEl = document.getElementById('loginError');
        
        if (!username || !password) {
            this.showError('Vui lòng nhập username và password', errorEl);
            return;
        }
        
        try {
            const response = await fetch(`${this.baseUrl}/api/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.token = data.token;
                localStorage.setItem('admin_token', this.token);
                
                document.getElementById('usernameDisplay').textContent = data.user.username;
                this.showDashboard();
                this.showToast('Đăng nhập thành công');
            } else {
                this.showError(data.error || 'Đăng nhập thất bại', errorEl);
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showError('Lỗi kết nối đến server', errorEl);
        }
    }
    
    async verifyToken() {
        try {
            const response = await fetch(`${this.baseUrl}/api/verify`, {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                document.getElementById('usernameDisplay').textContent = data.user.username;
                this.showDashboard();
            } else {
                this.showLogin();
            }
        } catch (error) {
            console.error('Verify token error:', error);
            this.showLogin();
        }
    }
    
    logout() {
        fetch(`${this.baseUrl}/api/logout`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.token}`
            }
        });
        
        localStorage.removeItem('admin_token');
        this.token = null;
        this.showLogin();
        this.showToast('Đã đăng xuất');
    }
    
    async loadData() {
        await Promise.all([
            this.loadKeys(),
            this.loadStats(),
            this.loadActivity()
        ]);
    }
    
    async loadKeys() {
        const tableBody = document.getElementById('keysTableBody');
        const loading = document.getElementById('loading');
        const noData = document.getElementById('noData');
        
        if (loading) loading.style.display = 'block';
        if (noData) noData.style.display = 'none';
        if (tableBody) tableBody.innerHTML = '';
        
        try {
            const response = await fetch(`${this.baseUrl}/api/keys`, {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.keys = data.data;
                this.renderKeys(this.keys);
                
                if (this.keys.length === 0 && noData) {
                    noData.style.display = 'block';
                }
            } else {
                this.showToast('Lỗi khi tải dữ liệu keys');
            }
        } catch (error) {
            console.error('Error loading keys:', error);
            this.showToast('Lỗi kết nối khi tải keys');
        } finally {
            if (loading) loading.style.display = 'none';
        }
    }
    
    renderKeys(keys) {
        const tableBody = document.getElementById('keysTableBody');
        if (!tableBody) return;
        
        tableBody.innerHTML = '';
        
        keys.forEach(key => {
            const row = document.createElement('tr');
            const createdDate = key.created_at 
                ? new Date(key.created_at).toLocaleDateString('vi-VN')
                : 'N/A';
            
            row.innerHTML = `
                <td>${key.id}</td>
                <td><strong>${key.key_name}</strong></td>
                <td class="key-cell">${this.truncateKey(key.server_key)}</td>
                <td class="key-cell">${this.truncateKey(key.api_key)}</td>
                <td>
                    <span class="status-badge ${key.status}">
                        ${key.status === 'active' ? 'Active' : 'Locked'}
                    </span>
                </td>
                <td>${createdDate}</td>
                <td class="action-cell">
                    <button class="btn-icon" onclick="admin.viewKey(${key.id})" title="Xem chi tiết">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn-icon" onclick="admin.resetKey(${key.id})" title="Reset API Key">
                        <i class="fas fa-redo"></i>
                    </button>
                    <button class="btn-icon" onclick="admin.toggleLock(${key.id})" title="${key.status === 'active' ? 'Lock' : 'Unlock'}">
                        <i class="fas ${key.status === 'active' ? 'fa-lock' : 'fa-unlock'}"></i>
                    </button>
                    <button class="btn-icon" onclick="admin.deleteKey(${key.id})" title="Xóa">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            `;
            
            tableBody.appendChild(row);
        });
    }
    
    async loadStats() {
        try {
            const response = await fetch(`${this.baseUrl}/api/stats`, {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                document.getElementById('totalKeys').textContent = data.data.total_keys || 0;
                document.getElementById('activeKeys').textContent = data.data.active_keys || 0;
                document.getElementById('lockedKeys').textContent = data.data.locked_keys || 0;
                document.getElementById('recentActivity').textContent = data.data.recent_activity || 0;
            }
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }
    
    async loadActivity() {
        const activityList = document.getElementById('activityList');
        if (!activityList) return;
        
        try {
            const response = await fetch(`${this.baseUrl}/api/activity`, {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.renderActivity(data.data);
            }
        } catch (error) {
            console.error('Error loading activity:', error);
            activityList.innerHTML = '<div class="activity-item">Lỗi tải hoạt động</div>';
        }
    }
    
    renderActivity(activities) {
        const activityList = document.getElementById('activityList');
        if (!activityList) return;
        
        if (!activities || activities.length === 0) {
            activityList.innerHTML = '<div class="activity-item">Không có hoạt động nào</div>';
            return;
        }
        
        activityList.innerHTML = '';
        
        activities.slice(0, 5).forEach(activity => {
            const time = activity.timestamp 
                ? new Date(activity.timestamp).toLocaleTimeString('vi-VN')
                : '';
            const date = activity.timestamp 
                ? new Date(activity.timestamp).toLocaleDateString('vi-VN')
                : '';
            
            const item = document.createElement('div');
            item.className = 'activity-item';
            item.innerHTML = `
                <div>
                    <div class="activity-action">
                        <i class="fas fa-${this.getActionIcon(activity.action)}"></i>
                        ${this.getActionText(activity.action)}
                    </div>
                    <div class="activity-details">${activity.details || ''}</div>
                </div>
                <div class="activity-time">${date} ${time}</div>
            `;
            
            activityList.appendChild(item);
        });
    }
    
    getActionIcon(action) {
        if (!action) return 'info-circle';
        switch(action.toLowerCase()) {
            case 'create': return 'plus-circle';
            case 'reset': return 'redo';
            case 'lock': return 'lock';
            case 'unlock': return 'unlock';
            case 'delete': return 'trash';
            case 'login': return 'sign-in-alt';
            case 'logout': return 'sign-out-alt';
            default: return 'info-circle';
        }
    }
    
    getActionText(action) {
        if (!action) return 'Hoạt động';
        switch(action.toLowerCase()) {
            case 'create': return 'Tạo key mới';
            case 'reset': return 'Reset API key';
            case 'lock': return 'Khóa key';
            case 'unlock': return 'Mở khóa key';
            case 'delete': return 'Xóa key';
            case 'login': return 'Đăng nhập';
            case 'logout': return 'Đăng xuất';
            default: return action;
        }
    }
    
    showCreateModal() {
        document.getElementById('newKeyName').value = '';
        document.getElementById('newKeyNotes').value = '';
        this.showModal('createModal');
    }
    
    showModal(modalId) {
        document.getElementById(modalId).style.display = 'flex';
    }
    
    hideModal(modalId) {
        document.getElementById(modalId).style.display = 'none';
    }
    
    async createKey() {
        const keyName = document.getElementById('newKeyName')?.value;
        const notes = document.getElementById('newKeyNotes')?.value;
        
        if (!keyName) {
            this.showToast('Vui lòng nhập tên key');
            return;
        }
        
        try {
            const response = await fetch(`${this.baseUrl}/api/keys`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    key_name: keyName, 
                    notes: notes || '' 
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.hideModal('createModal');
                this.loadData();
                this.showToast('Key đã được tạo thành công');
            } else {
                this.showToast(data.error || 'Lỗi khi tạo key');
            }
        } catch (error) {
            console.error('Create key error:', error);
            this.showToast('Lỗi kết nối đến server');
        }
    }
    
    viewKey(keyId) {
        const key = this.keys.find(k => k.id === keyId);
        if (!key) {
            this.showToast('Key không tìm thấy');
            return;
        }
        
        this.currentKeyId = keyId;
        
        // Fill modal with key details
        document.getElementById('detailKeyName').textContent = key.key_name;
        document.getElementById('detailServerKey').textContent = key.server_key;
        document.getElementById('detailApiKey').textContent = key.api_key;
        
        const statusBadge = document.getElementById('detailStatus');
        if (statusBadge) {
            statusBadge.textContent = key.status === 'active' ? 'Active' : 'Locked';
            statusBadge.className = `status-badge ${key.status}`;
        }
        
        document.getElementById('detailCreatedAt').textContent = key.created_at 
            ? new Date(key.created_at).toLocaleString('vi-VN')
            : 'N/A';
            
        document.getElementById('detailNotes').textContent = key.notes || 'Không có ghi chú';
        
        // Update lock button
        const lockBtn = document.getElementById('toggleLockBtn');
        if (lockBtn) {
            lockBtn.innerHTML = `<i class="fas fa-${key.status === 'active' ? 'lock' : 'unlock'}"></i> ${key.status === 'active' ? 'Khóa Key' : 'Mở khóa Key'}`;
        }
        
        // Bind copy buttons
        document.querySelectorAll('.btn-copy').forEach(btn => {
            btn.onclick = (e) => {
                const targetId = e.currentTarget.dataset.target;
                const text = document.getElementById(targetId)?.textContent;
                if (text) {
                    this.copyToClipboard(text);
                }
            };
        });
        
        // Show modal
        this.showModal('keyModal');
    }
    
    async resetKey(keyId) {
        if (!confirm('Bạn có chắc chắn muốn reset API key này? API key cũ sẽ không thể sử dụng được nữa.')) {
            return;
        }
        
        try {
            const response = await fetch(`${this.baseUrl}/api/keys/${keyId}/reset`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.loadData();
                this.hideModal('keyModal');
                this.showToast('Key đã được reset thành công');
            } else {
                this.showToast(data.error || 'Lỗi khi reset key');
            }
        } catch (error) {
            console.error('Reset key error:', error);
            this.showToast('Lỗi kết nối đến server');
        }
    }
    
    async toggleLock(keyId) {
        const key = this.keys.find(k => k.id === keyId);
        if (!key) {
            this.showToast('Key không tìm thấy');
            return;
        }
        
        const action = key.status === 'active' ? 'khóa' : 'mở khóa';
        
        if (!confirm(`Bạn có chắc chắn muốn ${action} key này?`)) {
            return;
        }
        
        try {
            const response = await fetch(`${this.baseUrl}/api/keys/${keyId}/lock`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.loadData();
                this.hideModal('keyModal');
                this.showToast(`Key đã được ${action} thành công`);
            } else {
                this.showToast(data.error || `Lỗi khi ${action} key`);
            }
        } catch (error) {
            console.error('Toggle lock error:', error);
            this.showToast('Lỗi kết nối đến server');
        }
    }
    
    async deleteKey(keyId) {
        if (!confirm('Bạn có chắc chắn muốn xóa key này? Hành động này không thể hoàn tác.')) {
            return;
        }
        
        try {
            const response = await fetch(`${this.baseUrl}/api/keys/${keyId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.loadData();
                this.hideModal('keyModal');
                this.showToast('Key đã được xóa thành công');
            } else {
                this.showToast(data.error || 'Lỗi khi xóa key');
            }
        } catch (error) {
            console.error('Delete key error:', error);
            this.showToast('Lỗi kết nối đến server');
        }
    }
    
    filterKeys(searchTerm) {
        if (!searchTerm) {
            this.renderKeys(this.keys);
            return;
        }
        
        const filtered = this.keys.filter(key => 
            key.key_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            key.server_key.toLowerCase().includes(searchTerm.toLowerCase()) ||
            key.api_key.toLowerCase().includes(searchTerm.toLowerCase())
        );
        
        this.renderKeys(filtered);
    }
    
    filterByStatus(status) {
        if (!status) {
            this.renderKeys(this.keys);
            return;
        }
        
        const filtered = this.keys.filter(key => key.status === status);
        this.renderKeys(filtered);
    }
    
    truncateKey(key, length = 20) {
        if (!key) return '';
        if (key.length <= length) return key;
        return key.substring(0, length) + '...';
    }
    
    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.showToast('Đã sao chép vào clipboard');
        }).catch(err => {
            console.error('Copy failed:', err);
            this.showToast('Lỗi khi sao chép');
        });
    }
    
    showToast(message) {
        const toast = document.getElementById('toast');
        const messageEl = document.getElementById('toastMessage');
        
        if (!toast || !messageEl) return;
        
        messageEl.textContent = message;
        toast.style.display = 'flex';
        
        setTimeout(() => {
            toast.style.display = 'none';
        }, 3000);
    }
    
    showError(message, element) {
        if (!element) return;
        
        element.textContent = message;
        element.style.display = 'block';
        
        setTimeout(() => {
            element.style.display = 'none';
        }, 5000);
    }
}

// Initialize admin panel when page loads
let admin;

document.addEventListener('DOMContentLoaded', () => {
    try {
        admin = new AdminPanel();
        console.log('✅ Admin Panel initialized successfully');
    } catch (error) {
        console.error('❌ Failed to initialize Admin Panel:', error);
    }
});

// Make admin accessible globally for onclick events
window.admin = admin;
