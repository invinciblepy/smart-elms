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


def test_register_and_login_student(client):
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Test Student",
            "email": "test.student@university.edu",
            "password": "Password123!",
            "role": "student",
        },
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["user"]["role"] == "student"
    assert data["access_token"]

    res = client.post(
        "/api/auth/login",
        json={"email": "test.student@university.edu", "password": "Password123!"},
    )
    assert res.status_code == 200
    assert res.get_json()["user"]["email"] == "test.student@university.edu"


def test_register_rejects_short_password(client):
    res = client.post(
        "/api/auth/register",
        json={
            "full_name": "X",
            "email": "bad",
            "password": "short",
            "role": "student",
        },
    )
    assert res.status_code == 400


def test_login_rejects_bad_password(client):
    client.post(
        "/api/auth/register",
        json={
            "full_name": "Test Student",
            "email": "test.student@university.edu",
            "password": "Password123!",
            "role": "student",
        },
    )
    res = client.post(
        "/api/auth/login",
        json={"email": "test.student@university.edu", "password": "wrong-password"},
    )
    assert res.status_code == 401
