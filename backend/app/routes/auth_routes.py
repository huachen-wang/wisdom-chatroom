from flask import Blueprint, request, jsonify
import uuid
import base64
from flask_cors import cross_origin
from mysql.connector import connect

auth_bp = Blueprint('auth', __name__)


def get_conn():
    return connect(
        host="",
        port="",
        user="",
        password="",
        database=""
    )


def is_valid_token(token):
    try:
        return base64.b64decode(token).decode("utf-8") == "huachenwang.net"
    except Exception:
        return False


# ✅ 登录或注册接口（仅返回 user_id，不创建 session）
@auth_bp.route("/api/login_or_register", methods=["POST"])
@cross_origin()
def login_or_register():
    print("🔥 login_or_register 接口被调用了！")
    data = request.get_json()
    email = data.get("email")
    name = data.get("username")

    conn = get_conn()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM chatroom_users WHERE email = %s", (email,))
    user = cursor.fetchone()

    # ✅ 用户已存在
    if user:
        if user["name"] != name:
            cursor.close()
            conn.close()
            return jsonify({"success": False, "message": "请检查您的用户名。"})
        user_id = user["id"]

    # ✅ 新用户注册
    else:
        cursor.execute("INSERT INTO chatroom_users (name, email) VALUES (%s, %s)", (name, email))
        conn.commit()
        user_id = cursor.lastrowid

    cursor.close()
    conn.close()

    # ✅ 只返回 user_id，不返回 session_id
    return jsonify({
        "success": True,
        "user_id": user_id
    })

@auth_bp.route("/api/session/new", methods=["POST"])
@cross_origin()
def create_new_session():
    data = request.get_json()
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"success": False, "message": "缺少 user_id 参数"}), 400

    conn = get_conn()
    cursor = conn.cursor()
    new_session_id = str(uuid.uuid4())

    cursor.execute("""
        INSERT INTO chatroom_sessions (session_id, user_id) 
        VALUES (%s, %s)
    """, (new_session_id, user_id))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({
        "success": True,
        "session_id": new_session_id
    })