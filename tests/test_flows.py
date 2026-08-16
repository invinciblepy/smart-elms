import io

import pytest

from app import create_app
from app.extensions import db
from config import TestingConfig


@pytest.fixture()
def client():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        with app.test_client() as client:
            yield client
        db.session.remove()
        db.drop_all()


def auth(client, role="instructor", email=None):
    email = email or f"{role}@university.edu"
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": f"{role.title()} Demo",
            "email": email,
            "password": "Password123!",
            "role": role,
        },
    )
    token = res.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_forgot_password(client):
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Student Demo",
            "email": "s@university.edu",
            "password": "Password123!",
            "role": "student",
        },
    )
    res = client.post("/api/auth/forgot-password", json={"email": "s@university.edu"})
    assert res.status_code == 200
    assert "instructor" in res.get_json()["message"].lower()


def test_remember_me_login(client):
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Student Demo",
            "email": "s@university.edu",
            "password": "Password123!",
            "role": "student",
        },
    )
    res = client.post(
        "/api/auth/login",
        json={"email": "s@university.edu", "password": "Password123!", "remember": True},
    )
    assert res.status_code == 200
    assert res.get_json()["access_token"]


def test_protected_without_token(client):
    res = client.get("/api/courses")
    assert res.status_code == 401


def test_file_upload_and_score(client):
    teacher = auth(client, "instructor", "t@university.edu")
    student = auth(client, "student", "st@university.edu")
    course_id = client.post(
        "/api/courses", json={"title": "Web Development", "description": "x"}, headers=teacher
    ).get_json()["course"]["course_id"]
    client.post(f"/api/courses/{course_id}/enroll", headers=student)
    aid = client.post(
        f"/api/courses/{course_id}/assignments",
        json={"title": "Assignment 3", "description": "Do the work", "max_score": 100},
        headers=teacher,
    ).get_json()["assignment"]["assignment_id"]

    data = {"comment": "My answer"}
    data["file"] = (io.BytesIO(b"hello assignment"), "work.txt")
    res = client.post(
        f"/api/assignments/{aid}/submit",
        data=data,
        headers=student,
        content_type="multipart/form-data",
    )
    assert res.status_code == 201
    sub_id = res.get_json()["submission"]["submission_id"]

    bad = {"comment": "x"}
    bad["file"] = (io.BytesIO(b"nope"), "virus.exe")
    res = client.post(
        f"/api/assignments/{aid}/submit",
        data=bad,
        headers=student,
        content_type="multipart/form-data",
    )
    assert res.status_code == 400

    res = client.put(f"/api/submissions/{sub_id}/score", json={"score": 72}, headers=teacher)
    assert res.status_code == 200
    assert res.get_json()["submission"]["score"] == 72


def test_quiz_attempt(client):
    teacher = auth(client, "instructor", "t2@university.edu")
    student = auth(client, "student", "st2@university.edu")
    course_id = client.post(
        "/api/courses", json={"title": "Quiz Course"}, headers=teacher
    ).get_json()["course"]["course_id"]
    client.post(f"/api/courses/{course_id}/enroll", headers=student)
    res = client.post(
        f"/api/courses/{course_id}/quizzes",
        json={
            "title": "Checkpoint",
            "questions": [
                {
                    "prompt": "2+2",
                    "option_a": "3",
                    "option_b": "4",
                    "option_c": "5",
                    "option_d": "6",
                    "correct_option": "B",
                }
            ],
        },
        headers=teacher,
    )
    assert res.status_code == 201
    qid = res.get_json()["quiz"]["quiz_id"]
    qnid = res.get_json()["quiz"]["questions"][0]["question_id"]
    res = client.post(
        f"/api/quizzes/{qid}/attempt",
        json={"answers": {str(qnid): "B"}},
        headers=student,
    )
    assert res.status_code == 201
    assert res.get_json()["attempt"]["score"] == 100


def test_milestone_crud(client):
    teacher = auth(client, "instructor", "t3@university.edu")
    course_id = client.post(
        "/api/courses", json={"title": "PM"}, headers=teacher
    ).get_json()["course"]["course_id"]
    res = client.post(
        f"/api/courses/{course_id}/milestones",
        json={"title": "Week 1", "requirement_type": "course_progress"},
        headers=teacher,
    )
    assert res.status_code == 201
    mid = res.get_json()["milestone"]["milestone_id"]
    res = client.put(f"/api/milestones/{mid}", json={"title": "Week 1 done"}, headers=teacher)
    assert res.status_code == 200
    assert res.get_json()["milestone"]["title"] == "Week 1 done"
    res = client.delete(f"/api/milestones/{mid}", headers=teacher)
    assert res.status_code == 200


