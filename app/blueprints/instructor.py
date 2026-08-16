from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from app.models import Assignment, Course, Enrollment, Student, Submission
from app.services.engagement import student_risk_summary
from app.utils import current_identity, role_required

instructor_bp = Blueprint("instructor", __name__)


@instructor_bp.get("/instructor/students")
@jwt_required()
@role_required("instructor")
def list_students():
    ident = current_identity()
    courses = Course.query.filter_by(teacher_id=ident["id"]).all()
    course_ids = [c.course_id for c in courses]
    seen = {}
    if course_ids:
        for e in Enrollment.query.filter(Enrollment.course_id.in_(course_ids)).all():
            seen.setdefault(e.student_id, []).append(e.course.title)
    rows = []
    for sid, titles in seen.items():
        summary = student_risk_summary(sid, course_ids)
        summary["courses"] = titles
        rows.append(summary)
    rows.sort(key=lambda r: r["full_name"])
    return jsonify({"students": rows})


@instructor_bp.get("/instructor/classes/<int:course_id>/roster")
@jwt_required()
@role_required("instructor")
def roster(course_id):
    ident = current_identity()
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    rows = []
    for e in course.enrollments:
        summary = student_risk_summary(e.student_id, [course_id])
        summary["progress_percent"] = e.progress_percent
        rows.append(summary)
    return jsonify({"course": course.to_dict(), "students": rows})
