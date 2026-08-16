from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Course, Enrollment, Module, ModuleEngagement, Student
from app.services.engagement import recompute_course_progress
from app.utils import current_identity, get_current_user, progress_status_label, role_required, student_enrolled

courses_bp = Blueprint("courses", __name__)


def _student_course_payload(course, student_id):
    enrollment = Enrollment.query.filter_by(student_id=student_id, course_id=course.course_id).first()
    progress = enrollment.progress_percent if enrollment else 0
    return course.to_dict(
        extra={
            "enrolled": enrollment is not None,
            "progress_percent": progress,
            "status_label": progress_status_label(progress) if enrollment else "Not enrolled",
        }
    )


@courses_bp.get("/courses")
@jwt_required()
def list_courses():
    ident = current_identity()
    if ident["role"] == "instructor":
        courses = Course.query.filter_by(teacher_id=ident["id"]).order_by(Course.title).all()
        payload = []
        for c in courses:
            payload.append(
                c.to_dict(
                    extra={
                        "enrolled_count": len(c.enrollments),
                        "assignment_count": len(c.assignments),
                    }
                )
            )
        return jsonify({"courses": payload})

    courses = Course.query.order_by(Course.title).all()
    return jsonify({"courses": [_student_course_payload(c, ident["id"]) for c in courses]})


@courses_bp.post("/courses")
@jwt_required()
@role_required("instructor")
def create_course():
    ident = current_identity()
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Course title is required"}), 400
    course = Course(
        title=title,
        description=(data.get("description") or "").strip(),
        teacher_id=ident["id"],
    )
    db.session.add(course)
    db.session.commit()
    return jsonify({"course": course.to_dict()}), 201


@courses_bp.get("/courses/<int:course_id>")
@jwt_required()
def get_course(course_id):
    course = Course.query.get_or_404(course_id)
    ident = current_identity()
    if ident["role"] == "instructor":
        if course.teacher_id != ident["id"]:
            return jsonify({"error": "Forbidden"}), 403
        return jsonify({"course": course.to_dict(extra={"enrolled_count": len(course.enrollments)})})
    return jsonify({"course": _student_course_payload(course, ident["id"])})


@courses_bp.put("/courses/<int:course_id>")
@jwt_required()
@role_required("instructor")
def update_course(course_id):
    ident = current_identity()
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    if data.get("title"):
        course.title = data["title"].strip()
    if "description" in data:
        course.description = data["description"]
    db.session.commit()
    return jsonify({"course": course.to_dict()})


@courses_bp.delete("/courses/<int:course_id>")
@jwt_required()
@role_required("instructor")
def delete_course(course_id):
    ident = current_identity()
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(course)
    db.session.commit()
    return jsonify({"message": "Course deleted"})


@courses_bp.post("/courses/<int:course_id>/enroll")
@jwt_required()
@role_required("student")
def enroll(course_id):
    ident = current_identity()
    course = Course.query.get_or_404(course_id)
    existing = Enrollment.query.filter_by(student_id=ident["id"], course_id=course_id).first()
    if existing:
        return jsonify({"error": "Already enrolled"}), 400
    db.session.add(Enrollment(student_id=ident["id"], course_id=course_id, progress_percent=0))
    db.session.commit()
    return jsonify({"course": _student_course_payload(course, ident["id"])}), 201


@courses_bp.get("/courses/<int:course_id>/modules")
@jwt_required()
def list_modules(course_id):
    course = Course.query.get_or_404(course_id)
    ident = current_identity()
    if ident["role"] == "student" and not student_enrolled(ident["id"], course_id):
        return jsonify({"error": "You are not enrolled in this course"}), 403
    if ident["role"] == "instructor" and course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    modules = []
    for m in course.modules:
        status = "Not started"
        time_spent = 0
        if ident["role"] == "student":
            eng = ModuleEngagement.query.filter_by(student_id=ident["id"], module_id=m.module_id).first()
            if eng:
                time_spent = eng.time_spent_minutes or 0
                status = "Completed" if eng.completed else "In progress"
        modules.append(m.to_dict(status=status, time_spent=time_spent))
    progress = 0
    if ident["role"] == "student":
        enr = Enrollment.query.filter_by(student_id=ident["id"], course_id=course_id).first()
        progress = enr.progress_percent if enr else 0
    return jsonify(
        {
            "course": course.to_dict(),
            "modules": modules,
            "progress_percent": progress,
        }
    )


