from datetime import datetime, timezone

from app.extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class Teacher(db.Model):
    __tablename__ = "teacher"

    teacher_id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    courses = db.relationship("Course", back_populates="teacher", lazy=True)

    def to_public(self):
        return {
            "id": self.teacher_id,
            "full_name": self.full_name,
            "email": self.email,
            "role": "instructor",
        }


class Student(db.Model):
    __tablename__ = "student"

    student_id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime)

    enrollments = db.relationship("Enrollment", back_populates="student", lazy=True)
    submissions = db.relationship("Submission", back_populates="student", lazy=True)
    login_activities = db.relationship("LoginActivity", back_populates="student", lazy=True)
    predictions = db.relationship(
        "Prediction", back_populates="student", lazy=True, order_by="Prediction.created_at.desc()"
    )

    def to_public(self):
        return {
            "id": self.student_id,
            "full_name": self.full_name,
            "email": self.email,
            "role": "student",
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }


class Course(db.Model):
    __tablename__ = "course"

    course_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.teacher_id"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    teacher = db.relationship("Teacher", back_populates="courses")
    enrollments = db.relationship("Enrollment", back_populates="course", lazy=True, cascade="all, delete-orphan")
    modules = db.relationship(
        "Module", back_populates="course", lazy=True, order_by="Module.order_index", cascade="all, delete-orphan"
    )
    assignments = db.relationship("Assignment", back_populates="course", lazy=True, cascade="all, delete-orphan")
    quizzes = db.relationship("Quiz", back_populates="course", lazy=True, cascade="all, delete-orphan")
    milestones = db.relationship("Milestone", back_populates="course", lazy=True, cascade="all, delete-orphan")

    def to_dict(self, extra=None):
        data = {
            "course_id": self.course_id,
            "title": self.title,
            "description": self.description,
            "teacher_id": self.teacher_id,
            "instructor": self.teacher.full_name if self.teacher else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "module_count": len(self.modules) if self.modules is not None else 0,
        }
        if extra:
            data.update(extra)
        return data


class Enrollment(db.Model):
    __tablename__ = "enrollment"

    student_id = db.Column(db.Integer, db.ForeignKey("student.student_id"), primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.course_id"), primary_key=True)
    enrolled_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    progress_percent = db.Column(db.Integer, default=0)

    student = db.relationship("Student", back_populates="enrollments")
    course = db.relationship("Course", back_populates="enrollments")

    __table_args__ = (
        db.CheckConstraint("progress_percent >= 0 AND progress_percent <= 100", name="ck_progress_range"),
    )


class Module(db.Model):
    __tablename__ = "module"

    module_id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.course_id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)
    order_index = db.Column(db.Integer, nullable=False)

    course = db.relationship("Course", back_populates="modules")
    engagements = db.relationship("ModuleEngagement", back_populates="module", lazy=True, cascade="all, delete-orphan")

    def to_dict(self, status=None, time_spent=0):
        return {
            "module_id": self.module_id,
            "course_id": self.course_id,
            "title": self.title,
            "content": self.content,
            "order_index": self.order_index,
            "status": status,
            "time_spent_minutes": time_spent,
        }


class Assignment(db.Model):
    __tablename__ = "assignment"

    assignment_id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.course_id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    max_score = db.Column(db.Integer, default=100)

    course = db.relationship("Course", back_populates="assignments")
    submissions = db.relationship("Submission", back_populates="assignment", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "assignment_id": self.assignment_id,
            "course_id": self.course_id,
            "course_title": self.course.title if self.course else None,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "max_score": self.max_score,
        }


class Submission(db.Model):
    __tablename__ = "submission"

    submission_id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("assignment.assignment_id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.student_id"), nullable=False)
    submitted_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    score = db.Column(db.Integer)
    file_path = db.Column(db.String(500))
    comment = db.Column(db.Text)

    assignment = db.relationship("Assignment", back_populates="submissions")
    student = db.relationship("Student", back_populates="submissions")

    __table_args__ = (db.UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student"),)

    def to_dict(self):
        return {
            "submission_id": self.submission_id,
            "assignment_id": self.assignment_id,
            "student_id": self.student_id,
            "student_name": self.student.full_name if self.student else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "score": self.score,
            "file_path": self.file_path,
            "comment": self.comment,
            "max_score": self.assignment.max_score if self.assignment else 100,
            "assignment_title": self.assignment.title if self.assignment else None,
        }


class LoginActivity(db.Model):
    __tablename__ = "login_activity"

    activity_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.student_id"), nullable=False)
    login_time = db.Column(db.DateTime, nullable=False)
    logout_time = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Integer)

    student = db.relationship("Student", back_populates="login_activities")


