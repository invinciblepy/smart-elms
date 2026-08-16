"""First-run seed: demo users, four courses, synthetic cohort, AI model, predictions."""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.extensions import bcrypt, db
from app.models import (
    Assignment,
    Course,
    Enrollment,
    LoginActivity,
    Milestone,
    Module,
    ModuleEngagement,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    Student,
    Submission,
    Teacher,
)
from app.services.engagement import recompute_course_progress
from app.services.ml import predict_for_student

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NOW = datetime.now(timezone.utc)
PASSWORD = "Password123!"

COURSE_DEFS = [
    {
        "title": "Web Development",
        "description": "Build modern, responsive websites with HTML, CSS and JavaScript.",
        "modules": [
            ("Introduction to the Web", "How the web works: browsers, HTTP, URLs and the request/response cycle."),
            ("Responsive Design Basics", "Flexible grids, media queries and mobile-first CSS."),
            ("Interactive Interfaces", "DOM events, forms and accessible interactive components."),
            ("Connecting to Services", "REST APIs, JSON and the Fetch API."),
            ("Building a Mini Project", "Plan, build and submit a small multi-page site."),
        ],
        "assignments": [
            ("Assignment 1 — Semantic homepage", "Create a semantic HTML homepage with navigation and a footer.", 21, 100),
            ("Assignment 2 — Responsive layout", "Rebuild the homepage so it works at 320px, 768px and 1200px.", 14, 100),
            ("Assignment 3 — Interactive form", "Complete the required tasks for this assignment and submit your work before the deadline.", 7, 100),
        ],
        "quiz": (
            "HTML & CSS checkpoint",
            [
                ("Which tag is used for the main page heading?", "h1", "p", "span", "div", "A"),
                ("What does CSS stand for?", "Computer Style Sheets", "Cascading Style Sheets", "Creative Styling System", "Coded Style Syntax", "B"),
                ("Which HTTP method is used to create a resource in REST?", "GET", "PUT", "POST", "HEAD", "C"),
                ("A media query is primarily used to…", "Connect to a database", "Adapt layout to viewport size", "Hash passwords", "Train a model", "B"),
            ],
        ),
        "milestones": [
            ("Complete first three modules", "module_access", 0, 18),
            ("Submit Assignment 1", "assignment_submit", 0, 20),
            ("Pass HTML & CSS checkpoint", "quiz_attempt", 0, 10),
        ],
    },
    {
        "title": "Database Systems",
        "description": "Relational modelling, SQL and database design for applications.",
        "modules": [
            ("Introduction to Databases", "Why we use databases and the difference between files and DBMS."),
            ("The Relational Model", "Relations, keys, integrity constraints and 3NF."),
            ("SQL Queries", "SELECT, JOIN, GROUP BY and subqueries."),
            ("ER Modelling", "Entities, relationships and mapping an ERD to tables."),
            ("Transactions", "ACID properties and isolation levels."),
        ],
        "assignments": [
            ("Assignment 1 — ERD for a library", "Draw a 3NF ERD and justify keys.", 18, 100),
            ("Assignment 2 — SQL worksheet", "Write ten queries against the sample schema.", 9, 100),
        ],
        "quiz": (
            "Normalisation quiz",
            [
                ("3NF forbids…", "Composite keys", "Transitive dependencies", "Foreign keys", "NULL values", "B"),
                ("A primary key must be…", "Nullable", "Unique and not null", "A date", "Encrypted", "B"),
                ("Which statement changes existing rows?", "INSERT", "SELECT", "UPDATE", "CREATE", "C"),
            ],
        ),
        "milestones": [
            ("Finish ER modelling module", "module_access", 3, 16),
            ("Submit ERD assignment", "assignment_submit", 0, 17),
        ],
    },
    {
        "title": "Project Management",
        "description": "Plan, track and deliver academic and software projects.",
        "modules": [
            ("Project lifecycle", "Initiation, planning, execution, monitoring and closure."),
            ("Work breakdown structures", "Decompose a project into manageable work packages."),
            ("Risk and stakeholders", "Identify, assess and communicate project risk."),
            ("Agile vs waterfall", "When each delivery style is appropriate."),
            ("Reporting progress", "RAG status, burndown and milestone tracking."),
        ],
        "assignments": [
            ("Assignment 1 — Project charter", "Write a one-page charter for Smart ELMS.", 16, 100),
            ("Assignment 2 — Risk register", "List eight risks with likelihood and mitigation.", 6, 100),
        ],
        "quiz": (
            "PM fundamentals",
            [
                ("A milestone is…", "A daily standup", "A significant checkpoint with no duration", "A Gantt bar", "A budget line", "B"),
                ("RAG status uses which colours?", "Red amber green", "Red azure gold", "Rose apple grey", "None", "A"),
                ("The critical path is the…", "Shortest path", "Cheapest path", "Longest dependent path", "Riskiest path", "C"),
            ],
        ),
        "milestones": [
            ("Submit project charter", "assignment_submit", 0, 15),
            ("Course 70% complete", "course_progress", None, 5),
        ],
    },
    {
        "title": "Software Engineering",
        "description": "Requirements, design, testing and maintainable code.",
        "modules": [
            ("Software process models", "Waterfall, iterative and incremental delivery."),
            ("Requirements engineering", "User stories, use cases and acceptance criteria."),
            ("Architecture styles", "Layered, client-server and REST."),
            ("Testing strategies", "Unit, integration and acceptance testing."),
            ("Version control", "Git branching and code review."),
        ],
        "assignments": [
            ("Assignment 1 — Use case model", "Produce a use-case diagram for Smart ELMS.", 19, 100),
            ("Assignment 2 — Test plan", "Write a test plan covering auth, submit and predict.", 8, 100),
            ("Assignment 3 — Refactor log", "Document three refactors and why they improve quality.", 3, 100),
        ],
        "quiz": (
            "SE checkpoint",
            [
                ("A unit test should…", "Hit the real database", "Exercise one unit in isolation", "Replace the UI", "Train a model", "B"),
                ("REST organises the API around…", "SOAP envelopes", "Resources and HTTP verbs", "Stored procedures", "Sessions only", "B"),
                ("Technical debt is…", "A bank loan", "Future cost of expedient design", "A test framework", "A UML tool", "B"),
            ],
        ),
        "milestones": [
            ("Submit use case model", "assignment_submit", 0, 18),
            ("Attempt SE checkpoint", "quiz_attempt", 0, 8),
        ],
    },
]

