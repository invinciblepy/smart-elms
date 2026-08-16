import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "smart-elms-dev-secret-change-me")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "smart-elms-jwt-secret-change-me-32b")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)
    JWT_TOKEN_LOCATION = ["headers"]

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'smart_elms.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = BASE_DIR / "uploads"
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}

    FRONTEND_FOLDER = BASE_DIR / "frontend"
    CHART_FOLDER = BASE_DIR / "instance" / "charts"
    AI_MODEL_PATH = BASE_DIR / "ai" / "models" / "best_model.pkl"
    AI_DATA_PATH = BASE_DIR / "ai" / "data" / "synthetic_students.csv"
    AI_ARTEFACT_FOLDER = BASE_DIR / "ai" / "artefacts"


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET_KEY = "test-jwt-secret-key-32-bytes-ok!!"
    SECRET_KEY = "test-secret-key-32-bytes-long!!"
    WTF_CSRF_ENABLED = False
