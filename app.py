from flask import Flask, render_template, request, jsonify
import sqlite3
import hashlib
import os
import datetime
import functools
from database import get_db_connection, init_db

app = Flask(__name__)

# Generate admin token from username and password
def generate_admin_token(username, password):
    """Generate a token from username and password"""
    salt = "keyhub_salt_2026"  # In production, use a secure random salt
    data = f"{username}:{password}:{salt}"
    return hashlib.sha256(data.encode()).hexdigest()

# Decorator to require admin token
def require_admin_token(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('X-Admin-Token')
        if not token:
            return jsonify({'error': '未授权访问'}), 401
        
        # Validate token by checking if it matches any user's token
        conn = get_db_connection()
        users = conn.execute('SELECT username, password FROM admin_users').fetchall()
        conn.close()
        
        valid = False
        for user in users:
            expected_token = generate_admin_token(user['username'], user['password'])
            if token == expected_token:
                valid = True
                break
        
        if not valid:
            return jsonify({'error': '未授权访问'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Initialize DB on startup
with app.app_context():
    init_db()

def generate_key():
    # Generate a random seed
    seed = os.urandom(32)
    # create hash
    hash_obj = hashlib.sha256(seed)
    full_hash = hash_obj.hexdigest().upper()
    # Format: KH-XXXXXXXX-XXXXXXXX (8 chars - 8 chars) from the hash
    # This gives us 16 random hex chars + prefix
    part1 = full_hash[:8]
    part2 = full_hash[8:16]
    return f"KH-{part1}-{part2}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

@app.route('/docs')
def docs_page():
    return render_template('docs.html')

# --- Authentication API ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    
    # Check username and password directly (plain text)
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM admin_users WHERE username = ? AND password = ?',
                       (username, password)).fetchone()
    conn.close()
    
    if user:
        # Generate token using username and plain password
        token = generate_admin_token(username, password)
        return jsonify({'success': True, 'token': token})
    else:
        return jsonify({'error': '用户名或密码错误'}), 401

# --- Projects API ---
@app.route('/api/projects', methods=['GET'])
@require_admin_token
def get_projects():
    conn = get_db_connection()
    projects = conn.execute('SELECT * FROM projects ORDER BY created_at DESC').fetchall()
    conn.close()
    return jsonify([dict(p) for p in projects])

@app.route('/api/projects', methods=['POST'])
@require_admin_token
def create_project():
    data = request.json
    name = data.get('name')
    description = data.get('description', '')
    if not name:
        return jsonify({'error': '项目名称必填'}), 400
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO projects (name, description, created_at) VALUES (?, ?, ?)',
                     (name, description, datetime.datetime.now().isoformat()))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': '项目名称已存在'}), 400
    conn.close()
    return jsonify({'success': True})

@app.route('/api/projects/<int:id>', methods=['PUT'])
@require_admin_token
def update_project(id):
    data = request.json
    name = data.get('name')
    description = data.get('description')
    
    conn = get_db_connection()
    # Check if default
    proj = conn.execute('SELECT is_default FROM projects WHERE id = ?', (id,)).fetchone()
    if not proj:
        conn.close()
        return jsonify({'error': '未找到项目'}), 404
    
    # Can't change default project? Spec says "Default project cannot be deleted", doesn't explicitly say not editable, but let's allow content edit.
    
    try:
        updates = []
        params = []
        if name:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
             updates.append("description = ?")
             params.append(description)
        
        if updates:
            params.append(id)
            conn.execute(f'UPDATE projects SET {", ".join(updates)} WHERE id = ?', params)
            conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': '名称冲突'}), 400

    conn.close()
    return jsonify({'success': True})

@app.route('/api/projects/<int:id>', methods=['DELETE'])
@require_admin_token
def delete_project(id):
    conn = get_db_connection()
    proj = conn.execute('SELECT is_default FROM projects WHERE id = ?', (id,)).fetchone()
    if not proj:
        conn.close()
        return jsonify({'error': '未找到项目'}), 404
    
    if proj['is_default']:
        conn.close()
        return jsonify({'error': '无法删除默认项目'}), 403
        
    conn.execute('DELETE FROM projects WHERE id = ?', (id,))
    conn.commit()
    conn.close() # Cascade delete should handle keys if configured, but need to enable foreign keys in sqlite
    # SQLite by default doesn't enforce FK unless PRAGMA foreign_keys = ON;
    # Let's fix that in connection or just ensure we clean up.
    # For now, assuming simple delete is fine or we manually clean.
    # Actually, easier to enable foreign keys in get_db_connection
    return jsonify({'success': True})

# --- Keys API ---
@app.route('/api/keys', methods=['GET'])
@require_admin_token
def get_keys():
    project_id = request.args.get('project_id')
    conn = get_db_connection()
    query = '''
        SELECT k.*, 
               (SELECT COUNT(*) FROM machine_bindings WHERE key_value = k.key) as binding_count 
        FROM keys k 
    '''
    params = []
    if project_id:
        query += ' WHERE k.project_id = ?'
        params.append(project_id)
    
    query += ' ORDER BY k.created_at DESC'
    
    keys = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(k) for k in keys])