def test_predict_validation(client):
    teacher = auth(client, "instructor", "t4@university.edu")
    res = client.post("/api/predict", json={"login_frequency": 3}, headers=teacher)
    assert res.status_code in {400, 503}


def test_pages_exist(client):
    for path in (
        "/",
        "/register",
        "/forgot",
        "/student/confirm",
        "/student/dashboard",
        "/student/support",
        "/instructor/assignment",
        "/instructor/milestones",
        "/instructor/alerts",
        "/instructor/reports",
    ):
        res = client.get(path)
        assert res.status_code == 200


def test_forgot_rejects_bad_email(client):
    res = client.post("/api/auth/forgot-password", json={"email": "not-an-email"})
    assert res.status_code == 400


def test_duplicate_register(client):
    payload = {
        "full_name": "Student Demo",
        "email": "dup@university.edu",
        "password": "Password123!",
        "role": "student",
    }
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 400


def test_logout_and_me(client):
    headers = auth(client, "student", "out@university.edu")
    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["user"]["role"] == "student"
    res = client.post("/api/auth/logout", headers=headers)
    assert res.status_code == 200


def test_already_enrolled(client):
    teacher = auth(client, "instructor", "t5@university.edu")
    student = auth(client, "student", "st5@university.edu")
    course_id = client.post(
        "/api/courses", json={"title": "Repeat"}, headers=teacher
    ).get_json()["course"]["course_id"]
    assert client.post(f"/api/courses/{course_id}/enroll", headers=student).status_code == 201
    assert client.post(f"/api/courses/{course_id}/enroll", headers=student).status_code == 400


def test_course_update_and_module_complete(client):
    teacher = auth(client, "instructor", "t6@university.edu")
    student = auth(client, "student", "st6@university.edu")
    course_id = client.post(
        "/api/courses", json={"title": "Old title"}, headers=teacher
    ).get_json()["course"]["course_id"]
    res = client.put(f"/api/courses/{course_id}", json={"title": "New title"}, headers=teacher)
    assert res.status_code == 200
    assert res.get_json()["course"]["title"] == "New title"
    client.post(f"/api/courses/{course_id}/enroll", headers=student)
    module_id = client.post(
        f"/api/courses/{course_id}/modules",
        json={"title": "Lesson 1", "content": "Notes"},
        headers=teacher,
    ).get_json()["module"]["module_id"]
    res = client.post(f"/api/modules/{module_id}/complete", headers=student)
    assert res.status_code == 200
    assert res.get_json()["module"]["status"] == "Completed"


def test_score_bounds_and_student_forbidden(client):
    teacher = auth(client, "instructor", "t7@university.edu")
    student = auth(client, "student", "st7@university.edu")
    course_id = client.post(
        "/api/courses", json={"title": "Score course"}, headers=teacher
    ).get_json()["course"]["course_id"]
    client.post(f"/api/courses/{course_id}/enroll", headers=student)
    aid = client.post(
        f"/api/courses/{course_id}/assignments",
        json={"title": "A1", "max_score": 100},
        headers=teacher,
    ).get_json()["assignment"]["assignment_id"]
    sub_id = client.post(
        f"/api/assignments/{aid}/submit",
        data={"comment": "done"},
        headers=student,
        content_type="multipart/form-data",
    ).get_json()["submission"]["submission_id"]
    assert (
        client.put(f"/api/submissions/{sub_id}/score", json={"score": 150}, headers=teacher).status_code
        == 400
    )
    assert (
        client.put(f"/api/submissions/{sub_id}/score", json={"score": 80}, headers=student).status_code
        == 403
    )


