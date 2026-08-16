from pathlib import Path

from flask import Blueprint, abort, current_app, send_from_directory

pages_bp = Blueprint("pages", __name__)


def _frontend(*parts):
    folder = Path(current_app.config["FRONTEND_FOLDER"])
    return folder.joinpath(*parts)


@pages_bp.get("/")
def login_page():
    return send_from_directory(_frontend(), "login.html")


@pages_bp.get("/register")
def register_page():
    return send_from_directory(_frontend(), "register.html")


@pages_bp.get("/forgot")
def forgot_page():
    return send_from_directory(_frontend(), "forgot.html")


@pages_bp.get("/student/<page>")
def student_page(page):
    allowed = {
        "dashboard",
        "courses",
        "course",
        "module",
        "assignments",
        "submit",
        "confirm",
        "quizzes",
        "quiz",
        "grades",
        "progress",
        "support",
    }
    if page not in allowed:
        abort(404)
    return send_from_directory(_frontend("student"), f"{page}.html")


@pages_bp.get("/instructor/<page>")
def instructor_page(page):
    allowed = {
        "dashboard",
        "classes",
        "class",
        "students",
        "student",
        "milestones",
        "alerts",
        "reports",
        "assignment",
    }
    if page not in allowed:
        abort(404)
    return send_from_directory(_frontend("instructor"), f"{page}.html")
