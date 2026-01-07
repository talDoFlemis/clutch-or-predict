#import "@preview/bloated-neurips:0.7.0": botrule, midrule, neurips2025, paragraph, toprule, url
#import "./logo.typ": LaTeX, LaTeXe, TeX

#let affls = (
  ufc: (
    department: "Department of Computer Science",
    institution: "Federal University of Ceará",
    location: "Fortaleza",
    country: "Brazil",
  ),
)

#let authors = (
  (name: "Erik Bayerlein", affl: "ufc", email: "erik.bayerlein@alu.ufc.br", equal: true),
  (name: "Said C. Rodrigues", affl: "ufc", email: "saidrodrigues@alu.ufc.br", equal: true),
)

#show: neurips2025.with(
  title: [Predicting Counter-Strike Matches using a XGBoost Model],
  authors: (authors, affls),
  keywords: ("Machine Learning", "NeurIPS"),
  abstract: [
    Predicting outcomes in professional esports presents unique challenges due to the high-dimensional, heterogeneous nature of match data and the non-stationary dynamics of team performance. In this work, we propose a robust machine learning framework for forecasting Counter-Strike match winners using Extreme Gradient Boosting (XGBoost). Unlike traditional approaches that rely on random cross-validation, we employ a strict temporal train-test split strategy to eliminate look-ahead bias, ensuring that the model is evaluated solely on future unseen data. The model is optimized using Randomized Search with time-series cross-validation, specifically targeting negative log-loss to maximize probability calibration, a critical requirement for confidence, weighted applications such as betting markets. Our results reinforce recent empirical findings that tree-based architectures continue to outperform deep learning baselines on tabular esports data, providing a scalable, interpretable, and mathematically sound prediction system.
  ],
  bibliography: bibliography("main.bib"),
  bibliography-opts: (title: none, full: true),
  // appendix: [
  //   #include "appendix.typ"
  //   #include "checklist.typ"
  // ],
  accepted: true,
)

#include "introduction.typ"

#include "data.typ"

#include "model_training.typ"

#include "result_and_discussions.typ"

#include "future_work.typ"

#include "ack.typ"

#include "participation.typ"


#heading(numbering: none)[References]