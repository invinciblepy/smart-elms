"""Generate a 500+ record synthetic student dataset for the AI module."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "ai" / "data" / "synthetic_students.csv"


def generate_dataset(n=520, seed=42):
    rng = np.random.default_rng(seed)

    login_frequency = rng.integers(0, 31, size=n)
    avg_assignment_score = np.clip(rng.normal(65, 15, size=n), 0, 100)
    assignment_submission_rate = np.clip(rng.uniform(0, 1, size=n), 0, 1)
    avg_quiz_score = np.clip(rng.normal(60, 20, size=n), 0, 100)
    days_since_last_login = np.clip(rng.exponential(5, size=n), 0, 40).astype(int)
    course_completion_rate = np.clip(rng.uniform(0, 1, size=n), 0, 1)

    # Latent risk score: higher = more at-risk. Tuned for ~30% positive class.
    latent = (
        (15 - login_frequency) / 15 * 0.18
        + (100 - avg_assignment_score) / 100 * 0.22
        + (1 - assignment_submission_rate) * 0.20
        + (100 - avg_quiz_score) / 100 * 0.16
        + np.minimum(days_since_last_login, 20) / 20 * 0.14
        + (1 - course_completion_rate) * 0.10
    )
    latent = latent + rng.normal(0, 0.07, size=n)
    threshold = np.quantile(latent, 0.70)
    at_risk = (latent >= threshold).astype(int)

    df = pd.DataFrame(
        {
            "student_code": [f"SYN{i:04d}" for i in range(1, n + 1)],
            "login_frequency": login_frequency,
            "avg_assignment_score": np.round(avg_assignment_score, 2),
            "assignment_submission_rate": np.round(assignment_submission_rate, 3),
            "avg_quiz_score": np.round(avg_quiz_score, 2),
            "days_since_last_login": days_since_last_login,
            "course_completion_rate": np.round(course_completion_rate, 3),
            "at_risk": at_risk,
        }
    )
    return df


def main(out_path=DEFAULT_OUT, n=520):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df = generate_dataset(n=n)
    df.to_csv(out_path, index=False)
    pos = int(df["at_risk"].sum())
    print(f"Wrote {len(df)} rows to {out_path} ({pos} at-risk, {100 * pos / len(df):.1f}%)")
    return df


if __name__ == "__main__":
    main()