@courses_bp.post("/courses/<int:course_id>/modules")
@jwt_required()
@role_required("instructor")
def create_module(course_id):
    ident = current_identity()
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Module title is required"}), 400
    next_index = (max([m.order_index for m in course.modules], default=0) + 1)
    module = Module(
        course_id=course_id,
        title=title,
        content=(data.get("content") or "").strip(),
        order_index=data.get("order_index") or next_index,
    )
    db.session.add(module)
    db.session.commit()
    return jsonify({"module": module.to_dict()}), 201


@courses_bp.get("/modules/<int:module_id>")
@jwt_required()
def get_module(module_id):
    module = Module.query.get_or_404(module_id)
    ident = current_identity()
    if ident["role"] == "student" and not student_enrolled(ident["id"], module.course_id):
        return jsonify({"error": "You are not enrolled in this course"}), 403
    if ident["role"] == "instructor" and module.course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    status = None
    time_spent = 0
    if ident["role"] == "student":
        eng = ModuleEngagement.query.filter_by(student_id=ident["id"], module_id=module_id).first()
        if eng:
            time_spent = eng.time_spent_minutes or 0
            status = "Completed" if eng.completed else "In progress"
        else:
            status = "Not started"
    return jsonify(
        {
            "module": module.to_dict(status=status, time_spent=time_spent),
            "course": module.course.to_dict(),
        }
    )


@courses_bp.put("/modules/<int:module_id>")
@jwt_required()
@role_required("instructor")
def update_module(module_id):
    ident = current_identity()
    module = Module.query.get_or_404(module_id)
    if module.course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    if data.get("title"):
        module.title = data["title"].strip()
    if "content" in data:
        module.content = data["content"]
    if data.get("order_index") is not None:
        module.order_index = int(data["order_index"])
    db.session.commit()
    return jsonify({"module": module.to_dict()})


@courses_bp.delete("/modules/<int:module_id>")
@jwt_required()
@role_required("instructor")
def delete_module(module_id):
    ident = current_identity()
    module = Module.query.get_or_404(module_id)
    if module.course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    course_id = module.course_id
    db.session.delete(module)
    db.session.commit()
    for enrollment in Enrollment.query.filter_by(course_id=course_id).all():
        recompute_course_progress(enrollment.student_id, course_id)
    return jsonify({"message": "Module deleted"})


@courses_bp.post("/modules/<int:module_id>/access")
@jwt_required()
@role_required("student")
def record_access(module_id):
    ident = current_identity()
    module = Module.query.get_or_404(module_id)
    if not student_enrolled(ident["id"], module.course_id):
        return jsonify({"error": "You are not enrolled in this course"}), 403
    minutes = int(request.get_json(silent=True).get("minutes") or 1) if request.get_json(silent=True) else 1
    minutes = max(1, min(minutes, 120))
    eng = ModuleEngagement.query.filter_by(student_id=ident["id"], module_id=module_id).first()
    if not eng:
        eng = ModuleEngagement(
            student_id=ident["id"],
            module_id=module_id,
            time_spent_minutes=0,
            completed=False,
        )
        db.session.add(eng)
    eng.time_spent_minutes = (eng.time_spent_minutes or 0) + minutes
    eng.last_accessed = datetime.now(timezone.utc)
    db.session.commit()
    recompute_course_progress(ident["id"], module.course_id)
    return jsonify({"module": module.to_dict(status="Completed" if eng.completed else "In progress", time_spent=eng.time_spent_minutes)})


@courses_bp.post("/modules/<int:module_id>/complete")
@jwt_required()
@role_required("student")
def complete_module(module_id):
    ident = current_identity()
    module = Module.query.get_or_404(module_id)
    if not student_enrolled(ident["id"], module.course_id):
        return jsonify({"error": "You are not enrolled in this course"}), 403
    eng = ModuleEngagement.query.filter_by(student_id=ident["id"], module_id=module_id).first()
    if not eng:
        eng = ModuleEngagement(student_id=ident["id"], module_id=module_id, time_spent_minutes=1)
        db.session.add(eng)
    eng.completed = True
    eng.last_accessed = datetime.now(timezone.utc)
    db.session.commit()
    progress = recompute_course_progress(ident["id"], module.course_id)
    return jsonify({"module": module.to_dict(status="Completed", time_spent=eng.time_spent_minutes), "progress_percent": progress})
