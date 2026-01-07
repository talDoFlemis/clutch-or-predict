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
  title: [Predicting Counter-Strike Matches using Machine Learning Models],
  authors: (authors, affls),
  keywords: ("Machine Learning", "NeurIPS"),
  abstract: [
    TODO
    #lorem(30)
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