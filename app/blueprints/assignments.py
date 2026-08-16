import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from flask_jwt_extended import jwt_required
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Assignment, Course, Enrollment, Submission
from app.services.engagement import recompute_course_progress
from app.services.ml import predict_for_student
from app.utils import current_identity, role_required, student_enrolled

assignments_bp = Blueprint("assignments", __name__)


ALLOWED_MIME = {
    "pdf": {"application/pdf"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
    "txt": {"text/plain", "application/octet-stream"},
}


def _allowed(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def _mime_ok(upload, ext):
    mime = (upload.mimetype or "").split(";")[0].strip().lower()
    if not mime or mime == "application/octet-stream":
        return True
    return mime in ALLOWED_MIME.get(ext, set())


@assignments_bp.get("/courses/<int:course_id>/assignments")
@jwt_required()
def list_course_assignments(course_id):
    course = Course.query.get_or_404(course_id)
    ident = current_identity()
    if ident["role"] == "student" and not student_enrolled(ident["id"], course_id):
        return jsonify({"error": "You are not enrolled in this course"}), 403
    if ident["role"] == "instructor" and course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    items = []
    for a in course.assignments:
        payload = a.to_dict()
        if ident["role"] == "student":
            sub = Submission.query.filter_by(assignment_id=a.assignment_id, student_id=ident["id"]).first()
            payload["submission"] = sub.to_dict() if sub else None
        else:
            payload["submission_count"] = len(a.submissions)
        items.append(payload)
    return jsonify({"assignments": items, "course": course.to_dict()})


@assignments_bp.post("/courses/<int:course_id>/assignments")
@jwt_required()
@role_required("instructor")
def create_assignment(course_id):
    ident = current_identity()
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Assignment title is required"}), 400
    due = data.get("due_date")
    due_dt = datetime.fromisoformat(due.replace("Z", "+00:00")) if due else None
    assignment = Assignment(
        course_id=course_id,
        title=title,
        description=data.get("description") or "",
        due_date=due_dt,
        max_score=int(data.get("max_score") or 100),
    )
    db.session.add(assignment)
    db.session.commit()
    return jsonify({"assignment": assignment.to_dict()}), 201


@assignments_bp.get("/assignments/<int:assignment_id>")
@jwt_required()
def get_assignment(assignment_id):
    assignment = Assignment.query.get_or_404(assignment_id)
    ident = current_identity()
    payload = assignment.to_dict()
    if ident["role"] == "student":
        if not student_enrolled(ident["id"], assignment.course_id):
            return jsonify({"error": "You are not enrolled in this course"}), 403
        sub = Submission.query.filter_by(assignment_id=assignment_id, student_id=ident["id"]).first()
        payload["submission"] = sub.to_dict() if sub else None
    else:
        if assignment.course.teacher_id != ident["id"]:
            return jsonify({"error": "Forbidden"}), 403
        payload["submissions"] = [s.to_dict() for s in assignment.submissions]
    return jsonify({"assignment": payload})


@assignments_bp.post("/assignments/<int:assignment_id>/submit")
@jwt_required()
@role_required("student")
def submit_assignment(assignment_id):
    ident = current_identity()
    assignment = Assignment.query.get_or_404(assignment_id)
    enrolled = Enrollment.query.filter_by(student_id=ident["id"], course_id=assignment.course_id).first()
    if not enrolled:
        return jsonify({"error": "You are not enrolled in this course"}), 403

    comment = request.form.get("comment") or ""
    file_path = None
    upload = request.files.get("file")
    if upload and upload.filename:
        if not _allowed(upload.filename):
            return jsonify({"error": "Only PDF, DOCX or TXT files are allowed"}), 400
        original = secure_filename(upload.filename)
        ext = original.rsplit(".", 1)[-1].lower()
        if not _mime_ok(upload, ext):
            return jsonify({"error": "The file type does not match a PDF, DOCX or TXT upload"}), 400
        stored = f"{uuid.uuid4().hex}.{ext}"
        dest = Path(current_app.config["UPLOAD_FOLDER"]) / stored
        dest.parent.mkdir(parents=True, exist_ok=True)
        upload.save(dest)
        file_path = stored
    elif not comment.strip():
        return jsonify({"error": "Add a written answer or upload a file"}), 400

    existing = Submission.query.filter_by(assignment_id=assignment_id, student_id=ident["id"]).first()
    if existing:
        existing.comment = comment
        existing.submitted_at = datetime.now(timezone.utc)
        if file_path:
            existing.file_path = file_path
        submission = existing
    else:
        submission = Submission(
            assignment_id=assignment_id,
            student_id=ident["id"],
            comment=comment,
            file_path=file_path,
        )
        db.session.add(submission)
    db.session.commit()
    recompute_course_progress(ident["id"], assignment.course_id)
    try:
        predict_for_student(ident["id"])
    except Exception:
        pass
    return jsonify({"submission": submission.to_dict(), "message": "Assignment submitted"}), 201


@assignments_bp.put("/submissions/<int:submission_id>/score")
@jwt_required()
@role_required("instructor")
def score_submission(submission_id):
    ident = current_identity()
    submission = Submission.query.get_or_404(submission_id)
    if submission.assignment.course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    try:
        score = int(data.get("score"))
    except (TypeError, ValueError):
        return jsonify({"error": "Score must be an integer"}), 400
    max_score = submission.assignment.max_score or 100
    if score < 0 or score > max_score:
        return jsonify({"error": f"Score must be between 0 and {max_score}"}), 400
    submission.score = score
    db.session.commit()
    recompute_course_progress(submission.student_id, submission.assignment.course_id)
    try:
        predict_for_student(submission.student_id)
    except Exception:
        pass
    return jsonify({"submission": submission.to_dict()})


@assignments_bp.get("/student/assignments")
@jwt_required()
@role_required("student")
def student_assignments():
    ident = current_identity()
    enrollments = Enrollment.query.filter_by(student_id=ident["id"]).all()
    course_ids = [e.course_id for e in enrollments]
    assignments = Assignment.query.filter(Assignment.course_id.in_(course_ids)).order_by(Assignment.due_date).all()
    items = []
    now = datetime.now(timezone.utc)
    for a in assignments:
        payload = a.to_dict()
        sub = Submission.query.filter_by(assignment_id=a.assignment_id, student_id=ident["id"]).first()
        payload["submission"] = sub.to_dict() if sub else None
        due = a.due_date
        if due and due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        payload["is_overdue"] = bool(due and due < now and not sub)
        items.append(payload)
    return jsonify({"assignments": items})


@assignments_bp.get("/student/grades")
@jwt_required()
@role_required("student")
def student_grades():
    ident = current_identity()
    submissions = Submission.query.filter_by(student_id=ident["id"]).all()
    quiz_from = __import__("app.models", fromlist=["QuizAttempt"]).QuizAttempt
    attempts = quiz_from.query.filter_by(student_id=ident["id"]).all()
    return jsonify(
        {
            "assignments": [s.to_dict() for s in submissions],
            "quizzes": [a.to_dict() for a in attempts],
        }
    )


@assignments_bp.get("/uploads/<path:filename>")
@jwt_required()
def download_upload(filename):
    ident = current_identity()
    sub = Submission.query.filter_by(file_path=filename).first()
    if not sub:
        return jsonify({"error": "File not found"}), 404
    if ident["role"] == "student" and sub.student_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    if ident["role"] == "instructor" and sub.assignment.course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename, as_attachment=True)
