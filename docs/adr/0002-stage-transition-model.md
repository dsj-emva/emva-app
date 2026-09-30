# Lead scores come from a stage-transition model, not a single won/lost model

A lead's probability of winning is the product of one learned conditional probability per step of the canonical
stage ladder (contacted given submitted, qualified given contacted, ... won given the last stage), each depending
on what was known at submission. The submit score multiplies every step; a stage score uses only the
steps still ahead of the lead's current stage, adjusted for its momentum. We chose this over a single "won within
H days" model because wins are rare and progress is plentiful: a lead lost at stage 4 of 5 still teaches three
successful transitions, and unfinished leads contribute every transition they have completed instead of being
discarded or mislabelled as lost (the previous project's first defect).

## Considered options

- Single binary "won within H days" (horizon labels): simpler and proven, but discards immature leads and learns
  nothing from partial progress.
- Treat unfinished leads as lost: rejected, biases against slow, large deals.

## Consequences

- The formatter must map every advertiser's CRM stages onto one canonical, ordered ladder.
- Progress the advertiser's own team caused or blocked is confounded with lead quality. The first step is
  therefore split: whether the advertiser attempted contact is modelled as the advertiser's behaviour and never
  counts against the lead; the lead's quality counts only from the first contact attempt. A lead never attempted
  is unfinished, not failed. Where a CRM records no contact attempts, the first transition is treated as
  unfinished until the lead reaches a later stage, and the model's reliance on it is reported as a known risk.
- By-product for advertisers: the share and estimated value of neglected leads.
