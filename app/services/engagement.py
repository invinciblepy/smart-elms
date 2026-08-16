from datetime import datetime, timezone

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
from app.utils import days_since, progress_status_label


def days_since_last_login(student_id):
    student = db.session.get(Student, student_id)
    last = student.last_login_at if student else None
    if last is None:
        latest = (
            LoginActivity.query.filter_by(student_id=student_id)
            .order_by(LoginActivity.login_time.desc())
            .first()
        )
        last = latest.login_time if latest else None
    if last is None:
        return 30
    return days_since(last)


def recompute_course_progress(student_id, course_id):
    modules = Module.query.filter_by(course_id=course_id).all()
    assignments = Assignment.query.filter_by(course_id=course_id).all()
    quizzes = Quiz.query.filter_by(course_id=course_id).all()

    scores = []
    if modules:
        done = ModuleEngagement.query.filter(
            ModuleEngagement.student_id == student_id,
            ModuleEngagement.module_id.in_([m.module_id for m in modules]),
            ModuleEngagement.completed.is_(True),
        ).count()
        scores.append(100 * done / len(modules))
    if assignments:
        submitted = Submission.query.filter(
            Submission.student_id == student_id,
            Submission.assignment_id.in_([a.assignment_id for a in assignments]),
        ).count()
        scores.append(100 * submitted / len(assignments))
    if quizzes:
        attempted = {
            a.quiz_id
            for a in QuizAttempt.query.filter(
                QuizAttempt.student_id == student_id,
                QuizAttempt.quiz_id.in_([q.quiz_id for q in quizzes]),
            ).all()
        }
        scores.append(100 * len(attempted) / len(quizzes))

    progress = int(round(sum(scores) / len(scores))) if scores else 0
    progress = max(0, min(100, progress))
    enrollment = Enrollment.query.filter_by(student_id=student_id, course_id=course_id).first()
    if enrollment:
        enrollment.progress_percent = progress
        db.session.commit()
    return progress


def student_features(student_id):
    enrollments = Enrollment.query.filter_by(student_id=student_id).all()
    course_ids = [e.course_id for e in enrollments]
    assignments = Assignment.query.filter(Assignment.course_id.in_(course_ids)).all() if course_ids else []
    assignment_ids = [a.assignment_id for a in assignments]
    submissions = (
        Submission.query.filter(
            Submission.student_id == student_id, Submission.assignment_id.in_(assignment_ids)
        ).all()
        if assignment_ids
        else []
    )
    quizzes = Quiz.query.filter(Quiz.course_id.in_(course_ids)).all() if course_ids else []
    quiz_ids = [q.quiz_id for q in quizzes]
    attempts = (
        QuizAttempt.query.filter(
            QuizAttempt.student_id == student_id, QuizAttempt.quiz_id.in_(quiz_ids)
        ).all()
        if quiz_ids
        else []
    )

    now = datetime.now(timezone.utc)
    window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta

    window_start = window_start - timedelta(days=30)
    logins = LoginActivity.query.filter(
        LoginActivity.student_id == student_id, LoginActivity.login_time >= window_start
    ).count()

    scored = [s.score for s in submissions if s.score is not None]
    avg_assignment = float(sum(scored) / len(scored)) if scored else 0.0
    submit_rate = (len(submissions) / len(assignments)) if assignments else 0.0
    quiz_scores = [a.score for a in attempts]
    avg_quiz = float(sum(quiz_scores) / len(quiz_scores)) if quiz_scores else 0.0
    completion = (
        float(sum(e.progress_percent or 0 for e in enrollments) / (100 * len(enrollments)))
        if enrollments
        else 0.0
    )

    return {
        "login_frequency": int(logins),
        "avg_assignment_score": round(avg_assignment, 2),
        "assignment_submission_rate": round(min(1.0, submit_rate), 3),
        "avg_quiz_score": round(avg_quiz, 2),
        "days_since_last_login": int(days_since_last_login(student_id)),
        "course_completion_rate": round(min(1.0, completion), 3),
    }


def student_risk_summary(student_id, course_ids=None):
    student = db.session.get(Student, student_id)
    prediction = (
        Prediction.query.filter_by(student_id=student_id).order_by(Prediction.created_at.desc()).first()
    )
    enrollments = Enrollment.query.filter_by(student_id=student_id).all()
    if course_ids:
        enrollments = [e for e in enrollments if e.course_id in course_ids]
    primary = enrollments[0].course.title if enrollments else "—"
    days = days_since_last_login(student_id)
    time_spent = 0
    q = ModuleEngagement.query.filter_by(student_id=student_id)
    if course_ids:
        module_ids = [m.module_id for m in Module.query.filter(Module.course_id.in_(course_ids)).all()]
        if module_ids:
            q = q.filter(ModuleEngagement.module_id.in_(module_ids))
        else:
            q = q.filter(False)
    time_spent = sum(e.time_spent_minutes or 0 for e in q.all())

    risk = prediction.risk_level if prediction else "Low"
    return {
        "student_id": student_id,
        "full_name": student.full_name if student else "",
        "email": student.email if student else "",
        "course": primary,
        "days_since_login": days,
        "time_spent_minutes": time_spent,
        "risk_level": risk,
        "at_risk": bool(prediction.at_risk) if prediction else False,
        "probability": prediction.probability if prediction else 0,
        "avg_progress": int(round(sum(e.progress_percent or 0 for e in enrollments) / len(enrollments)))
        if enrollments
        else 0,
        "status_label": progress_status_label(
            int(round(sum(e.progress_percent or 0 for e in enrollments) / len(enrollments))) if enrollments else 0
        ),
    }


