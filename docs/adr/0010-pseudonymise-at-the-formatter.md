# Personal data is pseudonymised at the formatter, from phase 1, even on synthetic data

The formatter drops names; normalises and SHA-256 hashes email and phone (the form the ad platforms' matching
already requires, so raw values are never needed again); deletes raw uploads once formatted; scrubs personal
data from free text before it is stored or sent to any language model; and never stores or features
special-category data (e.g. health details in insurance) without an explicit later ruling. Data is hosted in the
UK or EU with a stated retention period. Language models see only redacted column profiles and scrubbed text,
never raw rows. Per-advertiser encryption and hard tenant isolation are required before the first private
export is uploaded.

Phase 1 runs on synthetic data but behaves as if it were real, so the pipeline never has to be made safe later.
