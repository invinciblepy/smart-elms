# Smart ELMS

**A Smart E-Learning Management System with AI-Based Predictive Analytics for Early Identification of At-Risk Students**

University of the West of Scotland · MSc IT · Group 34

| Member | Component |
| --- | --- |
| Mohammad Hafeez (B01827888) | Frontend — HTML5, CSS3, vanilla JavaScript |
| Muhammad Hashaam Khan (B01825963) | Backend — Flask, SQLAlchemy, SQLite, JWT |
| Aqsa Shoukat (B01829432) | Progress tracking — pandas, matplotlib, seaborn |
| Malik Rashid Mehmood (B01811454) | AI module — scikit-learn Decision Tree + Logistic Regression |

This is an academic demonstration. All student records are **synthetic**. No real student data is stored.

The planned application is complete: student and instructor journeys, REST API, five chart types, AI risk prediction, and automated tests.

## Run locally

```bash
cd smart-elms
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python app.py
```

First start creates the SQLite database, trains the two models (about a minute), and seeds demo data.

Open http://127.0.0.1:5000

| Role | Email | Password |
| --- | --- | --- |
| Student | student@university.edu | Password123! |
| Instructor | instructor@university.edu | Password123! |

You can also register a new student or instructor from the Create account page. Forgot password is on `/forgot` (demonstration reminder only; no email is sent).

Typical demo path:

1. Sign in as the student. The dashboard shows courses, upcoming deadlines, and a non-threatening AI banner when risk is elevated.
2. Open a course, complete a module, submit Assignment 3 (PDF, DOCX or TXT, max 10 MB), then check the confirmation page.
3. Take a quiz and open Grades / Progress.
4. Sign out and sign in as the instructor. The dashboard lists deadline alerts and students needing attention.
5. Open My Classes to add modules, assignments and quizzes, then grade a submission and download the file.
6. Edit or delete a milestone. Open Alerts, Reports (five chart types plus model plots), and a student profile. Use **Refresh AI prediction** on the profile.

Remember me issues a 14-day JWT. A normal sign-in lasts 24 hours.

## Useful commands

```bash
flask --app app seed          # rebuild demo data (delete instance/smart_elms.db first)
python ai/generate_dataset.py
python ai/train_models.py
pytest -q
```

## What is implemented

- Login / register (student or instructor), remember me, forgot-password help page, bcrypt + JWT
- Student dashboard with course search, upcoming deadlines, and an AI reminder that links to Support
- Courses, modules, assignment submit (PDF/DOCX/TXT ≤ 10 MB) with confirmation page
- Quizzes, grades, progress, support
- Instructor dashboard, class management, quiz builder, assignment grading and file download
- Student list with search, per-student profile, High / Medium / Low risk
- Milestone create / edit (title, description, due date, requirement) / delete and completion %
- Yellow deadline alerts (due in 3 days or less and submission rate under 50%), red performance alerts (missed deadline or score below 70), and disengaged-student flags
- Five matplotlib/seaborn chart types plus Decision Tree and coefficient plots
- 520-row synthetic dataset, EDA artefacts, Decision Tree + Logistic Regression with GridSearchCV, `/api/predict`
- Predict-on-login for students and refresh from the instructor profile
- WCAG-minded markup: skip links, labelled fields, keyboard-usable file dropzone, focus outlines, responsive breakpoints at 320 / 768 / 1024 / 1440

## REST API (prefix `/api` unless noted)

### Auth
| Method | Path | Role |
| --- | --- | --- |
| POST | `/api/auth/register` | public |
| POST | `/api/auth/login` | public |
| POST | `/api/auth/forgot-password` | public |
| POST | `/api/auth/logout` | any signed-in user |
| GET | `/api/auth/me` | any signed-in user |

### Courses and modules
| Method | Path | Role |
| --- | --- | --- |
| GET | `/api/courses` | student or instructor |
| POST | `/api/courses` | instructor |
| GET / PUT / DELETE | `/api/courses/<id>` | instructor (write) |
| POST | `/api/courses/<id>/enroll` | student |
| GET / POST | `/api/courses/<id>/modules` | both / instructor |
| GET / PUT / DELETE | `/api/modules/<id>` | both / instructor |
| POST | `/api/modules/<id>/access` | student |
| POST | `/api/modules/<id>/complete` | student |

### Assignments, quizzes, milestones
| Method | Path | Role |
| --- | --- | --- |
| GET / POST | `/api/courses/<id>/assignments` | both / instructor |
| GET | `/api/assignments/<id>` | both |
| POST | `/api/assignments/<id>/submit` | student |
| PUT | `/api/submissions/<id>/score` | instructor |
| GET | `/api/student/assignments` | student |
| GET | `/api/student/grades` | student |
| GET | `/api/uploads/<filename>` | owner or class instructor |
| GET / POST | `/api/courses/<id>/quizzes` | both / instructor |
| GET | `/api/quizzes/<id>` | both |
| POST | `/api/quizzes/<id>/attempt` | student |
| GET | `/api/student/quizzes` | student |
| GET / POST | `/api/courses/<id>/milestones` | both / instructor |
| GET | `/api/milestones` | instructor |
| PUT / DELETE | `/api/milestones/<id>` | instructor |

### Analytics and AI
| Method | Path | Role |
| --- | --- | --- |
| GET | `/api/analytics/dashboard/student` | student |
| GET | `/api/analytics/dashboard/instructor` | instructor |
| GET | `/api/analytics/completions` | instructor |
| GET | `/api/analytics/quiz-scores` | instructor |
| GET | `/api/analytics/logins` | instructor |
| GET | `/api/analytics/students/<id>` | instructor |
| GET | `/api/analytics/milestones` | instructor |
| GET | `/api/analytics/alerts` | instructor |
| GET | `/api/analytics/charts/<name>` | instructor |
| POST | `/api/predict` | signed-in |
| POST | `/api/predict/refresh/<student_id>` | instructor |
| GET | `/api/predict/students` | instructor |
| GET | `/api/instructor/students` | instructor |
| GET | `/api/instructor/classes/<id>/roster` | instructor |
| GET | `/health` | public |

Chart names: `completions`, `score_trend`, `heatmap`, `histogram`, `milestones`, `tree`, `coefficients`.

Send `Authorization: Bearer <token>` on protected routes. Missing or invalid tokens return **401**. Role mismatches return **403**.

## Project layout

```
app/            Flask factory, models, REST blueprints
ai/             Dataset generation, training, notebook, artefacts
frontend/       Static HTML/CSS/JS (no React / Vue)
tests/          pytest + Flask test client
docs/           Accessibility notes for the frontend component
```

## Accessibility notes

See `docs/accessibility.md`. Automated WAVE / Lighthouse scores should be captured in the browser before the professor demo and pasted into the final report screenshot slots.