def milestone_met(milestone, student_id):
    rtype = milestone.requirement_type
    ref = milestone.requirement_ref_id
    if rtype == "assignment_submit":
        if ref:
            return (
                Submission.query.filter_by(assignment_id=ref, student_id=student_id).first() is not None
            )
        assignment_ids = [a.assignment_id for a in Assignment.query.filter_by(course_id=milestone.course_id).all()]
        if not assignment_ids:
            return False
        return (
            Submission.query.filter(
                Submission.student_id == student_id, Submission.assignment_id.in_(assignment_ids)
            ).first()
            is not None
        )
    if rtype == "quiz_attempt":
        if ref:
            return QuizAttempt.query.filter_by(quiz_id=ref, student_id=student_id).first() is not None
        quiz_ids = [q.quiz_id for q in Quiz.query.filter_by(course_id=milestone.course_id).all()]
        if not quiz_ids:
            return False
        return (
            QuizAttempt.query.filter(
                QuizAttempt.student_id == student_id, QuizAttempt.quiz_id.in_(quiz_ids)
            ).first()
            is not None
        )
    if rtype == "module_access":
        if ref:
            eng = ModuleEngagement.query.filter_by(module_id=ref, student_id=student_id).first()
            return bool(eng and (eng.completed or (eng.time_spent_minutes or 0) > 0))
        module_ids = [m.module_id for m in Module.query.filter_by(course_id=milestone.course_id).all()]
        if not module_ids:
            return False
        eng = ModuleEngagement.query.filter(
            ModuleEngagement.student_id == student_id, ModuleEngagement.module_id.in_(module_ids)
        ).first()
        return bool(eng and (eng.completed or (eng.time_spent_minutes or 0) > 0))
    if rtype == "course_progress":
        enr = Enrollment.query.filter_by(student_id=student_id, course_id=milestone.course_id).first()
        return bool(enr and (enr.progress_percent or 0) >= 70)
    enr = Enrollment.query.filter_by(student_id=student_id, course_id=milestone.course_id).first()
    return bool(enr and (enr.progress_percent or 0) >= 50)


def performance_alerts_for_courses(courses):
    now = datetime.now(timezone.utc)
    rows = []
    for course in courses:
        for assignment in course.assignments:
            due = assignment.due_date
            if due and due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            overdue = bool(due and due < now)
            by_student = {s.student_id: s for s in assignment.submissions}
            for enrollment in course.enrollments:
                student = enrollment.student
                name = student.full_name if student else f"Student {enrollment.student_id}"
                sub = by_student.get(enrollment.student_id)
                if overdue and sub is None:
                    rows.append(
                        {
                            "severity": "red",
                            "title": f"{name} has not submitted {assignment.title}",
                            "detail": f"{course.title} is past the deadline and no file or comment was received.",
                            "course": course.title,
                            "student_id": enrollment.student_id,
                            "assignment_id": assignment.assignment_id,
                        }
                    )
                elif sub is not None and sub.score is not None and sub.score < 70:
                    rows.append(
                        {
                            "severity": "red",
                            "title": f"{name} scored {sub.score} on {assignment.title}",
                            "detail": f"Score is below 70 on {course.title}.",
                            "course": course.title,
                            "student_id": enrollment.student_id,
                            "assignment_id": assignment.assignment_id,
                        }
                    )
    missed = [row for row in rows if "has not submitted" in row["title"]]
    scored = [row for row in rows if "scored" in row["title"]]
    mixed = []
    for i in range(max(len(scored), len(missed))):
        if i < len(scored):
            mixed.append(scored[i])
        if i < len(missed):
            mixed.append(missed[i])
    return mixed[:24]


def deadline_alerts_for_courses(courses):
    now = datetime.now(timezone.utc)
    deadline_alerts = []
    for course in courses:
        enrolled = len(course.enrollments) or 1
        for assignment in course.assignments:
            due = assignment.due_date
            if not due:
                continue
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            days = (due - now).days
            rate = 100 * len(assignment.submissions) / enrolled
            if 0 <= days <= 3 and rate < 50:
                deadline_alerts.append(
                    {
                        "severity": "yellow",
                        "title": f"{assignment.title} is due in {days} day(s)",
                        "detail": f"Only {rate:.0f}% of {course.title} have submitted.",
                        "course": course.title,
                        "assignment_id": assignment.assignment_id,
                        "days": days,
                        "submission_rate": round(rate, 1),
                    }
                )
    return deadline_alerts


def milestone_completion_rate(milestone):
    enrolled = Enrollment.query.filter_by(course_id=milestone.course_id).all()
    if not enrolled:
        return 0, 0, 0
    done = sum(1 for e in enrolled if milestone_met(milestone, e.student_id))
    return round(100 * done / len(enrolled), 1), done, len(enrolled)
