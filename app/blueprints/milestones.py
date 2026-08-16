from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Course, Milestone
from app.services.engagement import milestone_completion_rate
from app.utils import current_identity, role_required, student_enrolled

milestones_bp = Blueprint("milestones", __name__)


@milestones_bp.get("/milestones")
@jwt_required()
@role_required("instructor")
def list_all():
    ident = current_identity()
    courses = Course.query.filter_by(teacher_id=ident["id"]).all()
    rows = []
    for course in courses:
        for m in course.milestones:
            rate, completed, enrolled = milestone_completion_rate(m)
            rows.append(m.to_dict(extra={"completion_rate": rate, "completed": completed, "enrolled": enrolled}))
    return jsonify({"milestones": rows})


@milestones_bp.get("/courses/<int:course_id>/milestones")
@jwt_required()
def list_course(course_id):
    course = Course.query.get_or_404(course_id)
    ident = current_identity()
    if ident["role"] == "student" and not student_enrolled(ident["id"], course_id):
        return jsonify({"error": "You are not enrolled in this course"}), 403
    if ident["role"] == "instructor" and course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    rows = []
    for m in course.milestones:
        rate, completed, enrolled = milestone_completion_rate(m)
        rows.append(m.to_dict(extra={"completion_rate": rate, "completed": completed, "enrolled": enrolled}))
    return jsonify({"milestones": rows, "course": course.to_dict()})


@milestones_bp.post("/courses/<int:course_id>/milestones")
@jwt_required()
@role_required("instructor")
def create_milestone(course_id):
    ident = current_identity()
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Milestone title is required"}), 400
    due = data.get("due_date")
    due_dt = datetime.fromisoformat(due.replace("Z", "+00:00")) if due else None
    milestone = Milestone(
        course_id=course_id,
        title=title,
        description=data.get("description") or "",
        due_date=due_dt,
        requirement_type=data.get("requirement_type") or "manual",
        requirement_ref_id=data.get("requirement_ref_id"),
    )
    db.session.add(milestone)
    db.session.commit()
    rate, completed, enrolled = milestone_completion_rate(milestone)
    return jsonify({"milestone": milestone.to_dict(extra={"completion_rate": rate, "completed": completed, "enrolled": enrolled})}), 201


@milestones_bp.put("/milestones/<int:milestone_id>")
@jwt_required()
@role_required("instructor")
def update_milestone(milestone_id):
    ident = current_identity()
    milestone = Milestone.query.get_or_404(milestone_id)
    if milestone.course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    if data.get("title"):
        milestone.title = data["title"].strip()
    if "description" in data:
        milestone.description = data["description"]
    if data.get("due_date"):
        milestone.due_date = datetime.fromisoformat(data["due_date"].replace("Z", "+00:00"))
    if data.get("requirement_type"):
        milestone.requirement_type = data["requirement_type"]
    if "requirement_ref_id" in data:
        milestone.requirement_ref_id = data["requirement_ref_id"]
    db.session.commit()
    rate, completed, enrolled = milestone_completion_rate(milestone)
    return jsonify({"milestone": milestone.to_dict(extra={"completion_rate": rate, "completed": completed, "enrolled": enrolled})})


@milestones_bp.delete("/milestones/<int:milestone_id>")
@jwt_required()
@role_required("instructor")
def delete_milestone(milestone_id):
    ident = current_identity()
    milestone = Milestone.query.get_or_404(milestone_id)
    if milestone.course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(milestone)
    db.session.commit()
    return jsonify({"message": "Milestone deleted"})