def test_deadline_alert_and_dashboards(client):
    from datetime import datetime, timedelta, timezone

    teacher = auth(client, "instructor", "t8@university.edu")
    student = auth(client, "student", "st8@university.edu")
    course_id = client.post(
        "/api/courses", json={"title": "Alert course"}, headers=teacher
    ).get_json()["course"]["course_id"]
    client.post(f"/api/courses/{course_id}/enroll", headers=student)
    due = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    client.post(
        f"/api/courses/{course_id}/assignments",
        json={"title": "Due soon work", "due_date": due, "max_score": 100},
        headers=teacher,
    )
    alerts = client.get("/api/analytics/alerts", headers=teacher)
    assert alerts.status_code == 200
    titles = [row["title"] for row in alerts.get_json()["deadline_alerts"]]
    assert any("Due soon work" in t for t in titles)

    dash_i = client.get("/api/analytics/dashboard/instructor", headers=teacher)
    assert dash_i.status_code == 200
    assert dash_i.get_json()["stats"]["total_students"] == 1
    assert dash_i.get_json()["deadline_alerts"]

    dash_s = client.get("/api/analytics/dashboard/student", headers=student)
    assert dash_s.status_code == 200
    assert dash_s.get_json()["stats"]["assignments_due"] >= 1
    assert dash_s.get_json()["due_assignments"]


def test_predict_full_features(client):
    teacher = auth(client, "instructor", "t9@university.edu")
    res = client.post(
        "/api/predict",
        json={
            "login_frequency": 2,
            "avg_assignment_score": 40,
            "assignment_submission_rate": 0.2,
            "avg_quiz_score": 35,
            "days_since_last_login": 14,
            "course_completion_rate": 0.2,
        },
        headers=teacher,
    )
    assert res.status_code == 200
    body = res.get_json()
    assert "risk_level" in body
    assert "probability" in body


def test_milestone_due_date_update(client):
    from datetime import datetime, timedelta, timezone

    teacher = auth(client, "instructor", "t10@university.edu")
    course_id = client.post(
        "/api/courses", json={"title": "Goals"}, headers=teacher
    ).get_json()["course"]["course_id"]
    due = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    res = client.post(
        f"/api/courses/{course_id}/milestones",
        json={
            "title": "Week 2",
            "description": "Reach 70 percent",
            "requirement_type": "course_progress",
            "due_date": due,
        },
        headers=teacher,
    )
    assert res.status_code == 201
    mid = res.get_json()["milestone"]["milestone_id"]
    res = client.put(
        f"/api/milestones/{mid}",
        json={"title": "Week 2 revised", "description": "Updated", "requirement_type": "quiz_attempt"},
        headers=teacher,
    )
    assert res.status_code == 200
    body = res.get_json()["milestone"]
    assert body["title"] == "Week 2 revised"
    assert body["requirement_type"] == "quiz_attempt"


def test_analytics_charts_and_predict_student(client):
    from datetime import datetime, timedelta, timezone

    teacher = auth(client, "instructor", "t16@university.edu")
    student = auth(client, "student", "st16@university.edu")
    course_id = client.post(
        "/api/courses", json={"title": "Analytics", "description": "Charts"}, headers=teacher
    ).get_json()["course"]["course_id"]
    client.post(f"/api/courses/{course_id}/enroll", headers=student)
    client.post(
        f"/api/courses/{course_id}/modules",
        json={"title": "M1", "content": "Notes"},
        headers=teacher,
    )
    due = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    aid = client.post(
        f"/api/courses/{course_id}/assignments",
        json={"title": "A1", "due_date": due, "max_score": 100},
        headers=teacher,
    ).get_json()["assignment"]["assignment_id"]
    client.post(
        f"/api/assignments/{aid}/submit",
        data={"comment": "done"},
        headers=student,
        content_type="multipart/form-data",
    )
    qid = client.post(
        f"/api/courses/{course_id}/quizzes",
        json={
            "title": "Q1",
            "questions": [
                {
                    "prompt": "1+1",
                    "option_a": "1",
                    "option_b": "2",
                    "option_c": "3",
                    "option_d": "4",
                    "correct_option": "B",
                }
            ],
        },
        headers=teacher,
    ).get_json()["quiz"]["quiz_id"]
    client.post(f"/api/quizzes/{qid}/attempt", json={"answers": {}}, headers=student)
    student_id = client.get("/api/auth/me", headers=student).get_json()["user"]["id"]
    assert client.get("/api/analytics/completions", headers=teacher).status_code == 200
    assert client.get("/api/analytics/quiz-scores", headers=teacher).status_code == 200
    assert client.get("/api/analytics/logins", headers=teacher).status_code == 200
    assert client.get("/api/analytics/milestones", headers=teacher).status_code == 200
    profile = client.get(f"/api/analytics/students/{student_id}", headers=teacher)
    assert profile.status_code == 200
    chart = client.get("/api/analytics/charts/completions", headers=teacher)
    assert chart.status_code == 200
    assert "png" in chart.content_type
    pred = client.post("/api/predict", json={"student_id": student_id}, headers=student)
    assert pred.status_code == 200
    assert client.get("/api/predict/students", headers=teacher).status_code == 200
    assert client.get("/api/courses", headers=teacher).status_code == 200


