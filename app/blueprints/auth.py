import re
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, jwt_required

from app.extensions import bcrypt, db
from app.models import LoginActivity, Student, Teacher
from app.utils import current_identity

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_credentials(data, require_name=False, require_role=False):
    errors = []
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    full_name = (data.get("full_name") or "").strip()
    role = (data.get("role") or "").strip().lower()

    if require_name and len(full_name) < 2:
        errors.append("Full name is required")
    if not EMAIL_RE.match(email):
        errors.append("Enter a valid email address")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters")
    if require_role and role not in {"student", "instructor"}:
        errors.append("Role must be student or instructor")
    return errors, email, password, full_name, role


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    errors, email, password, full_name, role = _validate_credentials(
        data, require_name=True, require_role=True
    )
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    if Student.query.filter_by(email=email).first() or Teacher.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists"}), 400

    password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    if role == "student":
        user = Student(full_name=full_name, email=email, password_hash=password_hash)
    else:
        user = Teacher(full_name=full_name, email=email, password_hash=password_hash)
    db.session.add(user)
    db.session.commit()

    user_id = user.student_id if role == "student" else user.teacher_id
    token = create_access_token(
        identity=str(user_id),
        additional_claims={"role": role, "name": full_name, "email": email},
    )
    return jsonify({"access_token": token, "user": user.to_public()}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    errors, email, password, _, _ = _validate_credentials(data)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    role = None
    user = Student.query.filter_by(email=email).first()
    if user:
        role = "student"
    else:
        user = Teacher.query.filter_by(email=email).first()
        if user:
            role = "instructor"

    if not user or not bcrypt.check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password"}), 401

    now = datetime.now(timezone.utc)
    if role == "student":
        user.last_login_at = now
        db.session.add(
            LoginActivity(student_id=user.student_id, login_time=now)
        )
        user_id = user.student_id
    else:
        user_id = user.teacher_id

    db.session.commit()
    if role == "student":
        try:
            from app.services.ml import predict_for_student

            predict_for_student(user.student_id)
        except Exception:
            pass
    remember = bool(data.get("remember"))
    expires = timedelta(days=14) if remember else timedelta(hours=24)
    token = create_access_token(
        identity=str(user_id),
        additional_claims={"role": role, "name": user.full_name, "email": user.email},
        expires_delta=expires,
    )
    return jsonify({"access_token": token, "user": user.to_public()})


@auth_bp.post("/forgot-password")
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not EMAIL_RE.match(email):
        return jsonify({"error": "Enter a valid email address"}), 400
    exists = Student.query.filter_by(email=email).first() or Teacher.query.filter_by(email=email).first()
    message = (
        "If that email is registered, check with your course instructor. "
        "Demonstration accounts use Password123!"
    )
    if exists:
        return jsonify({"message": message, "demo_hint": True})
    return jsonify({"message": message, "demo_hint": False})


@auth_bp.post("/logout")
@jwt_required()
def logout():
    ident = current_identity()
    if ident["role"] == "student":
        open_session = (
            LoginActivity.query.filter_by(student_id=ident["id"], logout_time=None)
            .order_by(LoginActivity.login_time.desc())
            .first()
        )
        if open_session:
            now = datetime.now(timezone.utc)
            login_time = open_session.login_time
            if login_time.tzinfo is None:
                login_time = login_time.replace(tzinfo=timezone.utc)
            open_session.logout_time = now
            open_session.duration_minutes = max(1, int((now - login_time).total_seconds() / 60))
            db.session.commit()
    return jsonify({"message": "Logged out"})


@auth_bp.get("/me")
@jwt_required()
def me():
    user, ident = __import__("app.utils", fromlist=["get_current_user"]).get_current_user()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": user.to_public()})
