from flask import Flask, render_template, request, jsonify
import sqlite3
import hashlib
import os
import datetime
import functools
import uuid
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


PLAY_SESSION_TIMEOUT_HOURS = 8
COUNT_BASED_AUTH_TYPES = {"count", "count_date"}
PROJECT_TYPES = {
    "account": "账号管理",
    "activation": "激活码授权管理",
    "playback": "播控管理",
}


def normalize_project_type(project_type):
    project_type = project_type or "activation"
    if project_type not in PROJECT_TYPES:
        return None
    return project_type


def utc_now_iso():
    return datetime.datetime.now().isoformat()


def parse_date_or_datetime(value):
    if not value:
        return None

    try:
        if len(value) == 10:
            return datetime.datetime.combine(
                datetime.date.fromisoformat(value), datetime.time.max
            )
        return datetime.datetime.fromisoformat(value)
    except ValueError:
        return None


def is_license_expired(license_row):
    expires_at = parse_date_or_datetime(license_row["valid_until"])
    if not expires_at:
        return False
    return datetime.datetime.now() > expires_at


def uses_play_count(license_row):
    return license_row["auth_type"] in COUNT_BASED_AUTH_TYPES


def has_remaining_plays(license_row):
    if not uses_play_count(license_row):
        return True
    remaining = license_row["remaining_plays"]
    return remaining is not None and remaining > 0


def normalize_auth_type(auth_type):
    allowed = {"unlimited", "count", "date", "count_date"}
    if auth_type not in allowed:
        return None
    return auth_type


def serialize_license_status(license_row):
    expired = is_license_expired(license_row)
    count_ok = has_remaining_plays(license_row)
    active = bool(license_row["is_active"])
    playable = active and not expired and count_ok

    if not active:
        message = "授权已禁用"
    elif expired:
        message = "授权已过期"
    elif not count_ok:
        message = "剩余播放次数不足"
    else:
        message = "授权可用"

    return {
        "id": license_row["id"],
        "key": license_row["license_key"],
        "project_id": license_row["project_id"],
        "project_name": license_row["project_name"],
        "project_type": license_row["project_type"],
        "is_active": active,
        "auth_type": license_row["auth_type"] or "unlimited",
        "remaining_plays": license_row["remaining_plays"],
        "valid_until": license_row["valid_until"],
        "machine_code": license_row["machine_code"],
        "last_play_started_at": license_row["last_play_started_at"],
        "playable": playable,
        "expired": expired,
        "message": message,
    }


def get_license_for_client(conn, key_value, project_name):
    return conn.execute(
        """
        SELECT l.*, p.name as project_name, p.project_type as project_type
        FROM licenses l
        JOIN projects p ON l.project_id = p.id
        WHERE (l.license_key = ? OR (p.project_type = 'playback' AND l.machine_code = ?))
            AND p.name = ?
        """,
        (key_value, key_value, project_name),
    ).fetchone()


def check_machine_code(license_row, machine_code):
    expected = license_row["machine_code"]
    if expected and expected != machine_code:
        return False
    return True


def mark_stale_play_sessions(conn):
    cutoff = (
        datetime.datetime.now()
        - datetime.timedelta(hours=PLAY_SESSION_TIMEOUT_HOURS)
    ).isoformat()
    conn.execute(
        """
        UPDATE play_sessions
        SET status = 'timeout',
            ended_at = COALESCE(ended_at, last_heartbeat_at, started_at),
            duration_seconds = CAST(
                (julianday(COALESCE(last_heartbeat_at, started_at)) - julianday(started_at)) * 86400
                AS INTEGER
            )
        WHERE status = 'playing' AND started_at < ?
        """,
        (cutoff,),
    )


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
    return render_template(
        "docs.html",
        doc_type="activation",
        project_types=PROJECT_TYPES,
    )


