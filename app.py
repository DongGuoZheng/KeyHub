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
        token = request.headers.get("X-Admin-Token")
        if not token:
            return jsonify({"message": "未授权访问"}), 401

        # Validate token by checking if it matches any user's token
        conn = get_db_connection()
        users = conn.execute("SELECT username, password FROM admin_users").fetchall()
        conn.close()

        valid = False
        for user in users:
            expected_token = generate_admin_token(user["username"], user["password"])
            if token == expected_token:
                valid = True
                break

        if not valid:
            return jsonify({"message": "未授权访问"}), 401
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/admin")
def admin_page():
    return render_template("admin.html")


@app.route("/docs")
def docs_page():
    return render_template("docs.html")


# --- Authentication API ---
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"message": "用户名和密码不能为空"}), 400

    # Check username and password directly (plain text)
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM admin_users WHERE username = ? AND password = ?",
        (username, password),
    ).fetchone()
    conn.close()

    if user:
        # Generate token using username and plain password
        token = generate_admin_token(username, password)
        return jsonify({"success": True, "token": token, "message": "登录成功"})
    else:
        return jsonify({"message": "用户名或密码错误"}), 401


# --- Projects API ---
@app.route("/api/projects", methods=["GET"])
@require_admin_token
def get_projects():
    conn = get_db_connection()
    projects = conn.execute(
        "SELECT * FROM projects ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(p) for p in projects])


@app.route("/api/projects", methods=["POST"])
@require_admin_token
def create_project():
    data = request.json
    name = data.get("name")
    description = data.get("description", "")
    if not name:
        return jsonify({"message": "项目名称必填"}), 400

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO projects (name, description, created_at) VALUES (?, ?, ?)",
            (name, description, datetime.datetime.now().isoformat()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"message": "项目名称已存在"}), 400
    conn.close()
    return jsonify({"success": True, "message": "项目创建成功"})


@app.route("/api/projects/<int:id>", methods=["PUT"])
@require_admin_token
def update_project(id):
    data = request.json
    name = data.get("name")
    description = data.get("description")

    conn = get_db_connection()
    # Check if default
    proj = conn.execute(
        "SELECT is_default FROM projects WHERE id = ?", (id,)
    ).fetchone()
    if not proj:
        conn.close()
        return jsonify({"message": "未找到项目"}), 404

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
            conn.execute(
                f'UPDATE projects SET {", ".join(updates)} WHERE id = ?', params
            )
            conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"message": "名称冲突"}), 400

    conn.close()
    return jsonify({"success": True, "message": "项目已更新"})


@app.route("/api/projects/<int:id>", methods=["DELETE"])
@require_admin_token
def delete_project(id):
    conn = get_db_connection()
    proj = conn.execute(
        "SELECT is_default FROM projects WHERE id = ?", (id,)
    ).fetchone()
    if not proj:
        conn.close()
        return jsonify({"message": "未找到项目"}), 404

    if proj["is_default"]:
        conn.close()
        return jsonify({"message": "无法删除默认项目"}), 403

    conn.execute("DELETE FROM projects WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "项目已删除"})


# --- Licenses API (formerly Keys API) ---
@app.route("/api/keys", methods=["GET"])
@require_admin_token
def get_keys():
    project_id = request.args.get("project_id")
    conn = get_db_connection()
    query = """
        SELECT l.*
        FROM licenses l 
    """
    params = []
    if project_id:
        query += " WHERE l.project_id = ?"
        params.append(project_id)

    query += " ORDER BY l.created_at DESC"

    licenses = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(l) for l in licenses])


@app.route("/api/keys", methods=["POST"])
@require_admin_token
def create_key():
    data = request.json
    project_id = data.get("project_id")
    remarks = data.get("remarks", "")
    custom_key = data.get("custom_key")

    if not project_id:
        return jsonify({"message": "项目 ID 必填"}), 400

    conn = get_db_connection()

    if custom_key:
        # User provided custom key
        new_key = custom_key
    else:
        # Auto-generate key
        new_key = generate_key()

    # Ensure uniqueness (simple retry logic)
    for attempt in range(5):
        try:
            conn.execute(
                """INSERT INTO licenses (
                    project_id, license_key, 
                    is_active, remarks, created_at
                ) VALUES (?, ?, 1, ?, ?)""",
                (
                    project_id,
                    new_key,
                    remarks,
                    datetime.datetime.now().isoformat(),
                ),
            )
            conn.commit()
            break
        except sqlite3.IntegrityError:
            if custom_key:
                conn.close()
                return jsonify({"message": "该密钥在此项目中已存在"}), 400
            new_key = generate_key()
    else:
        conn.close()
        return jsonify({"message": "生成唯一密钥失败"}), 500

    conn.close()
    return jsonify({"success": True, "key": new_key, "message": "授权创建成功"})


