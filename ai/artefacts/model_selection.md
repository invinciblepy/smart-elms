# Model selection

Both a Decision Tree and Logistic Regression were trained on 520 synthetic rows with an 80/20 stratified split and GridSearchCV (5-fold, scoring recall).

| Model | Accuracy | Precision | Recall | F1 | ROC AUC |
| --- | --- | --- | --- | --- | --- |
| Decision Tree | 0.76 | 0.57 | 0.77 | 0.66 | 0.80 |
| Logistic Regression | 0.91 | 0.84 | 0.87 | 0.86 | 0.97 |

Winner: Logistic Regression. Recall of the at-risk class was weighted more heavily because a missed at-risk student never receives support. ROC AUC and F1 agreed with that choice.

SMOTE was not used. The generated label rate is already about 30 percent.

Artefacts: `tree.png`, `coefficients.png`, `best_model.pkl`.
