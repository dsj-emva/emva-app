# Each transition is learned by a regularised logistic regression by default, with gradient-boosted trees as a pre-registered challenger

Every run fits both, for every transition (time at a stage handled as a discrete-time hazard): regularised
logistic regression as the default, and calibrated gradient-boosted trees as the challenger. The challenger replaces
the default for an advertiser or an industry model only if it beats it on the backtest by a paired interval above
zero and its calibration is at least as good; the rule is fixed before results are seen. We keep both because the
previous project's evidence for logistic regression came from a generator that was itself a logistic regression,
so it proves nothing; the new adversarial generator plants interactions and non-linear effects blind to the model,
and the answer may differ between one advertiser's few thousand leads and a pooled industry model's tens of
thousands.

Either model explains a lead's score through per-lead contributions (coefficients or SHAP values) shown in the UI.
