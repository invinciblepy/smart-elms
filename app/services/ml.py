from pathlib import Path

import joblib
import pandas as pd

from config import Config
from app.extensions import db
from app.models import Prediction, Student
from app.services.engagement import student_features
from app.utils import risk_level_from_probability

FEATURES = [
    ("login_frequency", 0, 60),
    ("avg_assignment_score", 0, 100),
    ("assignment_submission_rate", 0, 1),
    ("avg_quiz_score", 0, 100),
    ("days_since_last_login", 0, 60),
    ("course_completion_rate", 0, 1),
]

FEATURE_ORDER = [name for name, _, _ in FEATURES]


def _model_path():
    return Path(Config.AI_MODEL_PATH)


_BUNDLE = None


def load_bundle():
    global _BUNDLE
    if _BUNDLE is not None:
        return _BUNDLE
    path = _model_path()
    if not path.exists():
        raise FileNotFoundError("Trained model not found. Run seed or ai/train_models.py first.")
    _BUNDLE = joblib.load(path)
    return _BUNDLE


def predict_features(feature_dict):
    bundle = load_bundle()
    pipeline = bundle["pipeline"]
    vector = pd.DataFrame(
        [[float(feature_dict[name]) for name in FEATURE_ORDER]],
        columns=FEATURE_ORDER,
    )
    proba_ok = hasattr(pipeline, "predict_proba")
    if proba_ok:
        probability = float(pipeline.predict_proba(vector)[0][1])
        at_risk = bool(probability >= 0.5)
    else:
        label = int(pipeline.predict(vector)[0])
        at_risk = bool(label == 1)
        probability = 0.85 if at_risk else 0.15
    return {
        "at_risk": at_risk,
        "probability": round(probability, 4),
        "risk_level": risk_level_from_probability(probability, at_risk),
        "model_name": bundle.get("model_name", "unknown"),
        "features": {k: feature_dict[k] for k in FEATURE_ORDER},
    }


def predict_for_student(student_id):
    student = db.session.get(Student, student_id)
    if not student:
        raise ValueError("Student not found")
    features = student_features(student_id)
    result = predict_features(features)
    pred = Prediction(
        student_id=student_id,
        at_risk=result["at_risk"],
        probability=result["probability"],
        risk_level=result["risk_level"],
        login_frequency=features["login_frequency"],
        avg_assignment_score=features["avg_assignment_score"],
        assignment_submission_rate=features["assignment_submission_rate"],
        avg_quiz_score=features["avg_quiz_score"],
        days_since_last_login=features["days_since_last_login"],
        course_completion_rate=features["course_completion_rate"],
    )
    db.session.add(pred)
    db.session.commit()
    return pred.to_dict()
