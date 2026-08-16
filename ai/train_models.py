"""Train Decision Tree and Logistic Regression models, pick the best, serialise it."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree

from ai.generate_dataset import generate_dataset

DATA_PATH = ROOT / "ai" / "data" / "synthetic_students.csv"
MODEL_PATH = ROOT / "ai" / "models" / "best_model.pkl"
ARTEFACT = ROOT / "ai" / "artefacts"
FEATURE_COLS = [
    "login_frequency",
    "avg_assignment_score",
    "assignment_submission_rate",
    "avg_quiz_score",
    "days_since_last_login",
    "course_completion_rate",
]


def _metrics(y_true, y_pred, y_proba):
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        "roc_auc": round(float(roc_auc_score(y_true, y_proba)), 4),
    }


def run_eda(df: pd.DataFrame):
    ARTEFACT.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")

    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    for ax, col in zip(axes.ravel(), FEATURE_COLS):
        sns.histplot(df, x=col, hue="at_risk", ax=ax, bins=18, palette=["#3B6FF5", "#DC2626"], alpha=0.75)
        ax.set_title(col.replace("_", " "))
    fig.tight_layout()
    fig.savefig(ARTEFACT / "eda_distributions.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 5))
    corr = df[FEATURE_COLS + ["at_risk"]].corr()
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="Blues", ax=ax)
    ax.set_title("Feature correlation matrix")
    fig.tight_layout()
    fig.savefig(ARTEFACT / "eda_correlation.png", dpi=140)
    plt.close(fig)

    balance = df["at_risk"].value_counts(normalize=True).to_dict()
    return {"class_balance": {str(k): round(float(v), 3) for k, v in balance.items()}}


def train(df: pd.DataFrame | None = None):
    ARTEFACT.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

    if df is None:
        if DATA_PATH.exists():
            df = pd.read_csv(DATA_PATH)
        else:
            df = generate_dataset()
            df.to_csv(DATA_PATH, index=False)

    eda = run_eda(df)
    X = df[FEATURE_COLS]
    y = df["at_risk"].astype(int)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    dt_pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", DecisionTreeClassifier(random_state=42)),
        ]
    )
    dt_grid = GridSearchCV(
        dt_pipe,
        {
            "clf__max_depth": [3, 5, 7, 10],
            "clf__min_samples_split": [2, 5, 10],
        },
        scoring="recall",
        cv=cv,
        n_jobs=1,
    )
    dt_grid.fit(X_train, y_train)

    lr_pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=400, random_state=42)),
        ]
    )
    lr_grid = GridSearchCV(
        lr_pipe,
        {
            "clf__C": [0.01, 0.1, 1, 10],
            "clf__solver": ["lbfgs", "liblinear"],
        },
        scoring="recall",
        cv=cv,
        n_jobs=1,
    )
    lr_grid.fit(X_train, y_train)

    candidates = {
        "decision_tree": dt_grid,
        "logistic_regression": lr_grid,
    }
    report = {"eda": eda, "models": {}}
    best_name = None
    best_score = -1
    best_est = None

    for name, grid in candidates.items():
        proba = grid.predict_proba(X_test)[:, 1]
        pred = (proba >= 0.5).astype(int)
        metrics = _metrics(y_test, pred, proba)
        # Prefer recall (proposal), then F1, then ROC-AUC
        rank = metrics["recall"] * 2 + metrics["f1"] + metrics["roc_auc"]
        report["models"][name] = {
            "best_params": grid.best_params_,
            "cv_best_recall": round(float(grid.best_score_), 4),
            "test": metrics,
            "rank_score": round(float(rank), 4),
        }
        if rank > best_score:
            best_score = rank
            best_name = name
            best_est = grid.best_estimator_

    report["selected_model"] = best_name
    report["selection_reason"] = (
        "Selected the model with the highest combined recall (weighted 2x), F1 and ROC-AUC "
        "on the held-out 20% test set, matching the proposal's emphasis on not missing at-risk students."
    )

    joblib.dump(
        {
            "pipeline": best_est,
            "model_name": best_name,
            "features": FEATURE_COLS,
            "metrics": report["models"][best_name]["test"],
        },
        MODEL_PATH,
    )

    # Interpretability artefacts
    dt_clf = dt_grid.best_estimator_.named_steps["clf"]
    fig, ax = plt.subplots(figsize=(14, 8))
    plot_tree(
        dt_clf,
        feature_names=FEATURE_COLS,
        class_names=["not_at_risk", "at_risk"],
        filled=True,
        max_depth=4,
        fontsize=8,
        ax=ax,
    )
    ax.set_title("Decision Tree (top levels)")
    fig.tight_layout()
    fig.savefig(ARTEFACT / "tree.png", dpi=140)
    plt.close(fig)
    (ARTEFACT / "tree.txt").write_text(export_text(dt_clf, feature_names=FEATURE_COLS), encoding="utf-8")

    lr_clf = lr_grid.best_estimator_.named_steps["clf"]
    coefs = lr_clf.coef_[0]
    order = np.argsort(np.abs(coefs))[::-1]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = ["#DC2626" if coefs[i] > 0 else "#3B6FF5" for i in order]
    ax.barh([FEATURE_COLS[i].replace("_", " ") for i in order][::-1], coefs[order][::-1], color=colors[::-1])
    ax.set_xlabel("Coefficient (positive → higher at-risk probability)")
    ax.set_title("Logistic Regression feature coefficients")
    fig.tight_layout()
    fig.savefig(ARTEFACT / "coefficients.png", dpi=140)
    plt.close(fig)

    (ARTEFACT / "model_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Saved model to {MODEL_PATH}")
    return report


if __name__ == "__main__":
    train()
