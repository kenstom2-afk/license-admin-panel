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
        document.getElementById('loginBtn').addEventListener('click', () => this.login());
        document.getElementById('password').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.login();
        });
        
        // Logout
        document.getElementById('logoutBtn').addEventListener('click', () => this.logout());
        
        // Refresh
        document.getElementById('refreshBtn').addEventListener('click', () => this.loadKeys());
        
        // Create Key
        document.getElementById('createKeyBtn').addEventListener('click', () => this.showCreateModal());
        document.getElementById('confirmCreate').addEventListener('click', () => this.createKey());
        document.getElementById('cancelCreate').addEventListener('click', () => this.hideCreateModal());
        
        // Search & Filter
        document.getElementById('searchInput').addEventListener('input', (e) => {
            this.filterKeys(e.target.value);
        });
        
        document.getElementById('statusFilter').addEventListener('change', (e) => {
            this.filterByStatus(e.target.value);
        });
        
        // Close modals
        document.querySelectorAll('.close-modal').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.modal').forEach(modal => {
                    modal.classList.remove('show');
                });
            });
        });
        
        // Click outside modal to close
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.remove('show');
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
        document.getElementById('loginScreen').style.display = 'flex';
        document.getElementById('dashboard').classList.add('hidden');
    }
    
    showDashboard() {
        document.getElementById('loginScreen').style.display = 'none';
        document.getElementById('dashboard').classList.remove('hidden');
        this.loadKeys();
        this.loadStats();
        this.loadActivity();
    }
    
    async login() {
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        const errorEl = document.getElementById('loginError');
        
        if (!username || !password) {
            this.showError('Vui lòng nhập username và password');
            return;
        }
        
        try {
            const response = await fetch(`${this.baseUrl}/login`, {
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
                this.showError(data.error || 'Đăng nhập thất bại');
            }
        } catch (error) {
            this.showError('Lỗi kết nối đến server');
            console.error('Login error:', error);
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
                document.getElementById('usernameDisplay').textContent = data.data.user.username;
                this.showDashboard();
            } else {
                this.showLogin();
            }
        } catch (error) {
            this.showLogin();
        }
    }
    
    logout() {
        localStorage.removeItem('admin_token');
        this.token = null;
        this.showLogin();
        this.showToast('Đã đăng xuất');
    }
    
    async loadKeys() {
        const tableBody = document.getElementById('keysTableBody');
        const loading = document.getElementById('loading');
        const table = document.getElementById('keysTable');
        const noData = document.getElementById('noData');
        
        loading.classList.remove('hidden');
        table.classList.remove('show');
        noData.classList.add('hidden');
        
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
                this.updateStats(data.stats);
                
                if (this.keys.length > 0) {
                    table.classList.add('show');
                    noData.classList.add('hidden');
                } else {
                    noData.classList.remove('hidden');
                }
            }
        } catch (error) {
            console.error('Error loading keys:', error);
            this.showError('Lỗi khi tải dữ liệu');
        } finally {
            loading.classList.add('hidden');
        }
    }
    
    renderKeys(keys) {
        const tableBody = document.getElementById('keysTableBody');
        tableBody.innerHTML = '';
        
        keys.forEach(key => {
            const row = document.createElement('tr');
            const createdDate = new Date(key.created_at).toLocaleDateString('vi-VN');
            
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
                    <button class="btn-icon view" onclick="admin.viewKey(${key.id})" title="Xem chi tiết">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn-icon reset" onclick="admin.resetKey(${key.id})" title="Reset API Key">
                        <i class="fas fa-redo"></i>
                    </button>
                    <button class="btn-icon lock" onclick="admin.toggleLock(${key.id})" title="${key.status === 'active' ? 'Lock' : 'Unlock'}">
                        <i class="fas ${key.status === 'active' ? 'fa-lock' : 'fa-unlock'}"></i>
                    </button>
                    <button class="btn-icon delete" onclick="admin.deleteKey(${key.id})" title="Xóa">
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
                document.getElementById('totalActivity').textContent = data.data.recent_activity || 0;
            }
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }
    
    async loadActivity() {
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
        }
    }
    
    renderActivity(activities) {
        const activityList = document.getElementById('activityList');
        activityList.innerHTML = '';
        
        activities.slice(0, 5).forEach(activity => {
            const time = new Date(activity.performed_at).toLocaleTimeString('vi-VN');
            const date = new Date(activity.performed_at).toLocaleDateString('vi-VN');
            
            const item = document.createElement('div');
            item.className = 'activity-item';
            item.innerHTML = `
                <div>
                    <div class="activity-action ${activity.action.toLowerCase()}">
                        <i class="fas fa-${this.getActionIcon(activity.action)}"></i>
                        ${this.getActionText(activity.action)}
                    </div>
                    <div class="activity-details">${activity.details}</div>
                </div>
                <div class="activity-time">${date} ${time}</div>
            `;
            
            activityList.appendChild(item);
        });
    }
    
    getActionIcon(action) {
        switch(action) {
            case 'CREATE': return 'plus-circle';
            case 'RESET': return 'redo';
            case 'LOCK': return 'lock';
            case 'UNLOCK': return 'unlock';
            case 'DELETE': return 'trash';
            default: return 'info-circle';
        }
    }
    
    getActionText(action) {
        switch(action) {
            case 'CREATE': return 'Tạo key mới';
            case 'RESET': return 'Reset API key';
            case 'LOCK': return 'Khóa key';
            case 'UNLOCK': return 'Mở khóa key';
            case 'DELETE': return 'Xóa key';
            default: return action;
        }
    }
    
    updateStats(stats) {
        document.getElementById('totalKeys').textContent = stats.total || 0;
        document.getElementById('activeKeys').textContent = stats.active || 0;
        document.getElementById('lockedKeys').textContent = stats.locked || 0;
    }
    
    showCreateModal() {
        document.getElementById('newKeyName').value = '';
        document.getElementById('newKeyNotes').value = '';
        document.getElementById('createModal').classList.add('show');
    }
    
    hideCreateModal() {
        document.getElementById('createModal').classList.remove('show');
    }
    
    async createKey() {
        const keyName = document.getElementById('newKeyName').value;
        const notes = document.getElementById('newKeyNotes').value;
        
        if (!keyName) {
            this.showError('Vui lòng nhập tên key');
            return;
        }
        
        try {
            const response = await fetch(`${this.baseUrl}/api/keys`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${this.token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ key_name: keyName, notes })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.hideCreateModal();
                this.loadKeys();
                this.loadActivity();
                this.showToast('Key đã được tạo thành công');
            } else {
                this.showError(data.error || 'Lỗi khi tạo key');
            }
        } catch (error) {
            this.showError('Lỗi kết nối đến server');
            console.error('Create key error:', error);
        }
    }
    
    async viewKey(keyId) {
        try {
            const key = this.keys.find(k => k.id === keyId);
            if (!key) return;
            
            this.currentKeyId = keyId;
            
            // Fill modal with key details
            document.getElementById('detailKeyName').textContent = key.key_name;
            document.getElementById('detailServerKey').textContent = key.server_key;
            document.getElementById('detailApiKey').textContent = key.api_key;
            document.getElementById('detailStatus').textContent = key.status === 'active' ? 'Active' : 'Locked';
            document.getElementById('detailStatus').className = `status-badge ${key.status}`;
            document.getElementById('detailCreatedAt').textContent = new Date(key.created_at).toLocaleString('vi-VN');
            document.getElementById('detailLastReset').textContent = key.last_reset_at 
                ? new Date(key.last_reset_at).toLocaleString('vi-VN')
                : 'Chưa reset';
            document.getElementById('detailNotes').textContent = key.notes || 'Không có ghi chú';
            
            // Bind action buttons
            const resetBtn = document.getElementById('resetKeyBtn');
            const lockBtn = document.getElementById('toggleLockBtn');
            const deleteBtn = document.getElementById('deleteKeyBtn');
            
            resetBtn.onclick = () => this.resetKey(keyId);
            lockBtn.onclick = () => this.toggleLock(keyId);
            deleteBtn.onclick = () => this.deleteKey(keyId);
            
            // Update lock button text
            lockBtn.innerHTML = `<i class="fas fa-${key.status === 'active' ? 'lock' : 'unlock'}"></i> ${key.status === 'active' ? 'Khóa Key' : 'Mở khóa Key'}`;
            
            // Bind copy buttons
            document.querySelectorAll('.btn-copy').forEach(btn => {
                btn.onclick = (e) => {
                    const targetId = e.target.closest('.btn-copy').dataset.target;
                    const text = document.getElementById(targetId).textContent;
                    this.copyToClipboard(text);
                };
            });
            
            document.getElementById('keyModal').classList.add('show');
        } catch (error) {
            console.error('Error viewing key:', error);
        }
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
                this.loadKeys();
                this.loadActivity();
                this.showToast('Key đã được reset thành công');
                
                // Close key modal if open
                document.getElementById('keyModal').classList.remove('show');
            } else {
                this.showError(data.error || 'Lỗi khi reset key');
            }
        } catch (error) {
            this.showError('Lỗi kết nối đến server');
            console.error('Reset key error:', error);
        }
    }
    
    async toggleLock(keyId) {
        const key = this.keys.find(k => k.id === keyId);
        if (!key) return;
        
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
                this.loadKeys();
                this.loadActivity();
                this.showToast(`Key đã được ${action} thành công`);
                
                // Close key modal if open
                document.getElementById('keyModal').classList.remove('show');
            } else {
                this.showError(data.error || `Lỗi khi ${action} key`);
            }
        } catch (error) {
            this.showError('Lỗi kết nối đến server');
            console.error('Toggle lock error:', error);
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
                this.loadKeys();
                this.loadActivity();
                this.showToast('Key đã được xóa thành công');
                
                // Close key modal if open
                document.getElementById('keyModal').classList.remove('show');
            } else {
                this.showError(data.error || 'Lỗi khi xóa key');
            }
        } catch (error) {
            this.showError('Lỗi kết nối đến server');
            console.error('Delete key error:', error);
        }
    }
    
    filterKeys(searchTerm) {
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
        if (key.length <= length) return key;
        return key.substring(0, length) + '...';
    }
    
    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
            this.showToast('Đã sao chép vào clipboard');
        }).catch(err => {
            console.error('Copy failed:', err);
        });
    }
    
    showToast(message) {
        const toast = document.getElementById('toast');
        const messageEl = document.getElementById('toastMessage');
        
        messageEl.textContent = message;
        toast.classList.remove('hidden');
        
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 3000);
    }
    
    showError(message) {
        const errorEl = document.getElementById('loginError');
        errorEl.textContent = message;
        errorEl.style.display = 'block';
        
        setTimeout(() => {
            errorEl.style.display = 'none';
        }, 5000);
    }
}

// Initialize admin panel when page loads
let admin;
document.addEventListener('DOMContentLoaded', () => {
    admin = new AdminPanel();
});