class ModuleEngagement(db.Model):
    __tablename__ = "module_engagement"

    engagement_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.student_id"), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey("module.module_id"), nullable=False)
    time_spent_minutes = db.Column(db.Integer, default=0)
    last_accessed = db.Column(db.DateTime)
    completed = db.Column(db.Boolean, default=False)

    module = db.relationship("Module", back_populates="engagements")
    student = db.relationship("Student")

    __table_args__ = (db.UniqueConstraint("student_id", "module_id", name="uq_student_module"),)


class Quiz(db.Model):
    __tablename__ = "quiz"

    quiz_id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.course_id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    course = db.relationship("Course", back_populates="quizzes")
    questions = db.relationship("QuizQuestion", back_populates="quiz", lazy=True, cascade="all, delete-orphan")
    attempts = db.relationship("QuizAttempt", back_populates="quiz", lazy=True, cascade="all, delete-orphan")

    def to_dict(self, include_answers=False):
        return {
            "quiz_id": self.quiz_id,
            "course_id": self.course_id,
            "course_title": self.course.title if self.course else None,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "question_count": len(self.questions),
            "questions": [q.to_dict(include_answers=include_answers) for q in self.questions],
        }


class QuizQuestion(db.Model):
    __tablename__ = "quiz_question"

    question_id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.quiz_id"), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(300), nullable=False)
    option_b = db.Column(db.String(300), nullable=False)
    option_c = db.Column(db.String(300), nullable=False)
    option_d = db.Column(db.String(300), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)

    quiz = db.relationship("Quiz", back_populates="questions")

    def to_dict(self, include_answers=False):
        data = {
            "question_id": self.question_id,
            "prompt": self.prompt,
            "option_a": self.option_a,
            "option_b": self.option_b,
            "option_c": self.option_c,
            "option_d": self.option_d,
        }
        if include_answers:
            data["correct_option"] = self.correct_option
        return data


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempt"

    attempt_id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quiz.quiz_id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.student_id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    attempted_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    quiz = db.relationship("Quiz", back_populates="attempts")
    student = db.relationship("Student")

    def to_dict(self):
        return {
            "attempt_id": self.attempt_id,
            "quiz_id": self.quiz_id,
            "quiz_title": self.quiz.title if self.quiz else None,
            "course_title": self.quiz.course.title if self.quiz and self.quiz.course else None,
            "student_id": self.student_id,
            "score": self.score,
            "attempted_at": self.attempted_at.isoformat() if self.attempted_at else None,
        }


class Milestone(db.Model):
    __tablename__ = "milestone"

    milestone_id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.course_id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime)
    requirement_type = db.Column(db.String(40), nullable=False, default="manual")
    requirement_ref_id = db.Column(db.Integer)

    course = db.relationship("Course", back_populates="milestones")

    def to_dict(self, extra=None):
        data = {
            "milestone_id": self.milestone_id,
            "course_id": self.course_id,
            "course_title": self.course.title if self.course else None,
            "title": self.title,
            "description": self.description,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "requirement_type": self.requirement_type,
            "requirement_ref_id": self.requirement_ref_id,
        }
        if extra:
            data.update(extra)
        return data


class Prediction(db.Model):
    __tablename__ = "prediction"

    prediction_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.student_id"), nullable=False)
    at_risk = db.Column(db.Boolean, nullable=False)
    probability = db.Column(db.Float, nullable=False)
    risk_level = db.Column(db.String(20), nullable=False)
    login_frequency = db.Column(db.Integer)
    avg_assignment_score = db.Column(db.Float)
    assignment_submission_rate = db.Column(db.Float)
    avg_quiz_score = db.Column(db.Float)
    days_since_last_login = db.Column(db.Integer)
    course_completion_rate = db.Column(db.Float)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    student = db.relationship("Student", back_populates="predictions")

    def to_dict(self):
        return {
            "prediction_id": self.prediction_id,
            "student_id": self.student_id,
            "at_risk": self.at_risk,
            "probability": round(self.probability, 4),
            "risk_level": self.risk_level,
            "features": {
                "login_frequency": self.login_frequency,
                "avg_assignment_score": self.avg_assignment_score,
                "assignment_submission_rate": self.assignment_submission_rate,
                "avg_quiz_score": self.avg_quiz_score,
                "days_since_last_login": self.days_since_last_login,
                "course_completion_rate": self.course_completion_rate,
            },
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
