from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Course, Enrollment, Prediction, Student
from app.services.ml import FEATURES, predict_features, predict_for_student
from app.utils import current_identity, role_required

predict_bp = Blueprint("predict", __name__)


@predict_bp.post("/predict")
@jwt_required()
def predict():
    data = request.get_json(silent=True) or {}
    if data.get("student_id") is not None:
        ident = current_identity()
        student_id = int(data["student_id"])
        if ident["role"] == "student" and ident["id"] != student_id:
            return jsonify({"error": "Forbidden"}), 403
        try:
            pred = predict_for_student(student_id)
        except FileNotFoundError:
            return jsonify({"error": "Prediction model is not trained yet"}), 503
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(pred)

    payload = {}
    missing = []
    for name, lo, hi in FEATURES:
        if name not in data:
            missing.append(name)
            continue
        try:
            value = float(data[name])
        except (TypeError, ValueError):
            return jsonify({"error": f"{name} must be numeric"}), 400
        if value < lo or value > hi:
            return jsonify({"error": f"{name} must be between {lo} and {hi}"}), 400
        payload[name] = value
    if missing:
        return jsonify({"error": f"Missing features: {', '.join(missing)}"}), 400
    try:
        result = predict_features(payload)
    except FileNotFoundError:
        return jsonify({"error": "Prediction model is not trained yet"}), 503
    return jsonify(result)


@predict_bp.post("/predict/refresh/<int:student_id>")
@jwt_required()
@role_required("instructor")
def refresh(student_id):
    Student.query.get_or_404(student_id)
    try:
        pred = predict_for_student(student_id)
    except FileNotFoundError:
        return jsonify({"error": "Prediction model is not trained yet"}), 503
    return jsonify(pred)


@predict_bp.get("/predict/students")
@jwt_required()
@role_required("instructor")
def all_predictions():
    ident = current_identity()
    course_ids = [c.course_id for c in Course.query.filter_by(teacher_id=ident["id"]).all()]
    student_ids = {
        e.student_id for e in Enrollment.query.filter(Enrollment.course_id.in_(course_ids)).all()
    } if course_ids else set()
    rows = []
    for sid in student_ids:
        pred = (
            Prediction.query.filter_by(student_id=sid)
            .order_by(Prediction.created_at.desc())
            .first()
        )
        student = db.session.get(Student, sid)
        rows.append(
            {
                "student_id": sid,
                "full_name": student.full_name if student else "",
                "prediction": pred.to_dict() if pred else None,
            }
        )
    return jsonify({"predictions": rows})
