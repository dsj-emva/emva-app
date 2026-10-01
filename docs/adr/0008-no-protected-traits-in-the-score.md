# The lead score never uses protected traits or their near-proxies, in every industry

- Status: under review (2026-09-30). The user may want age (and possibly other traits) usable, for example in
  insurance where it changes a quote. Ruled so far: not a per-country setting; traits sit behind one on/off switch
  that can be changed as needed. Still to decide: the switch's default and who may flip it. Until then build the
  switch, the proxy check and the refusal, and do not rely on either default.
- Amended 2026-10-01 (the user): the prohibited list now matches `CONTEXT.md`. It adds mentions of pregnancy or
  sexual orientation, and the national-origin stand-ins (country of residence, phone country code, enquiry
  language). Counts of adults and children are intent signals; ages are not. The refusal and the proxy check are
  still to be built, in phase 2.

Each industry profile lists prohibited inputs: protected traits (age, gender, ethnicity, religion, disability);
any mention of pregnancy or sexual orientation; and near-proxies for a protected trait or for national origin
(precise postcode or ZIP, name-based inference; country of residence, phone country code, enquiry language). The
ages of the people an enquiry names are prohibited too. The formatter refuses to use any of them as features, and
every run reports a proxy check (any allowed input that strongly predicts a prohibited one). A fairness report of
score distributions across groups, where the data allows it, is required before any pilot. Intent signals
(budget, property value, cover amount, nights, number of adults and of children, luxury level, urgency, enquiry
specificity) are always allowed.

A lead's country and phone country code may still be read to put its phone in the international form the
platforms match on; they are then dropped and never become features.

Insurance and real estate are restricted ad categories (Meta's "Financial products and services" and "Housing"
since January 2025 for US audiences: no age, gender, ZIP-level or lookalike targeting). Advertisers there target
broadly, so the lead score is the main direction the platform's bidding gets. A score driven by protected traits
would steer delivery towards those demographics through the value channel, undoing the targeting restriction and
exposing the advertiser under fair-housing, fair-lending, equality and consumer-duty rules. We apply the rule in
every industry, not only restricted ones, so one model design serves all three and compliance is demonstrable.

## Considered options

- Use whatever predicts and leave compliance to the advertiser: rejected, the risk is created by the score.
