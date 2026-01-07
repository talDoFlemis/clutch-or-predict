= Future Work

While the current XGBoost model demonstrates strong predictive performance, several promising directions could further enhance accuracy and robustness for real-world deployment.

== Continuous Model Retraining

The esports landscape evolves rapidly, new teams emerge, rosters change, and the competitive meta shifts with game updates. To maintain prediction accuracy over time, we propose implementing a continuous retraining pipeline, implementing monitoring systems that detect when model performance degrades below acceptable thresholds (e.g., accuracy drops, calibration worsens), automatically triggering retraining procedures.


== Revisiting LSTM-Based Neural Networks

The initial LSTM implementation failed due to its inability to contextualize performance statistics against opponent strength. However, this architecture class remains promising.

== Additional Enhancement Directions

1. *Player-Level Tracking:* Build a database linking individual players to teams over time, allowing the model to account for roster changes by aggregating player-level Elo and performance histories.

2. *Map-Specific Models:* Train separate sub-models for each map, capturing map-specific strategies, team preferences, and ban/pick patterns in best-of-three series.

3. *Ensemble Methods:* Combine XGBoost predictions with LSTM outputs through weighted averaging or stacking, leveraging XGBoost's Elo-aware strength assessment and LSTM's temporal pattern recognition.

By pursuing these directions, particularly the continuous retraining pipeline and redesigned LSTM architecture, the model could evolve from a static prediction tool into an adaptive system capable of capturing both long-term team strength and short-term competitive dynamics.