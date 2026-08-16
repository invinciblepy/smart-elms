from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from app.extensions import db
from app.models import Student, Teacher


def current_identity():
    verify_jwt_in_request()
    claims = get_jwt()
    return {
        "id": int(get_jwt_identity()),
        "role": claims.get("role"),
        "name": claims.get("name"),
        "email": claims.get("email"),
    }


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ident = current_identity()
            if ident["role"] not in roles:
                return jsonify({"error": "Forbidden for this role"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def get_current_user():
    ident = current_identity()
    if ident["role"] == "student":
        return db.session.get(Student, ident["id"]), ident
    if ident["role"] == "instructor":
        return db.session.get(Teacher, ident["id"]), ident
    return None, ident


def days_since(dt, now=None):
    if dt is None:
        return None
    now = now or __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=__import__("datetime").timezone.utc)
    return max(0, (now - dt).days)


def risk_level_from_probability(prob, at_risk):
    if prob >= 0.7 or (at_risk and prob >= 0.55):
        return "High"
    if prob >= 0.4 or at_risk:
        return "Medium"
    return "Low"


def student_enrolled(student_id, course_id):
    from app.models import Enrollment

    return Enrollment.query.filter_by(student_id=student_id, course_id=course_id).first() is not None


def progress_status_label(percent):
    if percent >= 80:
        return "Excellent"
    if percent >= 65:
        return "On track"
    if percent >= 50:
        return "Needs attention"
    return "At risk"
