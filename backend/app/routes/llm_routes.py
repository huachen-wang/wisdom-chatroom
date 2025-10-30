import random
import json
from flask import Blueprint, request, Response, stream_with_context, jsonify
from flask_cors import cross_origin
from mysql.connector import connect
from openai import OpenAI

llm_bp = Blueprint('llm', __name__)

# ✅ 数据库连接
def get_conn():
    return connect(
        host="",
        port="",
        user="",
        password="",
        database=""
    )

# ✅ 初始化 OpenAI 客户端（GPT-5）
llm_client = OpenAI(
    api_key=""
)

def call_openai_llm(prompt: str) -> str:
    response = llm_client.chat.completions.create(
        model="gpt-5",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

MENTORS = ["Tim Cook", "Mark Zuckerberg", "Warren Buffett"]

RESPONSE_PROMPT_TEMPLATE = """
You are {mentor}, a life mentor with a distinct personality and worldview. You are chatting in a room with several other mentors.

Here is the recent conversation history:
{history_block}

Now the user has a new question:
User: {user_question}

Please respond concisely in English, using {mentor}'s tone, values, and perspective.
If the topic invites deeper reflection, give a real-life example. Otherwise, keep it short and polite.

Important: Your answer must be a single paragraph, **no more than 100 words**.
Do not mention your name, other mentors, or meta-comments. Speak directly to the user as "you".
Only return your own response, nothing else.
"""

REACTION_PROMPT_TEMPLATE = """
You are {mentor}, a life mentor with a distinct personality and worldview. You are chatting in a room with several other mentors.

Here is the recent conversation history:
{history_block}

Please briefly react to the last two messages in the conversation.

Important: Your reaction must be concise, insightful, and **no more than 100 words**.
Do not mention your name, other mentors, or meta-comments. Speak directly to the user as "you".
Only return your own response, nothing else.
"""

def format_prompt(template_str, **kwargs):
    return template_str.format(**kwargs)

def save_message_to_db(session_id, sender, content):
    conn = get_conn()
    with conn.cursor() as cursor:
        sql = """
                    SELECT id, session_id, user_id, session_name, created_at
                    FROM chatroom_sessions
                    WHERE session_id = %s
                """
        cursor.execute(sql, (session_id,))
        rows = cursor.fetchall()
        if len(rows) > 0:
            session_name = rows[0][3]
            if session_name is None or session_name.strip() == "":
                new_session_name = content[:30] + "..." if len(content) > 30 else content
                update_sql = """
                    UPDATE chatroom_sessions
                    SET session_name = %s
                    WHERE session_id = %s
                """
                cursor.execute(update_sql, (new_session_name, session_id))
                conn.commit()
        sql = """
            INSERT INTO chatroom_chat_messages (session_id, sender, content)
            VALUES (%s, %s, %s)
        """
        cursor.execute(sql, (session_id, sender, content))
        conn.commit()

def get_recent_history_block(session_id, count=10):
    conn = get_conn()
    with conn.cursor(dictionary=True) as cursor:
        sql = """
            SELECT sender AS `from`, content
            FROM chatroom_chat_messages
            WHERE session_id = %s
            ORDER BY timestamp ASC
            LIMIT %s
        """
        cursor.execute(sql, (session_id, count))
        rows = cursor.fetchall()
        return "\n".join(f"{row['from']}：{row['content']}" for row in rows)

@llm_bp.route("/chatroom/stream", methods=["POST"])
@cross_origin()
def mentor_chatroom_stream():
    data = request.get_json()
    user_question = data.get("question", "").strip()
    session_id = data.get("session_id")

    if not user_question or not session_id:
        return Response("data: error\n\n", status=400, content_type='text/event-stream')

    save_message_to_db(session_id, "User", user_question)

    def generate():
        history_block = get_recent_history_block(session_id, 10)

        for mentor in MENTORS:
            prompt = format_prompt(
                RESPONSE_PROMPT_TEMPLATE,
                mentor=mentor,
                user_question=user_question,
                history_block=history_block
            )
            reply = call_openai_llm(prompt)
            msg = {"from": mentor, "content": reply}
            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
            save_message_to_db(session_id, mentor, reply)

        # ✅ reaction
        for mentor in MENTORS:
            if random.random() < 0.3:
                reaction_prompt = format_prompt(
                    REACTION_PROMPT_TEMPLATE,
                    mentor=mentor,
                    history_block=get_recent_history_block(session_id, 10)
                )
                reply = call_openai_llm(reaction_prompt)
                msg = {"from": mentor, "content": reply}
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
                save_message_to_db(session_id, mentor, reply)

        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), content_type='text/event-stream')

@llm_bp.route("/api/history", methods=["POST"])
def history():
    data = request.get_json()
    session_id = data.get("session_id")

    conn = get_conn()
    with conn.cursor(dictionary=True) as cursor:
        sql = """
            SELECT id, sender AS `from`, content, timestamp
            FROM chatroom_chat_messages
            WHERE session_id = %s
            ORDER BY timestamp ASC
        """
        cursor.execute(sql, (session_id,))
        rows = cursor.fetchall()

    return Response(
        json.dumps(rows, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8"
    )


@llm_bp.route("/api/mentors", methods=["GET"])
def get_mentors():
    mentor_list = [
        {"id": i + 1, "name": name}
        for i, name in enumerate(MENTORS)
    ]
    return Response(
        json.dumps(mentor_list, ensure_ascii=False, indent=2),
        content_type="application/json; charset=utf-8"
    )


@llm_bp.route("/api/sessions", methods=["POST"])
def get_user_sessions():
    data = request.get_json()
    user_id = data.get("user_id")
    print("Fetching sessions for user_id:", user_id)
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    conn = get_conn()
    with conn.cursor(dictionary=True) as cursor:
        sql = """
            SELECT session_id, session_name, created_at
            FROM chatroom_sessions
            WHERE user_id = %s
            ORDER BY created_at DESC
        """
        cursor.execute(sql, (user_id,))
        sessions = cursor.fetchall()

    return Response(
        json.dumps(sessions, ensure_ascii=False, indent=2, default=str),
        content_type="application/json; charset=utf-8"
    )


@llm_bp.route("/api/session/messages", methods=["POST"])
def get_session_messages():
    data = request.get_json()
    session_id = data.get("session_id")
    print("Fetching messages for session_id:", session_id)
    if not session_id:
        return jsonify({"error": "Missing session_id"}), 400

    conn = get_conn()
    with conn.cursor(dictionary=True) as cursor:
        sql = """
            SELECT id, sender AS `from`, content, timestamp
            FROM chatroom_chat_messages
            WHERE session_id = %s
            ORDER BY timestamp ASC
        """
        cursor.execute(sql, (session_id,))
        messages = cursor.fetchall()

    return Response(
        json.dumps(messages, ensure_ascii=False, indent=2, default=str),
        content_type="application/json; charset=utf-8"
    )
