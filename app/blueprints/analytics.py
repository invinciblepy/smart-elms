from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, current_app, jsonify, send_file
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import (
    Assignment,
    Course,
    Enrollment,
    LoginActivity,
    Milestone,
    Module,
    ModuleEngagement,
    Prediction,
    Quiz,
    QuizAttempt,
    Student,
    Submission,
)
from app.services.charts import generate_all_charts
from app.services.engagement import (
    days_since_last_login,
    deadline_alerts_for_courses,
    performance_alerts_for_courses,
    student_features,
    student_risk_summary,
)
from app.utils import current_identity, progress_status_label, role_required

analytics_bp = Blueprint("analytics", __name__)


@analytics_bp.get("/dashboard/student")
@jwt_required()
@role_required("student")
def student_dashboard():
    ident = current_identity()
    student = Student.query.get_or_404(ident["id"])
    enrollments = Enrollment.query.filter_by(student_id=student.student_id).all()
    course_ids = [e.course_id for e in enrollments]
    assignments = Assignment.query.filter(Assignment.course_id.in_(course_ids)).all() if course_ids else []
    now = datetime.now(timezone.utc)
    due_soon = 0
    due_assignments = []
    for a in assignments:
        due = a.due_date
        if not due:
            continue
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        submitted = Submission.query.filter_by(assignment_id=a.assignment_id, student_id=student.student_id).first()
        days_left = (due - now).days
        if not submitted and 0 <= days_left <= 7:
            due_soon += 1
            due_assignments.append(
                {
                    "assignment_id": a.assignment_id,
                    "title": a.title,
                    "course_title": a.course.title if a.course else "",
                    "due_date": due.isoformat(),
                    "days": days_left,
                }
            )
    due_assignments.sort(key=lambda row: row["days"])

    avg_progress = 0
    if enrollments:
        avg_progress = int(round(sum(e.progress_percent or 0 for e in enrollments) / len(enrollments)))

    logins = LoginActivity.query.filter_by(student_id=student.student_id).count()
    prediction = (
        Prediction.query.filter_by(student_id=student.student_id)
        .order_by(Prediction.created_at.desc())
        .first()
    )

    courses = []
    for e in enrollments:
        courses.append(
            e.course.to_dict(
                extra={
                    "enrolled": True,
                    "progress_percent": e.progress_percent,
                    "status_label": progress_status_label(e.progress_percent or 0),
                }
            )
        )

    banner = None
    weakest = min((c.get("progress_percent") or 0) for c in courses) if courses else 100
    ai_risk = bool(prediction and (prediction.at_risk or prediction.risk_level in {"High", "Medium"}))
    if ai_risk:
        banner = {
            "title": "Friendly reminder from Smart ELMS AI",
            "message": "Your recent activity suggests you might benefit from extra support. Helpful resources are available when you need them.",
            "risk_level": prediction.risk_level,
        }
    elif weakest < 55:
        banner = {
            "title": "Keep your progress moving",
            "message": "One of your courses is still below halfway. Open Support if you want a study plan or a conversation with your instructor.",
            "risk_level": "Low",
        }

    return jsonify(
        {
            "stats": {
                "courses_enrolled": len(enrollments),
                "avg_progress": avg_progress,
                "assignments_due": due_soon,
                "days_active": logins,
            },
            "courses": courses,
            "due_assignments": due_assignments,
            "ai_banner": banner,
            "prediction": prediction.to_dict() if prediction else None,
        }
    )


