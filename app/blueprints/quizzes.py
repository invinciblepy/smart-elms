from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Course, Enrollment, Quiz, QuizAttempt, QuizQuestion
from app.services.engagement import recompute_course_progress
from app.services.ml import predict_for_student
from app.utils import current_identity, role_required, student_enrolled

quizzes_bp = Blueprint("quizzes", __name__)


@quizzes_bp.get("/courses/<int:course_id>/quizzes")
@jwt_required()
def list_quizzes(course_id):
    course = Course.query.get_or_404(course_id)
    ident = current_identity()
    if ident["role"] == "student" and not student_enrolled(ident["id"], course_id):
        return jsonify({"error": "You are not enrolled in this course"}), 403
    if ident["role"] == "instructor" and course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    items = []
    for q in course.quizzes:
        payload = {
            "quiz_id": q.quiz_id,
            "course_id": q.course_id,
            "course_title": course.title,
            "title": q.title,
            "question_count": len(q.questions),
        }
        if ident["role"] == "student":
            attempt = (
                QuizAttempt.query.filter_by(quiz_id=q.quiz_id, student_id=ident["id"])
                .order_by(QuizAttempt.attempted_at.desc())
                .first()
            )
            payload["attempt"] = attempt.to_dict() if attempt else None
        else:
            payload["attempt_count"] = len(q.attempts)
        items.append(payload)
    return jsonify({"quizzes": items, "course": course.to_dict()})


@quizzes_bp.post("/courses/<int:course_id>/quizzes")
@jwt_required()
@role_required("instructor")
def create_quiz(course_id):
    ident = current_identity()
    course = Course.query.get_or_404(course_id)
    if course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    questions = data.get("questions") or []
    if not title:
        return jsonify({"error": "Quiz title is required"}), 400
    if len(questions) < 1:
        return jsonify({"error": "Add at least one question"}), 400
    quiz = Quiz(course_id=course_id, title=title)
    db.session.add(quiz)
    db.session.flush()
    for q in questions:
        option = (q.get("correct_option") or "").upper()
        if option not in {"A", "B", "C", "D"}:
            db.session.rollback()
            return jsonify({"error": "Each question needs a correct option A-D"}), 400
        if not (q.get("prompt") or "").strip():
            db.session.rollback()
            return jsonify({"error": "Each question needs a prompt"}), 400
        db.session.add(
            QuizQuestion(
                quiz_id=quiz.quiz_id,
                prompt=(q.get("prompt") or "").strip(),
                option_a=q.get("option_a") or "",
                option_b=q.get("option_b") or "",
                option_c=q.get("option_c") or "",
                option_d=q.get("option_d") or "",
                correct_option=option,
            )
        )
    db.session.commit()
    return jsonify({"quiz": quiz.to_dict(include_answers=True)}), 201


@quizzes_bp.get("/quizzes/<int:quiz_id>")
@jwt_required()
def get_quiz(quiz_id):
    quiz = Quiz.query.get_or_404(quiz_id)
    ident = current_identity()
    if ident["role"] == "student" and not student_enrolled(ident["id"], quiz.course_id):
        return jsonify({"error": "You are not enrolled in this course"}), 403
    if ident["role"] == "instructor" and quiz.course.teacher_id != ident["id"]:
        return jsonify({"error": "Forbidden"}), 403
    include = ident["role"] == "instructor"
    payload = quiz.to_dict(include_answers=include)
    if ident["role"] == "student":
        attempt = (
            QuizAttempt.query.filter_by(quiz_id=quiz_id, student_id=ident["id"])
            .order_by(QuizAttempt.attempted_at.desc())
            .first()
        )
        payload["attempt"] = attempt.to_dict() if attempt else None
    return jsonify({"quiz": payload})


@quizzes_bp.post("/quizzes/<int:quiz_id>/attempt")
@jwt_required()
@role_required("student")
def attempt_quiz(quiz_id):
    ident = current_identity()
    quiz = Quiz.query.get_or_404(quiz_id)
    enrolled = Enrollment.query.filter_by(student_id=ident["id"], course_id=quiz.course_id).first()
    if not enrolled:
        return jsonify({"error": "You are not enrolled in this course"}), 403
    data = request.get_json(silent=True) or {}
    answers = data.get("answers") or {}
    if not quiz.questions:
        return jsonify({"error": "Quiz has no questions"}), 400
    correct = 0
    for q in quiz.questions:
        given = str(answers.get(str(q.question_id)) or answers.get(q.question_id) or "").upper()
        if given == q.correct_option:
            correct += 1
    score = int(round(100 * correct / len(quiz.questions)))
    attempt = QuizAttempt(quiz_id=quiz_id, student_id=ident["id"], score=score)
    db.session.add(attempt)
    db.session.commit()
    recompute_course_progress(ident["id"], quiz.course_id)
    try:
        predict_for_student(ident["id"])
    except Exception:
        pass
    return jsonify({"attempt": attempt.to_dict(), "correct": correct, "total": len(quiz.questions)}), 201


@quizzes_bp.get("/student/quizzes")
@jwt_required()
@role_required("student")
def student_quizzes():
    ident = current_identity()
    enrollments = Enrollment.query.filter_by(student_id=ident["id"]).all()
    course_ids = [e.course_id for e in enrollments]
    quizzes = Quiz.query.filter(Quiz.course_id.in_(course_ids)).all()
    items = []
    for q in quizzes:
        attempt = (
            QuizAttempt.query.filter_by(quiz_id=q.quiz_id, student_id=ident["id"])
            .order_by(QuizAttempt.attempted_at.desc())
            .first()
        )
        items.append(
            {
                "quiz_id": q.quiz_id,
                "course_id": q.course_id,
                "course_title": q.course.title,
                "title": q.title,
                "question_count": len(q.questions),
                "attempt": attempt.to_dict() if attempt else None,
            }
        )
    return jsonify({"quizzes": items})
