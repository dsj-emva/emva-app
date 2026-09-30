# Only named pieces carry over from the previous proof of concept; its generators and schema do not

The previous repository (`EMVA/learning-modal`) is a read-only reference. Carried over:

- Ported as code with their tests: bootstrap and paired-comparison intervals, calibration by decile, and the
  redacted column profiler.
- Re-implemented from the same idea: the language-model mapping draft that a person confirms; category judgments
  with a response cache and a stamp of brief, prompt and model, behind the provider interface.
- Re-recorded as new rulings when first needed: missingness indicators, the rolling-origin backtest, the leakage
  screen.
- Reference only for the live-loop phase: the platform contract research (every limit still to be verified).

Left behind: horizon labels (replaced by the stage-transition model), the fixed 39-column schema, the frozen
baseline machinery, the monetary value transform, the Streamlit tool, and both data generators. The generators
especially: they were additive logistic models that the model they tested matched by construction, so they are
not a starting point for industry profiles.

Each port is its own commit naming its source file and commit.