@analytics_bp.get("/dashboard/instructor")
@jwt_required()
@role_required("instructor")
def instructor_dashboard():
    ident = current_identity()
    courses = Course.query.filter_by(teacher_id=ident["id"]).all()
    course_ids = [c.course_id for c in courses]
    student_ids = {
        e.student_id
        for e in Enrollment.query.filter(Enrollment.course_id.in_(course_ids)).all()
    } if course_ids else set()

    enrollments = Enrollment.query.filter(Enrollment.course_id.in_(course_ids)).all() if course_ids else []
    avg_engagement = 0
    if enrollments:
        avg_engagement = int(round(sum(e.progress_percent or 0 for e in enrollments) / len(enrollments)))

    assignments = Assignment.query.filter(Assignment.course_id.in_(course_ids)).all() if course_ids else []
    now = datetime.now(timezone.utc)
    due_soon = 0
    for a in assignments:
        due = a.due_date
        if not due:
            continue
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        if 0 <= (due - now).days <= 7:
            due_soon += 1

    attention = []
    at_risk_count = 0
    for sid in student_ids:
        summary = student_risk_summary(sid, course_ids)
        if summary["risk_level"] in {"High", "Medium"} or summary["days_since_login"] >= 4:
            attention.append(summary)
        if summary["risk_level"] == "High":
            at_risk_count += 1
    attention.sort(key=lambda s: ({"High": 0, "Medium": 1, "Low": 2}.get(s["risk_level"], 3), -s["days_since_login"]))

    return jsonify(
        {
            "stats": {
                "total_students": len(student_ids),
                "avg_engagement": avg_engagement,
                "at_risk_students": at_risk_count,
                "assignments_due": due_soon,
            },
            "students_needing_attention": attention[:12],
            "deadline_alerts": deadline_alerts_for_courses(courses),
            "performance_alerts": performance_alerts_for_courses(courses)[:12],
        }
    )


@analytics_bp.get("/completions")
@jwt_required()
@role_required("instructor")
def completions():
    ident = current_identity()
    courses = Course.query.filter_by(teacher_id=ident["id"]).all()
    rows = []
    for course in courses:
        enrolled = len(course.enrollments)
        for assignment in course.assignments:
            submitted = len(assignment.submissions)
            on_time = 0
            late = 0
            for s in assignment.submissions:
                due = assignment.due_date
                submitted_at = s.submitted_at
                if due and submitted_at:
                    if due.tzinfo is None:
                        due = due.replace(tzinfo=timezone.utc)
                    if submitted_at.tzinfo is None:
                        submitted_at = submitted_at.replace(tzinfo=timezone.utc)
                    if submitted_at <= due:
                        on_time += 1
                    else:
                        late += 1
                else:
                    on_time += 1
            rows.append(
                {
                    "course": course.title,
                    "assignment": assignment.title,
                    "enrolled": enrolled,
                    "submitted": submitted,
                    "on_time": on_time,
                    "late": late,
                    "completion_rate": round(100 * submitted / enrolled, 1) if enrolled else 0,
                }
            )
    return jsonify({"completions": rows})


@analytics_bp.get("/quiz-scores")
@jwt_required()
@role_required("instructor")
def quiz_scores():
    ident = current_identity()
    courses = Course.query.filter_by(teacher_id=ident["id"]).all()
    rows = []
    for course in courses:
        for quiz in course.quizzes:
            scores = [a.score for a in quiz.attempts]
            rows.append(
                {
                    "course": course.title,
                    "quiz": quiz.title,
                    "attempts": len(scores),
                    "average": round(sum(scores) / len(scores), 1) if scores else 0,
                    "scores": scores,
                }
            )
    return jsonify({"quizzes": rows})


@analytics_bp.get("/logins")
@jwt_required()
@role_required("instructor")
def logins():
    ident = current_identity()
    courses = Course.query.filter_by(teacher_id=ident["id"]).all()
    course_ids = [c.course_id for c in courses]
    student_ids = {
        e.student_id for e in Enrollment.query.filter(Enrollment.course_id.in_(course_ids)).all()
    } if course_ids else set()
    rows = []
    for sid in student_ids:
        student = db.session.get(Student, sid)
        activities = LoginActivity.query.filter_by(student_id=sid).all()
        rows.append(
            {
                "student_id": sid,
                "full_name": student.full_name if student else "",
                "login_count": len(activities),
                "days_since_last_login": days_since_last_login(sid),
                "total_minutes": sum(a.duration_minutes or 0 for a in activities),
                "logins": [
                    {
                        "login_time": a.login_time.isoformat() if a.login_time else None,
                        "duration_minutes": a.duration_minutes,
                    }
                    for a in activities
                ],
            }
        )
    return jsonify({"students": rows})


