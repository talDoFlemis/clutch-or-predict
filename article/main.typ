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
  title: [Counter-Strike 2 Match Prediction: From Web Scraping to XGBoost Model Development],
  authors: (authors, affls),
  keywords: ("Machine Learning", "Esports Analytics", "Web Scraping", "XGBoost", "SHAP"),
  abstract: [
    Accurate forecasting in professional esports is hindered by data scarcity and the non-stationary dynamics of team performance. This work presents an end-to-end machine learning framework for Counter-Strike 2 (CS2) match prediction. Addressing the lack of public benchmarks, we implemented a distributed data acquisition infrastructure with robust WAF evasion, compiling a novel dataset of 20,309 professional matches across 1,378 events. We introduce a feature engineering pipeline that synthesizes dynamic Elo ratings with event-weighted performance statistics and distributional team metrics. Leveraging an XGBoost architecture optimized for tabular data, our model achieves strong predictive performance under a strict temporal evaluation protocol designed to eliminate look-ahead bias. Furthermore, SHAP-based interpretability analysis reveals that while Elo ratings drive global predictive stability, granular performance metrics exhibit complex contextual interaction effects, offering new insights into the determinants of competitive success.
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