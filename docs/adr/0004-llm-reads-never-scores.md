# Language models read and explain; they never produce the lead score

Language models have three jobs: drafting the formatter's mapping from redacted column profiles for a person to
confirm; explaining a lead's score in plain words from the model's own contributions; and, as a measured
experiment, reading messy text into category judgments that the scoring model may use as features, each
admitted only if its learned weight holds up. On the way in that text is the lead's own free-text answers, plus
checks for spam, bots, duplicates and fake contact details; on the way back it is the advertiser's sales notes and
loss reasons, which inform stage scores and help separate a poor lead from a poorly handled one. They never output the lead score, because that must be a
calibrated, reproducible, testable prediction of winning learned from outcomes, and a model's reading of a lead
is none of those.

Claude Haiku 4.5 is the default for drafting and explaining. For judgments, Haiku 4.5 and TypeSafe's Jev (a
non-generative typed-decision model with calibrated confidences, faster and cheaper) are compared on the same
lead texts. Every provider sits behind one interface so it can be swapped.

## Considered options

- LLM as the scorer (lead in, score out): rejected, not a calibrated probability of winning and not
  reproducible. Revisit only with evidence from a real advertiser's data.