@analytics_bp.get("/students/<int:student_id>")
@jwt_required()
@role_required("instructor")
def student_profile(student_id):
    ident = current_identity()
    student = Student.query.get_or_404(student_id)
    teacher_course_ids = {c.course_id for c in Course.query.filter_by(teacher_id=ident["id"]).all()}
    enrollments = [e for e in student.enrollments if e.course_id in teacher_course_ids]
    if not enrollments:
        return jsonify({"error": "Student is not in your classes"}), 403

    courses = []
    for e in enrollments:
        modules = []
        for m in e.course.modules:
            eng = ModuleEngagement.query.filter_by(student_id=student_id, module_id=m.module_id).first()
            modules.append(
                {
                    "title": m.title,
                    "completed": bool(eng and eng.completed),
                    "time_spent_minutes": eng.time_spent_minutes if eng else 0,
                }
            )
        courses.append(
            {
                "course_id": e.course_id,
                "title": e.course.title,
                "progress_percent": e.progress_percent,
                "status_label": progress_status_label(e.progress_percent or 0),
                "modules": modules,
            }
        )

    submissions = [
        s.to_dict()
        for s in student.submissions
        if s.assignment.course_id in teacher_course_ids
    ]
    attempts = [
        a.to_dict()
        for a in QuizAttempt.query.filter_by(student_id=student_id).all()
        if a.quiz.course_id in teacher_course_ids
    ]
    prediction = (
        Prediction.query.filter_by(student_id=student_id).order_by(Prediction.created_at.desc()).first()
    )
    features = student_features(student_id)
    return jsonify(
        {
            "student": student.to_public(),
            "courses": courses,
            "submissions": submissions,
            "quiz_attempts": attempts,
            "features": features,
            "prediction": prediction.to_dict() if prediction else None,
            "days_since_last_login": days_since_last_login(student_id),
        }
    )


@analytics_bp.get("/milestones")
@jwt_required()
@role_required("instructor")
def milestones_analytics():
    from app.services.engagement import milestone_completion_rate

    ident = current_identity()
    courses = Course.query.filter_by(teacher_id=ident["id"]).all()
    rows = []
    for course in courses:
        for m in course.milestones:
            rate, completed, enrolled = milestone_completion_rate(m)
            rows.append(m.to_dict(extra={"completion_rate": rate, "completed": completed, "enrolled": enrolled}))
    return jsonify({"milestones": rows})


@analytics_bp.get("/alerts")
@jwt_required()
@role_required("instructor")
def alerts():
    ident = current_identity()
    courses = Course.query.filter_by(teacher_id=ident["id"]).all()
    course_ids = [c.course_id for c in courses]
    deadline_alerts = deadline_alerts_for_courses(courses)
    performance_alerts = performance_alerts_for_courses(courses)

    disengaged = []
    student_ids = {
        e.student_id for e in Enrollment.query.filter(Enrollment.course_id.in_(course_ids)).all()
    } if course_ids else set()
    for sid in student_ids:
        summary = student_risk_summary(sid, course_ids)
        if summary["days_since_login"] >= 6 or summary["time_spent_minutes"] < 20:
            disengaged.append(summary)

    disengaged.sort(key=lambda s: -s["days_since_login"])
    return jsonify(
        {
            "deadline_alerts": deadline_alerts,
            "performance_alerts": performance_alerts,
            "disengaged": disengaged,
        }
    )


@analytics_bp.get("/charts/<name>")
@jwt_required()
@role_required("instructor")
def chart(name):
    allowed = {
        "completions",
        "score_trend",
        "heatmap",
        "histogram",
        "milestones",
        "tree",
        "coefficients",
    }
    if name not in allowed:
        return jsonify({"error": "Unknown chart"}), 404
    generate_all_charts(current_identity()["id"])
    path = Path(current_app.config["CHART_FOLDER"]) / f"{name}.png"
    artefact = Path(current_app.config["AI_ARTEFACT_FOLDER"]) / f"{name}.png"
    if path.exists():
        return send_file(path, mimetype="image/png")
    if artefact.exists():
        return send_file(artefact, mimetype="image/png")
    return jsonify({"error": "Chart not available yet"}), 404