FIRST = [
    "Amina", "Bilal", "Chen", "Dina", "Elias", "Farah", "Gabriel", "Hana",
    "Ibrahim", "Jia", "Kofi", "Leila", "Mateo", "Noor", "Omar", "Priya",
    "Quinn", "Ravi", "Sara", "Tariq", "Uma", "Victor", "Wafa", "Yusuf",
    "Zara", "Alex", "Blake", "Carmen", "Dev", "Elena", "Felix", "Grace",
    "Hassan", "Ines", "Jonas", "Kira", "Leo", "Maya", "Nadia", "Owen",
    "Pia", "Rosa", "Samir", "Tina", "Usman", "Vera",
]
LAST = [
    "Ahmed", "Brown", "Chen", "Davies", "Edwards", "Farooq", "Garcia", "Hughes",
    "Iqbal", "Jones", "Khan", "Lewis", "Murphy", "Nguyen", "Okafor", "Patel",
    "Quinn", "Rahman", "Singh", "Taylor",
]


def _hash():
    return bcrypt.generate_password_hash(PASSWORD).decode("utf-8")


def _ensure_model():
    model_path = ROOT / "ai" / "models" / "best_model.pkl"
    if model_path.exists():
        return
    print("Training AI models (first run, about a minute)...")
    from ai.generate_dataset import generate_dataset
    from ai.train_models import train

    df = generate_dataset(n=520)
    df.to_csv(ROOT / "ai" / "data" / "synthetic_students.csv", index=False)
    train(df)


