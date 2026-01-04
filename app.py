# THÊM DÒNG NÀY Ở ĐẦU FILE (sau imports):
import os

# VÀ SỬA HÀM index() - TÌM DÒNG NÀY:
@app.route('/')
def index():
    return render_template('admin.html')

# THAY BẰNG:
@app.route('/')
def index():
    # Trả về HTML trực tiếp - không cần template file
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>License Admin Panel</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: #1a1a2e; color: white; font-family: Arial; }
            .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
            .card { background: #162447; border: 1px solid #1f4068; border-radius: 10px; }
            .btn-primary { background: #4361ee; border: none; }
            .btn-primary:hover { background: #3a0ca3; }
            .sidebar { background: #0f3460; min-height: 100vh; }
            .nav-link { color: #b8c1ec; }
            .nav-link.active { color: white; background: #1f4068; }
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <div class="row">
                <!-- Sidebar -->
                <div class="col-md-3 sidebar p-4">
                    <h3 class="mb-4">📋 License Admin</h3>
                    <div class="nav flex-column">
                        <button class="btn btn-dark mb-2 w-100" onclick="showSection('login')">Login</button>
                        <button class="btn btn-dark mb-2 w-100" onclick="showSection('create')">Create License</button>
                        <button class="btn btn-dark mb-2 w-100" onclick="showSection('api')">API Docs</button>
                    </div>
                    <hr>
                    <div class="text-muted small">
                        <p>API Endpoint:<br><code id="apiUrl"></code></p>
                    </div>
                </div>
                
                <!-- Main Content -->
                <div class="col-md-9 p-4">
                    <h2 id="title">License Management System</h2>
                    <hr>
                    
                    <!-- Login Section -->
                    <div id="loginSection">
                        <div class="card p-4">
                            <h4>🔐 Admin Login</h4>
                            <div class="alert alert-info">
                                <strong>Default Credentials:</strong><br>
                                Username: <code>admin</code><br>
                                Password: <code>admin123</code>
                            </div>
                            <form id="loginForm">
                                <div class="mb-3">
                                    <label>Username</label>
                                    <input type="text" id="username" class="form-control" required>
                                </div>
                                <div class="mb-3">
                                    <label>Password</label>
                                    <input type="password" id="password" class="form-control" required>
                                </div>
                                <button type="submit" class="btn btn-primary w-100">Login</button>
                            </form>
                            <div class="mt-3 text-center">
                                <button class="btn btn-sm btn-success" onclick="autoLogin()">Auto Login (Test)</button>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Create License Section -->
                    <div id="createSection" style="display:none;">
                        <div class="card p-4">
                            <h4>🆕 Create License</h4>
                            <form id="createForm">
                                <div class="mb-3">
                                    <label>Days Valid</label>
                                    <input type="number" id="days" class="form-control" value="30" min="1">
                                </div>
                                <div class="mb-3">
                                    <label>Note (Optional)</label>
                                    <textarea id="note" class="form-control" rows="2"></textarea>
                                </div>
                                <button type="submit" class="btn btn-primary">Create License Key</button>
                            </form>
                            <div id="result" class="mt-3"></div>
                        </div>
                    </div>
                    
                    <!-- API Docs Section -->
                    <div id="apiSection" style="display:none;">
                        <div class="card p-4">
                            <h4>📚 API Documentation</h4>
                            <h5 class="mt-3">Client API (for Android):</h5>
                            <pre class="bg-dark p-3 rounded">
POST /api/client/validate
Content-Type: application/json

{
    "license_key": "LIC-XXXX-XXXX-XXXX",
    "hwid": "device_id",
    "device_info": "Device Info"
}</pre>
                            
                            <h5 class="mt-3">Admin API:</h5>
                            <pre class="bg-dark p-3 rounded">
GET /api/admin/stats
Header: X-API-Key: your_api_key

POST /api/admin/licenses/create
Header: X-API-Key: your_api_key
Body: {"days_valid": 30, "note": "test"}</pre>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // Set API URL
            document.getElementById('apiUrl').textContent = window.location.origin;
            
            // Show section
            function showSection(section) {
                ['login', 'create', 'api'].forEach(s => {
                    document.getElementById(s + 'Section').style.display = 'none';
                });
                document.getElementById(section + 'Section').style.display = 'block';
                document.getElementById('title').textContent = 
                    section.charAt(0).toUpperCase() + section.slice(1) + ' - License Admin';
            }
            
            // Auto login for testing
            function autoLogin() {
                document.getElementById('username').value = 'admin';
                document.getElementById('password').value = 'admin123';
                alert('Credentials filled. Click Login button.');
            }
            
            // Login form
            document.getElementById('loginForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;
                
                try {
                    const response = await fetch('/api/admin/login', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({username, password})
                    });
                    
                    const data = await response.json();
                    if (data.success) {
                        alert('✅ Login successful! API is working.');
                        showSection('create');
                    } else {
                        alert('❌ Login failed: ' + data.message);
                    }
                } catch (error) {
                    alert('⚠️ Error: ' + error.message);
                }
            });
            
            // Create license
            document.getElementById('createForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                const days = document.getElementById('days').value;
                const note = document.getElementById('note').value;
                
                // Note: This requires API key - for demo only
                alert('To create license, you need API key. Check console for API test.');
                
                // Test API
                try {
                    const response = await fetch('/api/admin/stats');
                    const data = await response.json();
                    document.getElementById('result').innerHTML = `
                        <div class="alert alert-success">
                            ✅ API is working!<br>
                            Total Licenses: ${data.total_licenses || 0}<br>
                            <small>Note: Create license requires API key header</small>
                        </div>
                    `;
                } catch (error) {
                    document.getElementById('result').innerHTML = `
                        <div class="alert alert-danger">
                            ❌ API Error: ${error.message}
                        </div>
                    `;
                }
            });
            
            // Show login by default
            showSection('login');
        </script>
    </body>
    </html>
    '''