@app.route("/docs/<doc_type>")
def docs_by_type(doc_type):
    doc_type = normalize_project_type(doc_type)
    if not doc_type:
        return jsonify({"message": "文档类型不存在"}), 404
    return render_template(
        "docs.html",
        doc_type=doc_type,
        project_types=PROJECT_TYPES,
    )


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
    data = request.json or {}
    name = data.get("name")
    description = data.get("description", "")
    project_type = normalize_project_type(data.get("project_type"))
    if not name:
        return jsonify({"message": "项目名称必填"}), 400
    if not project_type:
        return jsonify({"message": "项目类型无效"}), 400

    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO projects (
                name, description, project_type, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (name, description, project_type, datetime.datetime.now().isoformat()),
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
    data = request.json or {}
    name = data.get("name")
    description = data.get("description")
    project_type = data.get("project_type")
    if project_type is not None:
        project_type = normalize_project_type(project_type)
        if not project_type:
            return jsonify({"message": "项目类型无效"}), 400

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
        if project_type is not None:
            updates.append("project_type = ?")
            params.append(project_type)

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
    data = request.json or {}
    project_id = data.get("project_id")
    remarks = data.get("remarks", "")
    custom_key = (data.get("custom_key") or "").strip()

    if not project_id:
        return jsonify({"message": "项目 ID 必填"}), 400

    conn = get_db_connection()
    project = conn.execute(
        "SELECT project_type FROM projects WHERE id = ?", (project_id,)
    ).fetchone()
    if not project:
        conn.close()
        return jsonify({"message": "项目不存在"}), 404

    project_type = project["project_type"] or "activation"
    if project_type == "playback" and not custom_key:
        conn.close()
        return jsonify({"message": "播控项目需填写客户端机器码"}), 400

    if custom_key:
        new_key = custom_key
    else:
        new_key = generate_key()

    machine_code = new_key if project_type == "playback" else None

    # Ensure uniqueness (simple retry logic)
    for attempt in range(5):
        try:
            conn.execute(
                """INSERT INTO licenses (
                    project_id, license_key, 
                    is_active, remarks, created_at, machine_code
                ) VALUES (?, ?, 1, ?, ?, ?)""",
                (
                    project_id,
                    new_key,
                    remarks,
                    datetime.datetime.now().isoformat(),
                    machine_code,
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
    now = datetime.datetime.now().isoformat()
    try:
        conn.execute(
            """INSERT INTO licenses (
                project_id, license_key,
                is_active, remarks, created_at, last_registered_at
            ) VALUES (?, ?, 1, ?, ?, ?)""",
            (
                project_id,
                custom_key,
                remarks,
                now,
                now,
            ),
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "key": custom_key, "message": "注册成功"}), 201
    except sqlite3.IntegrityError:
        # Key already exists - update last_registered_at timestamp
        try:
            now2 = datetime.datetime.now().isoformat()
            conn.execute(
                """UPDATE licenses SET last_registered_at = ?
                   WHERE license_key = ? AND project_id = ?""",
                (now2, custom_key, project_id),
            )
            conn.commit()
            conn.close()
            return jsonify({"success": True, "key": custom_key, "message": "重新注册成功"}), 200
        except Exception as upd_exc:
            conn.close()
            return jsonify({"success": False, "message": f"更新注册时间失败: {str(upd_exc)}"}), 500
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


# --- License Entitlement Admin API ---
@app.route("/api/licenses/<int:license_id>/entitlement", methods=["PUT"])
@require_admin_token
def update_license_entitlement(license_id):
    data = request.json or {}
    auth_type = normalize_auth_type(data.get("auth_type", "unlimited"))
    if not auth_type:
        return jsonify({"message": "授权类型无效"}), 400

    remaining_plays = data.get("remaining_plays")
    add_plays = data.get("add_plays")
    valid_until = data.get("valid_until") or None

    if valid_until and not parse_date_or_datetime(valid_until):
        return jsonify({"message": "到期时间格式无效"}), 400

    conn = get_db_connection()
    license_row = conn.execute(
        """
        SELECT l.*, p.name as project_name, p.project_type as project_type
        FROM licenses l
        JOIN projects p ON l.project_id = p.id
        WHERE l.id = ?
        """,
        (license_id,),
    ).fetchone()
    if not license_row:
        conn.close()
        return jsonify({"message": "未找到授权"}), 404
    if license_row["project_type"] != "playback":
        conn.close()
        return jsonify({"message": "仅播控管理项目可设置次数和到期时间"}), 400

    try:
        if remaining_plays in ("", None):
            next_remaining_plays = (
                0 if auth_type in COUNT_BASED_AUTH_TYPES else None
            )
        else:
            next_remaining_plays = int(remaining_plays)
            if next_remaining_plays < 0:
                raise ValueError

        if add_plays not in ("", None):
            add_plays = int(add_plays)
            if add_plays < 0:
                raise ValueError
            next_remaining_plays = (next_remaining_plays or 0) + add_plays
    except (TypeError, ValueError):
        conn.close()
        return jsonify({"message": "播放次数必须是非负整数"}), 400

    conn.execute(
        """
        UPDATE licenses
        SET auth_type = ?,
            remaining_plays = ?,
            valid_until = ?
        WHERE id = ?
        """,
        (auth_type, next_remaining_plays, valid_until, license_id),
    )
    conn.commit()

    row = conn.execute(
        """
        SELECT l.*, p.name as project_name, p.project_type as project_type
        FROM licenses l
        JOIN projects p ON l.project_id = p.id
        WHERE l.id = ?
        """,
        (license_id,),
    ).fetchone()
    result = serialize_license_status(row)
    conn.close()
    return jsonify({"success": True, "message": "授权权益已更新", "license": result})


@app.route("/api/licenses/<int:license_id>/play-sessions", methods=["GET"])
@require_admin_token
def get_license_play_sessions(license_id):
    limit = request.args.get("limit", 100)
    try:
        limit = max(1, min(int(limit), 500))
    except ValueError:
        limit = 100

    conn = get_db_connection()
    mark_stale_play_sessions(conn)
    conn.commit()

    sessions = conn.execute(
        """
        SELECT *
        FROM play_sessions
        WHERE license_id = ?
        ORDER BY started_at DESC
        LIMIT ?
        """,
        (license_id, limit),
    ).fetchall()
    conn.close()
    return jsonify([dict(session) for session in sessions])


# --- Verification API ---
@app.route("/api/verify", methods=["POST"])
def verify_key():
    data = request.json or {}
    key_value = data.get("key")
    project_name = data.get("project_name")
    machine_code = data.get("machine_code")

    if not key_value:
        return jsonify({"valid": False, "message": "密钥不能为空"}), 400

    if not project_name:
        return jsonify({"valid": False, "message": "项目名称不能为空"}), 400

    conn = get_db_connection()

    license_row = get_license_for_client(conn, key_value, project_name)

    if not license_row:
        conn.close()
        return jsonify({"valid": False, "message": "未找到该密钥在此项目下的授权"}), 404

    if not check_machine_code(license_row, machine_code):
        conn.close()
        return jsonify({"valid": False, "message": "机器码不匹配"}), 403

    status = serialize_license_status(license_row)
    if not status["playable"]:
        conn.close()
        return jsonify({"valid": False, "message": status["message"], **status}), 403

    conn.close()
    return jsonify({
        "valid": True,
        "message": "验证通过",
        **status
    })


# --- Public Playback API ---
@app.route("/api/license/status", methods=["POST"])
def license_status():
    data = request.json or {}
    key_value = data.get("key") or data.get("machine_code")
    project_name = data.get("project_name")
    machine_code = data.get("machine_code") or key_value

    if not key_value:
        return jsonify({"valid": False, "message": "机器码不能为空"}), 400
    if not project_name:
        return jsonify({"valid": False, "message": "项目名称不能为空"}), 400

    conn = get_db_connection()
    license_row = get_license_for_client(conn, key_value, project_name)
    if not license_row:
        conn.close()
        return jsonify({"valid": False, "message": "未找到该密钥在此项目下的授权"}), 404

    if not check_machine_code(license_row, machine_code):
        conn.close()
        return jsonify({"valid": False, "message": "机器码不匹配"}), 403

    if license_row["project_type"] != "playback":
        conn.close()
        return jsonify({"valid": False, "message": "该项目不是播控管理类型"}), 400

    status = serialize_license_status(license_row)
    conn.close()
    return jsonify({"valid": status["playable"], **status})


@app.route("/api/play/start", methods=["POST"])
def start_play():
    data = request.json or {}
    key_value = data.get("key") or data.get("machine_code")
    project_name = data.get("project_name")
    machine_code = data.get("machine_code") or key_value
    client_version = data.get("client_version")
    remarks = data.get("remarks", "")

    if not key_value:
        return jsonify({"success": False, "message": "机器码不能为空"}), 400
    if not project_name:
        return jsonify({"success": False, "message": "项目名称不能为空"}), 400
    if not machine_code:
        return jsonify({"success": False, "message": "机器码不能为空"}), 400

    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        mark_stale_play_sessions(conn)
        license_row = get_license_for_client(conn, key_value, project_name)
        if not license_row:
            conn.rollback()
            conn.close()
            return jsonify({"success": False, "message": "未找到该密钥在此项目下的授权"}), 404

        if not check_machine_code(license_row, machine_code):
            conn.rollback()
            conn.close()
            return jsonify({"success": False, "message": "机器码不匹配"}), 403

        if license_row["project_type"] != "playback":
            conn.rollback()
            conn.close()
            return jsonify({"success": False, "message": "该项目不是播控管理类型"}), 400

        status = serialize_license_status(license_row)
        if not status["playable"]:
            conn.rollback()
            conn.close()
            return jsonify({"success": False, "message": status["message"], **status}), 403

        now = utc_now_iso()
        if uses_play_count(license_row):
            cursor = conn.execute(
                """
                UPDATE licenses
                SET remaining_plays = remaining_plays - 1,
                    last_play_started_at = ?
                WHERE id = ? AND remaining_plays > 0
                """,
                (now, license_row["id"]),
            )
            if cursor.rowcount == 0:
                conn.rollback()
                conn.close()
                return jsonify({"success": False, "message": "剩余播放次数不足"}), 403
        else:
            conn.execute(
                "UPDATE licenses SET last_play_started_at = ? WHERE id = ?",
                (now, license_row["id"]),
            )

        session_id = uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO play_sessions (
                license_id, project_id, session_id, machine_code,
                started_at, last_heartbeat_at, status, client_version, remarks
            ) VALUES (?, ?, ?, ?, ?, ?, 'playing', ?, ?)
            """,
            (
                license_row["id"],
                license_row["project_id"],
                session_id,
                machine_code,
                now,
                now,
                client_version,
                remarks,
            ),
        )
        conn.commit()

        updated = conn.execute(
            """
            SELECT l.*, p.name as project_name, p.project_type as project_type
            FROM licenses l
            JOIN projects p ON l.project_id = p.id
            WHERE l.id = ?
            """,
            (license_row["id"],),
        ).fetchone()
        updated_status = serialize_license_status(updated)
        conn.close()
        return jsonify({
            "success": True,
            "message": "播放已开始",
            "session_id": session_id,
            **updated_status,
        })
    except Exception as exc:
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "message": f"开始播放失败: {str(exc)}"}), 500


@app.route("/api/play/end", methods=["POST"])
def end_play():
    data = request.json or {}
    session_id = data.get("session_id")
    remarks = data.get("remarks")

    if not session_id:
        return jsonify({"success": False, "message": "session_id 不能为空"}), 400

    conn = get_db_connection()
    session = conn.execute(
        "SELECT * FROM play_sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    if not session:
        conn.close()
        return jsonify({"success": False, "message": "未找到播放记录"}), 404

    if session["status"] == "ended":
        conn.close()
        return jsonify({"success": True, "message": "播放已结束"})

    now = utc_now_iso()
    started_at = parse_date_or_datetime(session["started_at"])
    duration_seconds = None
    if started_at:
        duration_seconds = max(
            0, int((datetime.datetime.now() - started_at).total_seconds())
        )

    conn.execute(
        """
        UPDATE play_sessions
        SET ended_at = ?,
            last_heartbeat_at = ?,
            duration_seconds = ?,
            status = 'ended',
            remarks = COALESCE(?, remarks)
        WHERE session_id = ?
        """,
        (now, now, duration_seconds, remarks, session_id),
    )
    conn.commit()
    conn.close()
    return jsonify({
        "success": True,
        "message": "播放已结束",
        "session_id": session_id,
        "duration_seconds": duration_seconds,
    })


@app.route("/api/play/heartbeat", methods=["POST"])
def play_heartbeat():
    data = request.json or {}
    session_id = data.get("session_id")
    if not session_id:
        return jsonify({"success": False, "message": "session_id 不能为空"}), 400

    conn = get_db_connection()
    session = conn.execute(
        "SELECT status FROM play_sessions WHERE session_id = ?", (session_id,)
    ).fetchone()
    if not session:
        conn.close()
        return jsonify({"success": False, "message": "未找到播放记录"}), 404

    if session["status"] != "playing":
        conn.close()
        return jsonify({"success": False, "message": "播放记录已结束"}), 409

    conn.execute(
        "UPDATE play_sessions SET last_heartbeat_at = ? WHERE session_id = ?",
        (utc_now_iso(), session_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "心跳已记录"})


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
    app.run(host="0.0.0.0", port=5001, debug=True)