def _persona(kind, rng):
    """kind: strong | mid | weak"""
    if kind == "strong":
        return {
            "login_days": rng.randint(10, 18),
            "inactive": rng.randint(0, 2),
            "module_p": 0.9,
            "submit_p": 0.95,
            "quiz_p": 0.95,
            "score": (78, 12),
            "minutes": (20, 55),
        }
    if kind == "weak":
        return {
            "login_days": rng.randint(1, 5),
            "inactive": rng.randint(7, 14),
            "module_p": 0.28,
            "submit_p": 0.35,
            "quiz_p": 0.4,
            "score": (42, 14),
            "minutes": (2, 12),
        }
    return {
        "login_days": rng.randint(5, 11),
        "inactive": rng.randint(2, 6),
        "module_p": 0.6,
        "submit_p": 0.65,
        "quiz_p": 0.7,
        "score": (62, 14),
        "minutes": (8, 28),
    }


def ensure_demo_alert():
    """Guarantee one assignment is due within 3 days with under 50% submissions."""
    course = Course.query.filter_by(title="Web Development").first()
    if not course or not course.assignments:
        return
    assignment = course.assignments[-1]
    enrolled = Enrollment.query.filter_by(course_id=course.course_id).count() or 1
    submitted = Submission.query.filter_by(assignment_id=assignment.assignment_id).count()
    rate = 100 * submitted / enrolled
    due = assignment.due_date
    now = datetime.now(timezone.utc)
    if due and due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    already = due is not None and 0 <= (due - now).days <= 3 and rate < 50
    if already:
        return
    assignment.due_date = now + timedelta(days=2)
    keep = max(1, int(enrolled * 0.35))
    subs = (
        Submission.query.filter_by(assignment_id=assignment.assignment_id)
        .order_by(Submission.submitted_at)
        .all()
    )
    for extra in subs[keep:]:
        db.session.delete(extra)
    db.session.commit()