def test_module_delete_and_mime_reject(client):
    teacher = auth(client, "instructor", "t14@university.edu")
    student = auth(client, "student", "st14@university.edu")
    course_id = client.post(
        "/api/courses", json={"title": "Delete me"}, headers=teacher
    ).get_json()["course"]["course_id"]
    client.post(f"/api/courses/{course_id}/enroll", headers=student)
    module_id = client.post(
        f"/api/courses/{course_id}/modules",
        json={"title": "Temp lesson", "content": "x"},
        headers=teacher,
    ).get_json()["module"]["module_id"]
    assert client.delete(f"/api/modules/{module_id}", headers=teacher).status_code == 200
    assert client.get(f"/api/modules/{module_id}", headers=teacher).status_code == 404

    aid = client.post(
        f"/api/courses/{course_id}/assignments",
        json={"title": "Mime check"},
        headers=teacher,
    ).get_json()["assignment"]["assignment_id"]
    data = {"comment": "x"}
    data["file"] = (io.BytesIO(b"not really a document"), "notes.txt", "image/png")
    res = client.post(
        f"/api/assignments/{aid}/submit",
        data=data,
        headers=student,
        content_type="multipart/form-data",
    )
    assert res.status_code == 400


def test_performance_alert_and_milestone_guard(client):
    from datetime import datetime, timedelta, timezone

    teacher = auth(client, "instructor", "t15@university.edu")
    student = auth(client, "student", "st15@university.edu")
    outsider = auth(client, "student", "out15@university.edu")
    course_id = client.post(
        "/api/courses", json={"title": "Red alerts"}, headers=teacher
    ).get_json()["course"]["course_id"]
    client.post(f"/api/courses/{course_id}/enroll", headers=student)
    due = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    client.post(
        f"/api/courses/{course_id}/assignments",
        json={"title": "Late work", "due_date": due},
        headers=teacher,
    )
    alerts = client.get("/api/analytics/alerts", headers=teacher)
    assert alerts.status_code == 200
    titles = [row["title"] for row in alerts.get_json()["performance_alerts"]]
    assert any("Late work" in t for t in titles)
    assert client.get(f"/api/courses/{course_id}/milestones", headers=outsider).status_code == 403


def test_unenrolled_student_cannot_open_assignment(client):
    teacher = auth(client, "instructor", "t13@university.edu")
    outsider = auth(client, "student", "out13@university.edu")
    course_id = client.post(
        "/api/courses", json={"title": "Closed"}, headers=teacher
    ).get_json()["course"]["course_id"]
    aid = client.post(
        f"/api/courses/{course_id}/assignments",
        json={"title": "Hidden work"},
        headers=teacher,
    ).get_json()["assignment"]["assignment_id"]
    res = client.get(f"/api/assignments/{aid}", headers=outsider)
    assert res.status_code == 403


def test_instructor_students_and_download(client):
    teacher = auth(client, "instructor", "t11@university.edu")
    student = auth(client, "student", "st11@university.edu")
    other = auth(client, "student", "st12@university.edu")
    course_id = client.post(
        "/api/courses", json={"title": "Files"}, headers=teacher
    ).get_json()["course"]["course_id"]
    client.post(f"/api/courses/{course_id}/enroll", headers=student)
    aid = client.post(
        f"/api/courses/{course_id}/assignments",
        json={"title": "Upload"},
        headers=teacher,
    ).get_json()["assignment"]["assignment_id"]
    data = {"comment": "file"}
    data["file"] = (io.BytesIO(b"hello"), "notes.txt")
    res = client.post(
        f"/api/assignments/{aid}/submit",
        data=data,
        headers=student,
        content_type="multipart/form-data",
    )
    filename = res.get_json()["submission"]["file_path"]
    assert client.get(f"/api/uploads/{filename}", headers=teacher).status_code == 200
    assert client.get(f"/api/uploads/{filename}", headers=other).status_code == 403
    roster = client.get(f"/api/instructor/classes/{course_id}/roster", headers=teacher)
    assert roster.status_code == 200
    assert len(roster.get_json()["students"]) == 1
    people = client.get("/api/instructor/students", headers=teacher)
    assert people.status_code == 200
    assert people.get_json()["students"]
