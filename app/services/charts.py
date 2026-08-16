from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from flask import current_app

from app.extensions import db
from app.models import (
    Assignment,
    Course,
    Enrollment,
    LoginActivity,
    Milestone,
    Quiz,
    QuizAttempt,
    Student,
    Submission,
)
from app.services.engagement import milestone_completion_rate

sns.set_theme(style="whitegrid")
NAVY = "#1B365D"
BLUE = "#3B6FF5"
GREEN = "#16A34A"
ORANGE = "#EA580C"
RED = "#DC2626"


def _chart_dir():
    path = Path(current_app.config["CHART_FOLDER"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_all_charts(teacher_id):
    out = _chart_dir()
    courses = Course.query.filter_by(teacher_id=teacher_id).all()
    _completion_chart(courses, out / "completions.png")
    _score_trend(courses, out / "score_trend.png")
    _heatmap(courses, out / "heatmap.png")
    _histogram(courses, out / "histogram.png")
    _milestone_bars(courses, out / "milestones.png")
    return out


def _completion_chart(courses, path):
    labels, on_time, late = [], [], []
    for course in courses:
        enrolled = len(course.enrollments) or 1
        for assignment in course.assignments:
            ot = late_n = 0
            for s in assignment.submissions:
                due = assignment.due_date
                submitted = s.submitted_at
                if due and submitted:
                    if due.tzinfo is None:
                        due = due.replace(tzinfo=timezone.utc)
                    if submitted.tzinfo is None:
                        submitted = submitted.replace(tzinfo=timezone.utc)
                    if submitted <= due:
                        ot += 1
                    else:
                        late_n += 1
                else:
                    ot += 1
            labels.append(assignment.title[:22])
            on_time.append(100 * ot / enrolled)
            late.append(100 * late_n / enrolled)

    fig, ax = plt.subplots(figsize=(10, 4.8))
    if not labels:
        ax.text(0.5, 0.5, "No assignment data yet", ha="center", va="center")
    else:
        x = np.arange(len(labels))
        ax.bar(x, on_time, color=BLUE, label="On time")
        ax.bar(x, late, bottom=on_time, color=ORANGE, label="Late")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=25, ha="right")
        ax.set_ylabel("Class completion (%)")
        ax.set_title("Assignment completion")
        ax.legend()
        ax.set_ylim(0, 110)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _score_trend(courses, path):
    points = []
    for course in courses:
        for assignment in course.assignments:
            scores = [s.score for s in assignment.submissions if s.score is not None]
            if scores:
                points.append((assignment.title[:18], float(np.mean(scores)), "Assignment"))
        for quiz in course.quizzes:
            scores = [a.score for a in quiz.attempts]
            if scores:
                points.append((quiz.title[:18], float(np.mean(scores)), "Quiz"))

    fig, ax = plt.subplots(figsize=(10, 4.5))
    if not points:
        ax.text(0.5, 0.5, "No scored work yet", ha="center", va="center")
    else:
        labels = [p[0] for p in points]
        values = [p[1] for p in points]
        ax.plot(labels, values, marker="o", color=BLUE, linewidth=2)
        ax.set_ylim(0, 100)
        ax.set_ylabel("Class average")
        ax.set_title("Score trend across assessments")
        plt.xticks(rotation=25, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _heatmap(courses, path):
    course_ids = [c.course_id for c in courses]
    student_ids = sorted(
        {
            e.student_id
            for e in Enrollment.query.filter(Enrollment.course_id.in_(course_ids)).all()
        }
    ) if course_ids else []
    # Keep the chart readable: up to 16 students
    student_ids = student_ids[:16]
    now = datetime.now(timezone.utc)
    weeks = 8
    week_starts = [now - timedelta(days=7 * (weeks - i)) for i in range(weeks)]
    labels = [d.strftime("W%U") for d in week_starts]
    names = []
    matrix = []
    for sid in student_ids:
        student = db.session.get(Student, sid)
        names.append((student.full_name if student else str(sid))[:16])
        counts = []
        for i, start in enumerate(week_starts):
            end = week_starts[i + 1] if i + 1 < len(week_starts) else now + timedelta(days=1)
            n = LoginActivity.query.filter(
                LoginActivity.student_id == sid,
                LoginActivity.login_time >= start,
                LoginActivity.login_time < end,
            ).count()
            counts.append(n)
        matrix.append(counts)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    if not matrix:
        ax.text(0.5, 0.5, "No login data yet", ha="center", va="center")
    else:
        sns.heatmap(
            np.array(matrix),
            annot=False,
            cmap="Blues",
            xticklabels=labels,
            yticklabels=names,
            ax=ax,
        )
        ax.set_title("Login frequency heatmap (students × week)")
        ax.set_xlabel("Week")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _histogram(courses, path):
    scores = []
    for course in courses:
        for quiz in course.quizzes:
            scores.extend(a.score for a in quiz.attempts)
        for assignment in course.assignments:
            scores.extend(s.score for s in assignment.submissions if s.score is not None)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    if not scores:
        ax.text(0.5, 0.5, "No scores yet", ha="center", va="center")
    else:
        sns.histplot(scores, bins=12, color=BLUE, ax=ax)
        ax.set_title("Score distribution")
        ax.set_xlabel("Score")
        ax.set_ylabel("Count")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _milestone_bars(courses, path):
    titles, rates = [], []
    for course in courses:
        for m in course.milestones:
            rate, _, _ = milestone_completion_rate(m)
            titles.append(f"{course.title[:12]}: {m.title[:18]}")
            rates.append(rate)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    if not titles:
        ax.text(0.5, 0.5, "No milestones yet", ha="center", va="center")
    else:
        colors = [GREEN if r >= 70 else ORANGE if r >= 40 else RED for r in rates]
        ax.barh(titles[::-1], rates[::-1], color=colors[::-1])
        ax.set_xlim(0, 100)
        ax.set_xlabel("Class completion (%)")
        ax.set_title("Milestone progress")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
