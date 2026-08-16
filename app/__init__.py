from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from config import Config
from app.extensions import db, bcrypt, jwt


def create_app(config_class=Config):
    app = Flask(
        __name__,
        static_folder=str(config_class.FRONTEND_FOLDER),
        static_url_path="/assets",
        instance_relative_config=True,
    )
    app.config.from_object(config_class)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["CHART_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(config_class.AI_ARTEFACT_FOLDER).mkdir(parents=True, exist_ok=True)
    Path(config_class.AI_DATA_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(config_class.AI_MODEL_PATH).parent.mkdir(parents=True, exist_ok=True)
    (Path(app.instance_path)).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)

    @jwt.unauthorized_loader
    def _missing_token(_reason):
        return jsonify({"error": "Unauthorised"}), 401

    @jwt.invalid_token_loader
    def _invalid_token(_reason):
        return jsonify({"error": "Unauthorised"}), 401

    @jwt.expired_token_loader
    def _expired_token(_header, _payload):
        return jsonify({"error": "Session expired. Please sign in again."}), 401

    from app import models  # noqa: F401
    from app.blueprints.auth import auth_bp
    from app.blueprints.courses import courses_bp
    from app.blueprints.assignments import assignments_bp
    from app.blueprints.quizzes import quizzes_bp
    from app.blueprints.analytics import analytics_bp
    from app.blueprints.predict import predict_bp
    from app.blueprints.pages import pages_bp
    from app.blueprints.milestones import milestones_bp
    from app.blueprints.instructor import instructor_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(courses_bp, url_prefix="/api")
    app.register_blueprint(assignments_bp, url_prefix="/api")
    app.register_blueprint(quizzes_bp, url_prefix="/api")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(predict_bp, url_prefix="/api")
    app.register_blueprint(milestones_bp, url_prefix="/api")
    app.register_blueprint(instructor_bp, url_prefix="/api")
    app.register_blueprint(pages_bp)

    @app.get("/health")
    def health():
        return {"status": "ok", "app": "Smart ELMS"}

    @app.errorhandler(400)
    def bad_request(err):
        return {"error": getattr(err, "description", "Bad request")}, 400

    @app.errorhandler(401)
    def unauthorized(err):
        return {"error": "Unauthorised"}, 401

    @app.errorhandler(403)
    def forbidden(err):
        return {"error": "Forbidden"}, 403

    @app.errorhandler(404)
    def not_found(err):
        # Serve SPA-style HTML 404 only for non-API routes
        return {"error": "Not found"}, 404

    @app.errorhandler(413)
    def too_large(err):
        return {"error": "File exceeds the 10 MB limit"}, 413

    return app
