# Industry facts live in profiles as ranges with confidence, and the trust gate must pass across each range

The generator and lead simulator are industry-neutral; every industry fact (form fields, sales-cycle length, deal
sizes, stage and neglect rates, how leads write, planted effects) lives in one industry profile. Each uncertain
number is a range tagged sourced, estimated or guessed, with its source when one exists, and synthetic datasets
are generated at the low, middle and high ends of those ranges. A model passes its trust gate on a profile only
if it passes at every end. We chose ranges over single cited benchmarks because good sources for these numbers
are scarce and sometimes wrong, and a model tuned to one benchmark's value would be trusted on a number nobody
checked.

Profiles are written by someone who does not write the model, and the model by someone who does not see the
profiles' planted effects, so the synthetic test cannot be written in the model's own hand (the previous
project's generator was the same additive model it tested). The split is structural: profiles, generator, lead
simulator and hidden truth live in their own repository, `emva-sim`, beside `emva-app` under `~/code/emva/`.
`emva-sim` reaches EMVA only as the outside world does (CSV uploads, the intake and CRM-update endpoints), and
agent settings in `emva-app` deny reading `../emva-sim`.

Phase 1 ships profiles for the three target industries, deliberately far apart: insurance (short cycle, high
volume), real estate (long cycle, high value) and planned hospitality (detailed enquiry, concierge-planned,
high value).
