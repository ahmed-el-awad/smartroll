from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from models import db
from routes.auth_routes import auth_bp
from routes.session_routes import session_bp
from routes.attendance_routes import attendance_bp
from routes.classroom_routes import classroom_bp
from routes.login_routes import login_bp
from routes.signup_routes import signup_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app)
    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(auth_bp)
    app.register_blueprint(session_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(classroom_bp)
    app.register_blueprint(login_bp)
    app.register_blueprint(signup_bp)


    @app.route("/")
    def home():
        return jsonify({"message": "SmartRoll backend running"})

    return app


if __name__ == "__main__":
    app = create_app()
    # 0.0.0.0 lets phones on same Wi-Fi reach your laptop server
    app.run(host="0.0.0.0", port=5001)
