#import "@preview/bloated-neurips:0.7.0": botrule, midrule, toprule

= Model Training

== Temporal Train-Test Split Strategy

To ensure realistic out-of-sample evaluation, we employ a strict temporal split rather than random shuffling. All matches occurring on or before November 30, 2025, constitute the training set, while matches after this date serve as the test set. This mimics real-world deployment where the model must predict future matches based solely on historical data, preventing any form of temporal leakage. @cerqueira2020evaluating

This chronological partitioning yielded:
- *Training Set:* Historical matches (≤ 2025-11-30)
- *Test Set:* Future matches (> 2025-11-30)

== Feature Selection and Preprocessing

Prior to model training, we conducted a preliminary feature analysis to identify features that could negatively impact generalization performance. Two feature categories were excluded:

1. *Swing Statistics:* These metrics exhibited high multicollinearity with other performance indicators without contributing additional predictive power. @muthukrishnan2024effect
2. *Rating 3.0 Metrics:* While conceptually valuable, Rating 3.0 is a composite metric already incorporating kills, deaths, and utility usage. To avoid feature redundancy and preserve model interpretability, we relied on the constituent raw statistics instead.

After feature pruning, the final input space comprised 140 features (70 per team), plus Elo ratings, map encoding, and event weight.

== Model Architecture: XGBoost Classifier

We selected *XGBoost* (Extreme Gradient Boosting) as our primary modeling framework due to its demonstrated superiority in structured/tabular prediction tasks. XGBoost's gradient-boosted decision trees provide several advantages over deep learning alternatives for this domain. @grinsztajn2022tree
\

The model was configured with the following base parameters:
- *Objective:* `binary:logistic` (binary classification with probability output)
- *Evaluation Metric:* `logloss` (cross-entropy loss)
- *Random State:* 42 (reproducibility)

== Hyperparameter Optimization

To identify the optimal model configuration, we performed *Randomized Search Cross-Validation* with a time-series aware splitting strategy. @bischl2023hyperparameter Standard k-fold cross-validation violates temporal ordering assumptions; instead, we employed `TimeSeriesSplit` with 5 folds, ensuring that each validation fold contains only data chronologically subsequent to its training fold. @hyndman2018forecasting

The hyperparameter search space encompassed 50 random configurations sampled from:

#figure(
  caption: [Hyperparameter search space for XGBoost optimization.],
  table(
    columns: (1fr, 2fr),
    align: left + horizon,
    stroke: none,
    toprule,
    table.header([Parameter], [Search Space]),
    midrule,
    [`n_estimators`], [[100, 300, 500, 800, 1000]],
    [`learning_rate`], [[0.001, 0.005, 0.01, 0.03, 0.05, 0.1]],
    [`max_depth`], [[3, 4, 5, 6, 8]],
    [`min_child_weight`], [[1, 3, 5, 7]],
    [`gamma`], [[0, 0.1, 0.2]],
    [`subsample`], [[0.6, 0.7, 0.8]],
    [`colsample_bytree`], [[0.4, 0.5, 0.6]],
    [`reg_alpha` (L1)], [[0, 0.1, 1]],
    [`reg_lambda` (L2)], [[1, 2, 4, 5]],
    botrule,
  ),
) <tab-hyperparameter-search>

The optimization objective was *negative log loss* (cross-entropy), which directly penalizes poorly calibrated probability estimates, being critical for a prediction system intended for probabilistic betting or confidence-weighted recommendations. @ziyin2019deepgamblerslearningabstain

After evaluating 50 random configurations, the best-performing hyperparameter combination was:

#figure(
  caption: [Optimal hyperparameters identified through randomized search.],
  table(
    columns: (1fr, 1fr),
    align: left + horizon,
    stroke: none,
    toprule,
    table.header([Parameter], [Optimal Value]),
    midrule,
    [`n_estimators`], [800],
    [`learning_rate`], [0.01],
    [`max_depth`], [4],
    [`min_child_weight`], [3],
    [`gamma`], [0.2],
    [`subsample`], [0.8],
    [`colsample_bytree`], [0.5],
    [`reg_alpha` (L1)], [0],
    [`reg_lambda` (L2)], [4],
    botrule,
  ),
) <tab-optimal-hyperparameters>

These parameters strike a balance between model complexity and regularization: the moderate `max_depth` of 4 prevents overfitting to noisy patterns, while the large ensemble size (800 trees) with conservative learning rate (0.01) allows gradual convergence. The high L2 regularization (`reg_lambda=4`) combined with no L1 penalty suggests that retaining all features with smoothed coefficients outperforms aggressive feature selection.

Critically, we incorporated *sample weighting* during training using the previously engineered `event_weight` feature. This ensures that high-importance matches (e.g., Major finals) contribute proportionally more to the loss function than low-stakes qualifiers, effectively teaching the model to prioritize patterns from competitive equilibrium states.

== Model Persistence and Deployment

The best-performing model was serialized using *MLflow*. The exported artifact includes:

- *Model binary:* Native XGBoost booster object
- *Input schema:* Feature names, types, and example inputs
- *Conda environment specification:* Reproducible dependency snapshot
- *Metadata:* Training date, hyperparameters, validation metrics

This MLflow-compatible format enables seamless integration with production inference pipelines, A/B testing frameworks, and model monitoring systems.