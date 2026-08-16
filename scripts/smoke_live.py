"""Live HTTP smoke against a running Smart ELMS server."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:5000"


def req(path, method="GET", data=None, token=None, expect=200):
    headers = {"Accept": "application/json"}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as res:
            raw = res.read()
            payload = json.loads(raw.decode("utf-8")) if raw and res.headers.get_content_type() == "application/json" else raw
            if res.status != expect:
                raise SystemExit(f"FAIL {method} {path} expected {expect} got {res.status}")
            return res.status, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        if exc.code != expect:
            raise SystemExit(f"FAIL {method} {path} expected {expect} got {exc.code}: {raw[:300]!r}")
        try:
            return exc.code, json.loads(raw.decode("utf-8"))
        except Exception:
            return exc.code, raw


def main():
    status, health = req("/health")
    print("health", status, health)

    pages = [
        "/",
        "/register",
        "/forgot",
        "/student/dashboard",
        "/student/confirm",
        "/student/support",
        "/instructor/assignment",
        "/instructor/milestones",
        "/instructor/alerts",
        "/instructor/reports",
    ]
    for path in pages:
        request = urllib.request.Request(BASE + path)
        with urllib.request.urlopen(request, timeout=15) as res:
            if res.status != 200:
                raise SystemExit(f"FAIL page {path} {res.status}")
            print("page", path, res.status)

    req("/api/courses", expect=401)

    _, login = req(
        "/api/auth/login",
        method="POST",
        data={"email": "instructor@university.edu", "password": "Password123!", "remember": True},
    )
    teacher = login["access_token"]
    print("instructor login ok", login["user"]["email"])

    _, dash = req("/api/analytics/dashboard/instructor", token=teacher)
    print(
        "instructor dash",
        dash["stats"],
        "alerts",
        len(dash.get("deadline_alerts") or []),
        "attention",
        len(dash.get("students_needing_attention") or []),
    )

    _, alerts = req("/api/analytics/alerts", token=teacher)
    print(
        "deadline alerts",
        len(alerts["deadline_alerts"]),
        "performance",
        len(alerts.get("performance_alerts") or []),
        "disengaged",
        len(alerts["disengaged"]),
    )

    _, miles = req("/api/milestones", token=teacher)
    print("milestones", len(miles["milestones"]))
    if miles["milestones"]:
        mid = miles["milestones"][0]["milestone_id"]
        _, updated = req(
            f"/api/milestones/{mid}",
            method="PUT",
            data={"description": miles["milestones"][0].get("description") or "Checked in live smoke"},
            token=teacher,
        )
        print("milestone update", updated["milestone"]["milestone_id"])

    for name in ("completions", "score_trend", "heatmap", "histogram", "milestones"):
        request = urllib.request.Request(
            BASE + f"/api/analytics/charts/{name}",
            headers={"Authorization": f"Bearer {teacher}"},
        )
        with urllib.request.urlopen(request, timeout=60) as res:
            if res.status != 200 or "png" not in (res.headers.get("Content-Type") or ""):
                raise SystemExit(f"FAIL chart {name} {res.status} {res.headers.get('Content-Type')}")
            print("chart", name, res.status, res.headers.get("Content-Type"), "bytes", res.length)

    _, pred = req(
        "/api/predict",
        method="POST",
        data={
            "login_frequency": 2,
            "avg_assignment_score": 38,
            "assignment_submission_rate": 0.25,
            "avg_quiz_score": 40,
            "days_since_last_login": 12,
            "course_completion_rate": 0.22,
        },
        token=teacher,
    )
    print("predict", pred["risk_level"], pred["probability"])

    _, forgot = req("/api/auth/forgot-password", method="POST", data={"email": "student@university.edu"})
    print("forgot", forgot)

    _, student_login = req(
        "/api/auth/login",
        method="POST",
        data={"email": "student@university.edu", "password": "Password123!"},
    )
    student = student_login["access_token"]
    _, s_dash = req("/api/analytics/dashboard/student", token=student)
    print(
        "student dash courses",
        s_dash["stats"]["courses_enrolled"],
        "due",
        s_dash["stats"]["assignments_due"],
        "banner",
        bool(s_dash.get("ai_banner")),
        "prediction",
        bool(s_dash.get("prediction")),
    )

    req("/api/courses", method="POST", data={"title": "Nope"}, token=student, expect=403)
    print("SMOKE OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("SMOKE FAIL", exc)
        sys.exit(1)