def seed_all():
    db.create_all()
    if Teacher.query.filter_by(email="instructor@university.edu").first():
        print("Database already seeded.")
        _ensure_model()
        return

    rng = random.Random(42)
    pw = _hash()

    instructor = Teacher(full_name="Course Instructor", email="instructor@university.edu", password_hash=pw)
    demo = Student(
        full_name="Student User",
        email="student@university.edu",
        password_hash=pw,
        last_login_at=NOW - timedelta(hours=3),
    )
    db.session.add_all([instructor, demo])
    db.session.flush()

    named = [
        ("Student A", "high"),
        ("Student B", "mid"),
        ("Student C", "high"),
        ("Student D", "low"),
    ]
    students = [demo]
    for i, (name, band) in enumerate(named, start=1):
        last_login_days = {"high": 9, "mid": 6, "low": 4}[band]
        if name == "Student C":
            last_login_days = 11
        s = Student(
            full_name=name,
            email=f"student.{name.split()[-1].lower()}@university.edu",
            password_hash=pw,
            last_login_at=NOW - timedelta(days=last_login_days, hours=4),
        )
        db.session.add(s)
        students.append(s)

    used_names = {"Student User", "Student A", "Student B", "Student C", "Student D"}
    while len(students) < 48:
        fname = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if fname in used_names:
            continue
        used_names.add(fname)
        # Mix of personas
        roll = rng.random()
        inactive = 1
        if roll < 0.22:
            inactive = rng.randint(8, 14)
        elif roll < 0.55:
            inactive = rng.randint(3, 7)
        else:
            inactive = rng.randint(0, 2)
        s = Student(
            full_name=fname,
            email=f"s{len(students):03d}.{fname.split()[0].lower()}@university.edu",
            password_hash=pw,
            last_login_at=NOW - timedelta(days=inactive, hours=rng.randint(1, 10)),
        )
        db.session.add(s)
        students.append(s)
    db.session.flush()

    created_courses = []
    for spec in COURSE_DEFS:
        course = Course(title=spec["title"], description=spec["description"], teacher_id=instructor.teacher_id)
        db.session.add(course)
        db.session.flush()
        modules = []
        for idx, (title, content) in enumerate(spec["modules"], start=1):
            m = Module(course_id=course.course_id, title=title, content=content, order_index=idx)
            db.session.add(m)
            modules.append(m)
        assignments = []
        for title, desc, days_ago_due_offset, max_score in spec["assignments"]:
            # mix of past and upcoming due dates — last item often upcoming
            due = NOW + timedelta(days=(7 - days_ago_due_offset))
            a = Assignment(
                course_id=course.course_id,
                title=title,
                description=desc,
                due_date=due,
                max_score=max_score,
            )
            db.session.add(a)
            assignments.append(a)
        db.session.flush()
        qtitle, qitems = spec["quiz"]
        quiz = Quiz(course_id=course.course_id, title=qtitle)
        db.session.add(quiz)
        db.session.flush()
        for prompt, a, b, c, d, correct in qitems:
            db.session.add(
                QuizQuestion(
                    quiz_id=quiz.quiz_id,
                    prompt=prompt,
                    option_a=a,
                    option_b=b,
                    option_c=c,
                    option_d=d,
                    correct_option=correct,
                )
            )
        milestones = []
        for title, rtype, ref_index, days in spec["milestones"]:
            ref = None
            if rtype == "module_access":
                ref = modules[ref_index].module_id
            elif rtype == "assignment_submit":
                ref = assignments[ref_index].assignment_id
            elif rtype == "quiz_attempt":
                ref = quiz.quiz_id
            ms = Milestone(
                course_id=course.course_id,
                title=title,
                description=f"Track {title.lower()} for {course.title}.",
                due_date=NOW + timedelta(days=days),
                requirement_type=rtype,
                requirement_ref_id=ref,
            )
            db.session.add(ms)
            milestones.append(ms)
        created_courses.append(
            {
                "course": course,
                "modules": modules,
                "assignments": assignments,
                "quiz": quiz,
                "spec": spec,
            }
        )
    db.session.flush()

    # Enrol everyone on 3–4 courses. Demo student on all four.
    for student in students:
        if student.email == "student@university.edu":
            chosen = created_courses
        else:
            k = 4 if rng.random() < 0.55 else 3
            chosen = rng.sample(created_courses, k=k)
        for pack in chosen:
            db.session.add(
                Enrollment(student_id=student.student_id, course_id=pack["course"].course_id, progress_percent=0)
            )
    db.session.flush()

    def engage_student(student, pack, persona):
        for module in pack["modules"]:
            if rng.random() > persona["module_p"]:
                continue
            completed = rng.random() < (0.85 if persona["module_p"] > 0.7 else 0.45)
            minutes = rng.randint(*persona["minutes"])
            db.session.add(
                ModuleEngagement(
                    student_id=student.student_id,
                    module_id=module.module_id,
                    time_spent_minutes=minutes,
                    last_accessed=NOW - timedelta(days=rng.randint(0, max(1, persona["inactive"]))),
                    completed=completed,
                )
            )
        for assignment in pack["assignments"]:
            if rng.random() > persona["submit_p"]:
                continue
            due = assignment.due_date
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            late = rng.random() < 0.2
            submitted_at = due - timedelta(days=rng.randint(0, 4)) if not late else due + timedelta(hours=rng.randint(4, 48))
            score_mu, score_sd = persona["score"]
            score = int(max(20, min(100, rng.gauss(score_mu, score_sd))))
            db.session.add(
                Submission(
                    assignment_id=assignment.assignment_id,
                    student_id=student.student_id,
                    submitted_at=submitted_at,
                    score=score,
                    comment="Submitted via Smart ELMS seed data.",
                    file_path=None,
                )
            )
        if rng.random() <= persona["quiz_p"]:
            score_mu, score_sd = persona["score"]
            db.session.add(
                QuizAttempt(
                    quiz_id=pack["quiz"].quiz_id,
                    student_id=student.student_id,
                    score=int(max(20, min(100, rng.gauss(score_mu, score_sd)))),
                    attempted_at=NOW - timedelta(days=rng.randint(1, 12)),
                )
            )

    def login_history(student, persona):
        for _ in range(persona["login_days"]):
            when = NOW - timedelta(days=rng.randint(persona["inactive"], persona["inactive"] + 28))
            dur = rng.randint(8, 75)
            db.session.add(
                LoginActivity(
                    student_id=student.student_id,
                    login_time=when,
                    logout_time=when + timedelta(minutes=dur),
                    duration_minutes=dur,
                )
            )

    # Demo student: crafted to resemble the Figma dashboard
    demo_plan = {
        "Web Development": {"modules": 3, "assignments": 2, "quiz": True, "score": 78},
        "Database Systems": {"modules": 2, "assignments": 1, "quiz": True, "score": 58},
        "Project Management": {"modules": 5, "assignments": 2, "quiz": True, "score": 88},
        "Software Engineering": {"modules": 1, "assignments": 1, "quiz": False, "score": 45},
    }
    for pack in created_courses:
        plan = demo_plan[pack["course"].title]
        for i, module in enumerate(pack["modules"]):
            if i >= plan["modules"]:
                break
            db.session.add(
                ModuleEngagement(
                    student_id=demo.student_id,
                    module_id=module.module_id,
                    time_spent_minutes=25 + i * 8,
                    last_accessed=NOW - timedelta(days=1),
                    completed=True,
                )
            )
        for i, assignment in enumerate(pack["assignments"]):
            if i >= plan["assignments"]:
                continue
            db.session.add(
                Submission(
                    assignment_id=assignment.assignment_id,
                    student_id=demo.student_id,
                    submitted_at=NOW - timedelta(days=4 - i),
                    score=plan["score"] - i * 3,
                    comment="My submission for this assignment.",
                    file_path=None,
                )
            )
        if plan["quiz"]:
            db.session.add(
                QuizAttempt(
                    quiz_id=pack["quiz"].quiz_id,
                    student_id=demo.student_id,
                    score=plan["score"],
                    attempted_at=NOW - timedelta(days=5),
                )
            )
    for d in range(12):
        when = NOW - timedelta(days=d * 2, hours=2)
        db.session.add(
            LoginActivity(
                student_id=demo.student_id,
                login_time=when,
                logout_time=when + timedelta(minutes=40),
                duration_minutes=40,
            )
        )

    # Remaining students
    for student in students:
        if student.email == "student@university.edu":
            continue
        if student.full_name in {"Student A", "Student C"}:
            persona = _persona("weak", rng)
        elif student.full_name == "Student B":
            persona = _persona("mid", rng)
        elif student.full_name == "Student D":
            persona = _persona("strong", rng)
        else:
            roll = rng.random()
            persona = _persona("weak" if roll < 0.28 else "strong" if roll > 0.62 else "mid", rng)
        enrolled_packs = [
            p
            for p in created_courses
            if Enrollment.query.filter_by(student_id=student.student_id, course_id=p["course"].course_id).first()
        ]
        # query in loop is fine for 48 students
        for pack in enrolled_packs:
            engage_student(student, pack, persona)
        login_history(student, persona)

    db.session.commit()

    for enr in Enrollment.query.all():
        recompute_course_progress(enr.student_id, enr.course_id)

    ensure_demo_alert()
    _ensure_model()
    print("Scoring students with the trained model...")
    for student in Student.query.all():
        try:
            predict_for_student(student.student_id)
        except Exception as exc:
            print(f"  skip {student.email}: {exc}")

    print("Seed complete.")
    print("  Instructor  instructor@university.edu   Password123!")
    print("  Student     student@university.edu      Password123!")
