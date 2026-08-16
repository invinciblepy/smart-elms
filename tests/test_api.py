import pytest

from app import create_app
from app.extensions import db
from config import TestingConfig


@pytest.fixture()
def app_client():
    app = create_app(TestingConfig)
    with app.app_context():
        db.create_all()
        with app.test_client() as client:
            yield client
        db.session.remove()
        db.drop_all()


def _auth(client, role, email):
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": f"{role.title()} User",
            "email": email,
            "password": "Password123!",
            "role": role,
        },
    )
    token = res.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_instructor_creates_course_and_student_enrols(app_client):
    teacher = _auth(app_client, "instructor", "t@university.edu")
    student = _auth(app_client, "student", "s@university.edu")

    res = app_client.post(
        "/api/courses",
        json={"title": "Web Development", "description": "HTML and CSS"},
        headers=teacher,
    )
    assert res.status_code == 201
    course_id = res.get_json()["course"]["course_id"]

    res = app_client.post(f"/api/courses/{course_id}/enroll", headers=student)
    assert res.status_code == 201
    assert res.get_json()["course"]["enrolled"] is True

    res = app_client.get("/api/courses", headers=student)
    titles = [c["title"] for c in res.get_json()["courses"]]
    assert "Web Development" in titles


def test_student_cannot_create_course(app_client):
    student = _auth(app_client, "student", "s2@university.edu")
    res = app_client.post("/api/courses", json={"title": "Nope"}, headers=student)
    assert res.status_code == 403


def test_health(app_client):
    res = app_client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"
