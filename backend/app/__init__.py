import os
from flask import Flask
from flask_cors import CORS


def create_app():
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    FRONTEND_DIST = os.path.join(BASE_DIR, "fronted/dist")

    app = Flask(__name__, static_folder=FRONTEND_DIST, static_url_path="/")

    @app.route('/')
    def serve_index():
        return app.send_static_file('index.html')

    @app.route('/chat')
    def serve_index2():
        return app.send_static_file('index.html')

    @app.errorhandler(404)
    def not_found(e):
        print("出错啦",e.get_response())
        return app.send_static_file("index.html")

    CORS(app,
         resources={r"/api/*": {"origins": "*"}},
         supports_credentials=True,
         allow_headers=["Content-Type", "Authorization"],
         methods=["GET", "POST", "OPTIONS"])

    from .routes.auth_routes import auth_bp
    from .routes.llm_routes import llm_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(llm_bp)

    return app
