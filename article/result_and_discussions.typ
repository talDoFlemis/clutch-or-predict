= Results and Discussion

== Predictive Performance Metrics

The trained XGBoost model achieved strong generalization performance on the temporal test set:

- *Test Accuracy:* 82.02% — The model correctly predicted match outcomes with high accuracy on unseen future matches
- *Log Loss:* 0.4412 — The probabilistic predictions exhibited well-calibrated confidence scores, as evidenced by low cross-entropy loss

#figure(
  image("images/confusion_matrix.png", width: 50%),
  caption: [Confusion matrix for test set predictions. Rows represent actual outcomes, columns represent predicted outcomes.],
) <fig-confusion-matrix>

@fig-confusion-matrix demonstrates balanced predictive performance across both classes (Team 1 wins vs. Team 2 wins). The relatively symmetric confusion matrix indicates that the model does not exhibit systematic bias toward predicting either team, a critical property for fair match prediction.

#figure(
  image("images/roc_curve.png", width: 60%),
  caption: [Receiver Operating Characteristic (ROC) curve with Area Under Curve (AUC) metric.],
) <fig-roc-curve>

The ROC curve (@fig-roc-curve) illustrates the model's discrimination ability across various classification thresholds. An AUC significantly above 0.5 (random classifier baseline) confirms that the model successfully learned meaningful patterns distinguishing winning teams from losing teams.

#figure(
  image("images/distr_predicted_prob.png", width: 70%),
  caption: [Distribution of predicted probabilities separated by actual outcome. Blue histogram shows matches where Team 1 won; red histogram shows Team 2 victories.],
) <fig-distr_predicted_prob>

@fig-distr_predicted_prob reveals the model's confidence distribution. Ideally, predicted probabilities should cluster near 0 for Team 1 wins and near 1 for Team 2 wins. The observed separation between distributions indicates that the model produces differentiated confidence estimates rather than converging to indecisive predictions near 0.5.

== Feature Importance and Model Interpretability

Understanding which features drive predictions is essential for validating model behavior and identifying potential biases or data leakage.

#figure(
  image("images/important_feat.png", width: 70%),
  caption: [Top 20 most important features ranked by XGBoost's gain metric, which measures the average improvement in loss contributed by each feature across all decision splits.],
) <fig-important-feat>

@fig-important-feat reveals that Elo ratings dominate the feature importance hierarchy, with `t1_elo` and `t2_elo` ranking as the most influential predictors. This aligns with domain knowledge: Elo ratings encapsulate long-term team strength and recent form, making them natural strong signals for match outcomes.

Beyond Elo, the model heavily weights team-aggregated performance statistics such as:
- *Average Damage per Round (ADR):* Measures consistent firepower output
- *Kill/Death statistics:* Fundamental indicators of mechanical skill
- *KAST percentage:* Captures survivability and trade effectiveness

Notably, *distributional features* (median, P25, P75, standard deviation) appear frequently, suggesting that roster depth and consistency matter beyond simply having high-performing star players. Teams with narrow interquartile ranges (balanced rosters) may exhibit more predictable performance than teams reliant on carry players.

\
\
\
\
\
\
\
\
\

== Explainability via SHAP (SHapley Additive exPlanations)

To move beyond global feature importance and understand *how* features influence individual predictions, we employed SHAP, a game-theoretic framework for model interpretability.

#figure(
  image("images/feature_impact_pred.png", width: 90%),
  caption: [SHAP summary plot showing feature impact on predictions. Each point represents a sample; Position along x-axis shows SHAP value, rightward push toward Team 2 win, leftward push toward Team 1 win.],
) <fig-feature_impact_pred>

@fig-feature_impact_pred provides a global view of feature behavior:
- *Elo disparity:* Higher `t2_elo` (red points) strongly pushes predictions toward Team 2 victory (positive SHAP values), while higher `t1_elo` pushes toward Team 1.
- *Performance metrics:* Features like ADR, kills, and KAST exhibit consistent directional relationships, i.e., higher values for Team 2 increase their win probability.

#figure(
  image("images/indiv_pred.png", width: 90%),
  caption: [SHAP waterfall plot for a high-confidence individual prediction.],
) <fig-indiv-pred>

@fig-indiv-pred demonstrates an individual prediction's decision path. For this particular match, the model identified a significant Elo advantage for one team, reinforced by superior ADR and kill statistics, leading to a high-confidence prediction.

#figure(
  image("images/top_6_important_feat.png", width: 100%),
  caption: [SHAP dependence plots for the top 6 most important features.],
) <fig-top-6-important-feat>

@fig-top-6-important-feat reveals nonlinear relationships and interaction effects:
- *Elo ratings:* Exhibit near-linear SHAP relationships, confirming their role as stable, interpretable strength indicators.
- *Performance statistics:* Display more complex patterns, with interaction effects (color gradients) suggesting that certain features are more predictive in specific contexts (e.g., high ADR matters more when facing lower-Elo opponents).

== Discussion and Limitations

=== Model Selection and Architecture Decisions

During the initial phase of model development, we experimented with an LSTM-embedded neural network architecture to capture temporal dependencies in team performance. The hypothesis was that sequential modeling of match histories could better capture momentum and form trajectories. However, this approach yielded unsatisfying results with a critical flaw: while the LSTM model performed reasonably well on matches between teams of similar competitive tiers (e.g., tier 1 vs. tier 1, tier 3 vs. tier 3), it exhibited systematic failures when predicting cross-tier matchups. Specifically, the model would incorrectly favor tier 3 teams against tier 1 opponents when the lower-tier team had accumulated strong statistical performances against weaker opposition.

Although we were able to empirically identify this failure mode, the precise mechanism driving this behavior remains unclear. We hypothesize that the LSTM may overemphasize short-term performance trends without adequately contextualizing opponent strength, effectively conflating dominance over weaker competition with true competitive parity.

This limitation motivated the adoption of XGBoost with Elo ratings as core features. Elo ratings inherently encode opponent strength through their update mechanism—victories against strong opponents yield larger rating increases than wins against weak teams. By combining Elo (contextual strength assessment) with raw performance statistics, the gradient boosting approach successfully balanced historical form with competitive tier awareness.

\

=== Model Strengths
1. *Temporal validity:* Strict chronological splitting ensures the model is evaluated under realistic deployment conditions.
2. *Interpretability:* SHAP analysis confirms that predictions align with domain knowledge (Elo, ADR, kills).
3. *Calibration:* Low log loss and ROC performance indicate well-calibrated probability estimates suitable for decision-making under uncertainty.
4. *Opponent-aware strength estimation:* Elo integration prevents the inflation of predictions for teams with strong statistics against weak competition.

=== Limitations and Future Work
1. *Roster instability:* The model aggregates player statistics by team but does not track individual player transfers. A roster change mid-season could degrade predictions until sufficient new match data accumulates.
2. *Map-specific strategies:* While map encoding is included, the model treats it as a simple categorical variable. Future work could investigate map-specific Elo ratings or interaction terms.
3. *Sample size for rare events:* Major finals and other high-stakes matches are underrepresented in the dataset. Synthetic oversampling or importance re-weighting strategies could mitigate this.

Despite these limitations, the model demonstrates that it can effectively leverage historical match data to produce actionable predictions for Counter-Strike 2 esports outcomes.

\