@app.route('/api/keys', methods=['POST'])
@require_admin_token
def create_key():
    data = request.json
    project_id = data.get('project_id')
    remarks = data.get('remarks', '')
    count = data.get('count', 1)  # Optional: generate multiple (not in spec but useful) -> Spec says "One click generate", usually implies single.
    
    if not project_id:
        return jsonify({'error': '项目 ID 必填'}), 400
        
    conn = get_db_connection()
    new_key = generate_key()
    
    # Ensure uniqueness (simple retry logic)
    for _ in range(5):
        try:
            conn.execute('INSERT INTO keys (key, created_at, is_active, remarks, project_id) VALUES (?, ?, 1, ?, ?)',
                         (new_key, datetime.datetime.now().isoformat(), remarks, project_id))
            conn.commit()
            break
        except sqlite3.IntegrityError:
            new_key = generate_key()
    else:
        conn.close()
        return jsonify({'error': '生成唯一密钥失败'}), 500

    conn.close()
    return jsonify({'success': True, 'key': new_key})

@app.route('/api/keys/<key_value>', methods=['DELETE'])
@require_admin_token
def delete_key(key_value):
    conn = get_db_connection()
    # Manual cascade if FK not enabled, but good practice
    conn.execute('DELETE FROM machine_bindings WHERE key_value = ?', (key_value,))
    conn.execute('DELETE FROM keys WHERE key = ?', (key_value,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/keys/<key_value>/status', methods=['PUT'])
@require_admin_token
def toggle_key_status(key_value):
    data = request.json
    is_active = data.get('is_active')
    if is_active is None:
        return jsonify({'error': '缺少状态参数'}), 400
    
    conn = get_db_connection()
    conn.execute('UPDATE keys SET is_active = ? WHERE key = ?', (1 if is_active else 0, key_value))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/keys/<key_value>/remarks', methods=['PUT'])
@require_admin_token
def update_key_remarks(key_value):
    data = request.json
    remarks = data.get('remarks', '')
    
    conn = get_db_connection()
    conn.execute('UPDATE keys SET remarks = ? WHERE key = ?', (remarks, key_value))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# --- Bindings API ---
@app.route('/api/keys/<key_value>/bindings', methods=['GET'])
@require_admin_token
def get_bindings(key_value):
    conn = get_db_connection()
    bindings = conn.execute('SELECT * FROM machine_bindings WHERE key_value = ?', (key_value,)).fetchall()
    conn.close()
    return jsonify([dict(b) for b in bindings])

@app.route('/api/bindings/<int:id>', methods=['DELETE'])
@require_admin_token
def unbind_machine(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM machine_bindings WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/bindings/<int:id>/remarks', methods=['PUT'])
@require_admin_token
def update_binding_remarks(id):
    data = request.json
    remarks = data.get('remarks', '')
    conn = get_db_connection()
    conn.execute('UPDATE machine_bindings SET remarks = ? WHERE id = ?', (remarks, id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# --- Verification API (Core Logic) ---
@app.route('/api/verify', methods=['POST'])
def verify_key():
    data = request.json
    key_value = data.get('key')
    machine_id = data.get('machine_id')
    
    if not key_value or not machine_id:
        return jsonify({'valid': False, 'message': '缺少必要参数'}), 400
        
    conn = get_db_connection()
    
    # 1. Fetch Key Info - 在所有项目里查找密钥
    query = '''
        SELECT k.key, k.is_active
        FROM keys k
        WHERE k.key = ?
    '''
    key_row = conn.execute(query, (key_value,)).fetchone()
    
    if not key_row:
        conn.close()
        return jsonify({'valid': False, 'message': '未找到密钥'}), 404
         
    # 2. Check Active Status
    if not key_row['is_active']:
        conn.close()
        return jsonify({'valid': False, 'message': '密钥已禁用'}), 403

    # 3. Check Binding
    binding = conn.execute('SELECT * FROM machine_bindings WHERE key_value = ? AND machine_id = ?', 
                           (key_value, machine_id)).fetchone()
                           
    if binding:
        conn.close()
        return jsonify({'valid': True, 'message': '验证通过 (已绑定)'})
    else:
        # 4. Bind if not bound
        # Requirement: "No limit on bindings" -> Just insert new binding
        try:
            conn.execute('INSERT INTO machine_bindings (key_value, machine_id, bound_at) VALUES (?, ?, ?)',
                         (key_value, machine_id, datetime.datetime.now().isoformat()))
            conn.commit()
            conn.close()
            return jsonify({'valid': True, 'message': '验证通过 (新绑定已创建)'})
        except Exception as e:
            conn.close()
            return jsonify({'valid': False, 'message': f'绑定失败: {str(e)}'}), 500

# --- Admin Management API ---
@app.route('/api/admin/users', methods=['GET'])
@require_admin_token
def get_admin_users():
    """Get all admin users"""
    conn = get_db_connection()
    users = conn.execute('SELECT id, username, created_at FROM admin_users ORDER BY created_at DESC').fetchall()
    conn.close()
    return jsonify([dict(u) for u in users])

@app.route('/api/admin/users', methods=['POST'])
@require_admin_token
def create_admin_user():
    """Create a new admin user"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    
    conn = get_db_connection()
    try:
        # Check if username already exists
        existing = conn.execute('SELECT id FROM admin_users WHERE username = ?', (username,)).fetchone()
        if existing:
            conn.close()
            return jsonify({'error': '用户名已存在'}), 400
        
        now = datetime.datetime.now().isoformat()
        conn.execute('INSERT INTO admin_users (username, password, created_at) VALUES (?, ?, ?)',
                     (username, password, now))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '管理员创建成功'})
    except Exception as e:
        conn.close()
        return jsonify({'error': f'创建失败: {str(e)}'}), 500

@app.route('/api/admin/users/<username>', methods=['DELETE'])
@require_admin_token
def delete_admin_user(username):
    """Delete an admin user"""
    conn = get_db_connection()
    
    # Check if it's the default admin
    if username == 'admin':
        conn.close()
        return jsonify({'error': '不能删除默认管理员账户'}), 403
    
    # Check if it's the last admin
    admin_count = conn.execute('SELECT COUNT(*) as count FROM admin_users').fetchone()['count']
    if admin_count <= 1:
        conn.close()
        return jsonify({'error': '不能删除最后一个管理员账户'}), 403
    
    # Check if user exists
    user = conn.execute('SELECT id FROM admin_users WHERE username = ?', (username,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'error': '用户不存在'}), 404
    
    conn.execute('DELETE FROM admin_users WHERE username = ?', (username,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': '管理员已删除'})

@app.route('/api/admin/users/<username>', methods=['PUT'])
@require_admin_token
def update_admin_username(username):
    """Update admin username"""
    data = request.json
    new_username = data.get('new_username')
    
    if not new_username:
        return jsonify({'error': '新用户名不能为空'}), 400
    
    if username == 'admin':
        return jsonify({'error': '不能修改默认管理员的用户名'}), 403
    
    conn = get_db_connection()
    
    # Check if user exists
    user = conn.execute('SELECT id FROM admin_users WHERE username = ?', (username,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'error': '用户不存在'}), 404
    
    # Check if new username already exists
    existing = conn.execute('SELECT id FROM admin_users WHERE username = ?', (new_username,)).fetchone()
    if existing:
        conn.close()
        return jsonify({'error': '新用户名已存在'}), 400
    
    try:
        conn.execute('UPDATE admin_users SET username = ? WHERE username = ?', (new_username, username))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '用户名已更新'})
    except Exception as e:
        conn.close()
        return jsonify({'error': f'更新失败: {str(e)}'}), 500

@app.route('/api/admin/users/<username>/password', methods=['PUT'])
@require_admin_token
def update_admin_password(username):
    """Update admin password"""
    data = request.json
    new_password = data.get('new_password')
    
    if not new_password:
        return jsonify({'error': '新密码不能为空'}), 400
    
    conn = get_db_connection()
    
    # Check if user exists
    user = conn.execute('SELECT id FROM admin_users WHERE username = ?', (username,)).fetchone()
    if not user:
        conn.close()
        return jsonify({'error': '用户不存在'}), 404
    
    try:
        conn.execute('UPDATE admin_users SET password = ? WHERE username = ?', (new_password, username))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '密码已更新'})
    except Exception as e:
        conn.close()
        return jsonify({'error': f'更新失败: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