# --- Public Registration API (No Auth Required) ---
@app.route("/api/register", methods=["POST"])
def register_user():
    """Public endpoint for client-side user registration"""
    data = request.json or {}
    custom_key = data.get("key") or data.get("custom_key")
    remarks = data.get("remarks", "")
    project_name = data.get("project_name")

    if not custom_key:
        return jsonify({"success": False, "message": "密钥不能为空"}), 400

    if not project_name:
        return jsonify({"success": False, "message": "项目名称必填"}), 400

    conn = get_db_connection()

    # Require explicit project name to locate the target project
    project = conn.execute(
        "SELECT id FROM projects WHERE name = ?", (project_name,)
    ).fetchone()
    if not project:
        conn.close()
        return jsonify({"success": False, "message": "指定的项目不存在"}), 404

    project_id = project["id"]

    # Create license with custom key
    try:
        conn.execute(
            """INSERT INTO licenses (
                project_id, license_key, 
                is_active, remarks, created_at
            ) VALUES (?, ?, 1, ?, ?)""",
            (
                project_id,
                custom_key,
                remarks,
                datetime.datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "key": custom_key, "message": "注册成功"}), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "message": "该密钥在此项目中已存在"}), 409
    except Exception as exc:
        conn.close()
        return jsonify({"success": False, "message": f"注册失败: {str(exc)}"}), 500


@app.route("/api/keys/<key_value>", methods=["DELETE"])
@require_admin_token
def delete_key(key_value):
    conn = get_db_connection()
    # Find the license by license_key (need to check project_id from query or handle all)
    # For simplicity, delete by license_key (assuming it's unique enough, or we need project_id)
    project_id = request.args.get("project_id")
    if project_id:
        conn.execute("DELETE FROM licenses WHERE license_key = ? AND project_id = ?", (key_value, project_id))
    else:
        conn.execute("DELETE FROM licenses WHERE license_key = ?", (key_value,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "授权已删除"})


@app.route("/api/keys/<key_value>/status", methods=["PUT"])
@require_admin_token
def toggle_key_status(key_value):
    data = request.json
    is_active = data.get("is_active")
    if is_active is None:
        return jsonify({"message": "缺少状态参数"}), 400

    conn = get_db_connection()
    project_id = request.args.get("project_id")
    if project_id:
        conn.execute(
            "UPDATE licenses SET is_active = ? WHERE license_key = ? AND project_id = ?",
            (1 if is_active else 0, key_value, project_id),
        )
    else:
        conn.execute(
            "UPDATE licenses SET is_active = ? WHERE license_key = ?",
            (1 if is_active else 0, key_value),
        )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "状态已更新"})


@app.route("/api/keys/<key_value>/remarks", methods=["PUT"])
@require_admin_token
def update_key_remarks(key_value):
    data = request.json
    remarks = data.get("remarks", "")

    conn = get_db_connection()
    project_id = request.args.get("project_id")
    if project_id:
        conn.execute("UPDATE licenses SET remarks = ? WHERE license_key = ? AND project_id = ?", 
                    (remarks, key_value, project_id))
    else:
        conn.execute("UPDATE licenses SET remarks = ? WHERE license_key = ?", (remarks, key_value))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "备注已更新"})


