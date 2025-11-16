from flask import Blueprint, request, jsonify
import sqlite3
import os

user_bp = Blueprint("user", __name__, url_prefix="/api")
DB_PATH = "instance/database.db"

@user_bp.route("/user", methods=["GET"])
def get_user():
    email = request.args.get("email")
    if not email:
        return jsonify({"status": "error", "message": "Email required"}), 400

    try:
        if not os.path.exists(DB_PATH):
            return jsonify({"status": "error", "message": "Database not found"}), 500

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT first_name, last_name FROM users WHERE email=?",
            (email,)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            name = f"{user[0]} {user[1]}".strip()
            return jsonify({"status": "success", "name": name}), 200
        else:
            return jsonify({"status": "error", "message": "User not found"}), 404

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