# --- Verification API (Simplified, No Machine Binding) ---
@app.route("/api/verify", methods=["POST"])
def verify_key():
    data = request.json
    key_value = data.get("key")
    project_name = data.get("project_name")

    if not key_value:
        return jsonify({"valid": False, "message": "密钥不能为空"}), 400

    if not project_name:
        return jsonify({"valid": False, "message": "项目名称不能为空"}), 400

    conn = get_db_connection()

    # Fetch license info by license_key and project_name
    query = """
        SELECT l.*, p.name as project_name
        FROM licenses l
        JOIN projects p ON l.project_id = p.id
        WHERE l.license_key = ? AND p.name = ?
    """
    license_row = conn.execute(query, (key_value, project_name)).fetchone()

    if not license_row:
        conn.close()
        return jsonify({"valid": False, "message": "未找到该密钥在此项目下的授权"}), 404

    # Check Active Status
    if not license_row["is_active"]:
        conn.close()
        return jsonify({"valid": False, "message": "授权已禁用"}), 403

    conn.close()
    return jsonify({
        "valid": True,
        "message": "验证通过",
        "project_name": license_row["project_name"]
    })


# --- Admin Management API ---
@app.route("/api/admin/users", methods=["GET"])
@require_admin_token
def get_admin_users():
    """Get all admin users"""
    conn = get_db_connection()
    users = conn.execute(
        "SELECT id, username, created_at FROM admin_users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(u) for u in users])


@app.route("/api/admin/users", methods=["POST"])
@require_admin_token
def create_admin_user():
    """Create a new admin user"""
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "用户名和密码不能为空"}), 400

    conn = get_db_connection()
    try:
        # Check if username already exists
        existing = conn.execute(
            "SELECT id FROM admin_users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            conn.close()
            return jsonify({"error": "用户名已存在"}), 400

        now = datetime.datetime.now().isoformat()
        conn.execute(
            "INSERT INTO admin_users (username, password, created_at) VALUES (?, ?, ?)",
            (username, password, now),
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "管理员创建成功"})
    except Exception as e:
        conn.close()
        return jsonify({"error": f"创建失败: {str(e)}"}), 500


@app.route("/api/admin/users/<username>", methods=["DELETE"])
@require_admin_token
def delete_admin_user(username):
    """Delete an admin user"""
    conn = get_db_connection()

    # Check if it's the default admin
    if username == "admin":
        conn.close()
        return jsonify({"error": "不能删除默认管理员账户"}), 403

    # Check if it's the last admin
    admin_count = conn.execute("SELECT COUNT(*) as count FROM admin_users").fetchone()[
        "count"
    ]
    if admin_count <= 1:
        conn.close()
        return jsonify({"error": "不能删除最后一个管理员账户"}), 403

    # Check if user exists
    user = conn.execute(
        "SELECT id FROM admin_users WHERE username = ?", (username,)
    ).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "用户不存在"}), 404

    conn.execute("DELETE FROM admin_users WHERE username = ?", (username,))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "管理员已删除"})


@app.route("/api/admin/users/<username>", methods=["PUT"])
@require_admin_token
def update_admin_username(username):
    """Update admin username"""
    data = request.json
    new_username = data.get("new_username")

    if not new_username:
        return jsonify({"error": "新用户名不能为空"}), 400

    if username == "admin":
        return jsonify({"error": "不能修改默认管理员的用户名"}), 403

    conn = get_db_connection()

    # Check if user exists
    user = conn.execute(
        "SELECT id FROM admin_users WHERE username = ?", (username,)
    ).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "用户不存在"}), 404

    # Check if new username already exists
    existing = conn.execute(
        "SELECT id FROM admin_users WHERE username = ?", (new_username,)
    ).fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "新用户名已存在"}), 400

    try:
        conn.execute(
            "UPDATE admin_users SET username = ? WHERE username = ?",
            (new_username, username),
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "用户名已更新"})
    except Exception as e:
        conn.close()
        return jsonify({"error": f"更新失败: {str(e)}"}), 500


@app.route("/api/admin/users/<username>/password", methods=["PUT"])
@require_admin_token
def update_admin_password(username):
    """Update admin password"""
    data = request.json
    new_password = data.get("new_password")

    if not new_password:
        return jsonify({"error": "新密码不能为空"}), 400

    conn = get_db_connection()

    # Check if user exists
    user = conn.execute(
        "SELECT id FROM admin_users WHERE username = ?", (username,)
    ).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "用户不存在"}), 404

    try:
        conn.execute(
            "UPDATE admin_users SET password = ? WHERE username = ?",
            (new_password, username),
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "密码已更新"})
    except Exception as e:
        conn.close()
        return jsonify({"error": f"更新失败: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True)
