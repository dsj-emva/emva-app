# Phase 1 report: the first thin slice

- State: done (approved by the user on 2026-10-01)
- Date: 2026-10-01
- Plan: PRD [#4](https://github.com/dsj-emva/emva-app/issues/4) (with the user's rulings in its comments, repeated below), issues #5 to #11 in the "Phase 1" milestone
- Pull requests (all merged): [#12](https://github.com/dsj-emva/emva-app/pull/12) (start, new words), [#13](https://github.com/dsj-emva/emva-app/pull/13) (upload), [#14](https://github.com/dsj-emva/emva-app/pull/14) (Railway containers), [#15](https://github.com/dsj-emva/emva-app/pull/15) (Mapping), [#16](https://github.com/dsj-emva/emva-app/pull/16) (Formatter), [#19](https://github.com/dsj-emva/emva-app/pull/19) (training), [#20](https://github.com/dsj-emva/emva-app/pull/20) (scoring), [#21](https://github.com/dsj-emva/emva-app/pull/21) (Backtest results), [#22](https://github.com/dsj-emva/emva-app/pull/22) (end-of-phase cleanup), this report ([#23](https://github.com/dsj-emva/emva-app/pull/23)) and the close-out at approval ([#24](https://github.com/dsj-emva/emva-app/pull/24))
- Live: https://web-production-1d4fc.up.railway.app (Railway, europe-west4; open, no access protection, hand-made data only)

## What was built

One path, screen to model and back, on the hand-made dataset in `services/api/tests/hand_made/` (101 leads and 418 stage-history rows written by hand, in a CRM's own shape):

1. **Upload**: name an advertiser, pick its **Data source**, upload the **Leads file** and the **Stage-history file**. Files go to object storage, records to Postgres, nothing to local disk. Replacing a file is allowed until the Mapping is confirmed. There is a 20 MB cap.
2. **Review**: the person fills in the **Mapping** by hand:
   - each column's role;
   - the inputs to the score, each a number or a category;
   - each **CRM stage** placed on a **Stage** of the **Canonical ladder** or on Lost;
   - the date order and time zone;
   - the **Typical deal size**.

   The service lists every reason the Mapping can't be confirmed yet. Confirmation is a separate act, timed by the injected clock, and final.
3. **Formatter** (runs on confirmation, in one transaction):
   - Names are dropped. Emails are normalised and SHA-256 hashed, and so are lead identifiers.
   - Phones are resolved to E.164, the international form the ad platforms match on: from a `+`/`00` prefix first, then the lead's own country column, then a currency used in only one country. Otherwise the hash of the digits is kept and counted as "phones without a country".
   - Inputs that look like contact details, or categories with too many values, are refused.
   - Unreadable rows are reported as row numbers and reasons only.
   - Raw uploads are deleted after the commit.
   - The Outcome rules: Won is final; otherwise the latest event decides; reaching a Stage implies every earlier one.
4. **Training**: the stage-by-stage model (decision 0002) is fitted with one L2 logistic regression per **Transition** from Contact attempted onwards (decision 0009, C = 1.0, fixed). **Neglected leads** are left out of learning. A Transition with fewer than 10 made or 10 failed uses a smoothed rate. Features are fitted on every lead submitted by the time. A missing number is learned from as "not given". The model is stored as JSON. Training runs inside the request, serialised per advertiser.
5. **Results**: a time-ordered **Backtest** runs as part of each **Training run**:
   - 5 folds by submission time; the first only trains.
   - Calibration groups, plus a slope fitted lead by lead.
   - The **Status-quo signal** (every lead given its fold's prior win rate), compared by paired Brier difference with a 2000-resample bootstrap interval (seed 2026).
   - AUC, reported and not gated.
   - Pass or fail against decision 0005's thresholds, written in code before any result.
   - Every number labelled with its Data source.
6. **Scoring**: a form built from the Mapping's inputs. The service runs the same `format_lead` and feature code as training. It returns:
   - the **Submit score**, which is the chance of winning × the Typical deal size;
   - the chance itself;
   - the **Score explanation**: from the typical lead, one input at a time, in steps that add up exactly to this lead's chance.

   Nothing about the scored lead is stored.

## Done-when checks

| check | how it was run | result |
|---|---|---|
| In the browser, on the hand-made dataset: upload, map columns and sales steps on the review screen and confirm, train, see calibration and the status-quo comparison, score one lead and see its explanation | Browser pane, local dev stack (main at 5d2461e) and Railway (5d2461e, then re-run at 9b3eb1c). Mapping filled in by hand through the screen's controls; the draft read back equal to the tests' mapping. Files sent through the screen's own file input from a script, because the browser tool cannot open the OS file picker | **pass** locally and on Railway, identical numbers (below). Screenshots: [results](phase-1/results.png), [score](phase-1/score.png), [Railway results](phase-1/railway-results.png), [Railway score](phase-1/railway-score.png) |
| Nothing trains before the mapping is confirmed (a test proves it) | `test_training_api.py::test_training_is_refused_before_the_mapping_is_confirmed_and_nothing_is_stored` (a variant for a confirmed mapping not yet formatted went with the repair code at approval: confirming now always formats) | **pass** |
| No name, raw email or raw phone number is stored after formatting (a test proves it) | `test_formatting_api.py::test_after_formatting_no_personal_data_is_stored_anywhere`. It proves first that the scan can see the data, then scans every Postgres table and every stored object after formatting, training and scoring, including the model and Backtest JSON. A variant uses emails as lead identifiers and a free-text column | **pass** |
| Tests cover mapping sales steps onto the standard ladder, the score formula and the injected clock | Ladder: `test_ladder.py`, `test_mapping.py`, `test_transitions.py`, `test_formatter.py`. Score formula: `test_scoring.py` (chance × Typical deal size; product of four Transitions; smoothed Transition). Clock: `test_clock.py`, `test_only_the_clock_reads_the_time.py` (an AST guard that no other module reads the time), and fixed-clock tests on upload, confirmation and formatting | **pass** |
| `make test`, `make lint`, `make check-client` pass and CI is green | Each target run on main; `gh run list --branch main` | **pass**: 433 Python and 55 screen tests; lint and client check clean; CI green on 9b3eb1c |
| The app runs on Railway in a Europe region and the same path works there | Railway services `api`, `web`, Postgres (europe-west4) and a bucket (ams). Pushes to main deploy automatically. The path was re-run in the browser on the final deploy | **pass** |

The numbers seen, the same locally and on Railway, all **on hand-made test data**:

- **Formatting:** 100 leads; 18 won, 58 lost, 24 with no Outcome yet; 13 Neglected leads; 8 unreadable rows.
- **Transitions** (made / failed / left out), all four learned:
  - Contact attempted → Engaged: 67 / 16 / 4
  - Engaged → Qualified: 49 / 15 / 3
  - Qualified → Proposal: 35 / 12 / 2
  - Proposal → Won: 18 / 13 / 4
- **Backtest:** 58 leads scored.
  - Calibration slope **1.218: fail** (gate 0.8 to 1.2).
  - Brier difference against the Status-quo signal +0.022, 95% interval −0.010 to +0.056: **fail** (gate: interval above zero). Emva 0.162, status quo 0.183.
  - AUC 0.72, not gated.
  - **The Trust gate fails on the hand-made data.** It is reported as it is; nothing was tuned. 58 hand-made leads are a small sample, and the dataset was written by hand to exercise the path, not to prove the model.
- **Scored lead** (Phone, Safari, party 2, 12 nights, budget 18,500): chance 82.8%, Submit score 9,932 (Typical deal size 12,000).
  - The explanation starts from the typical lead at 10.2%: channel −2.6, trip type 0, party size −0.8, nights +20.9, budget +55.0 points.

## Review

Each PR had `/code-review` (Standards and Spec in separate helper agents) before it merged, and every PR was changed after its review. The whole phase then had one more review (`1dbb2d8...main`). That review found:
- data-source labels defined twice;
- two status codes for one refusal;
- screens stating rules the service owns;
- a personal-data scan that stopped before training;
- `formatted_at` copied rather than taken from the clock.

All of these were fixed in #22, along with three screen problems the browser check found.

Fixes made after review that are worth knowing:
- **Personal data:** lead identifiers are hashed, because CRMs often use the email as the identifier.
- **Input checks:** contact-like and free-text inputs are refused.
- **Phones:** handled deterministically (the user's ruling).
- **Uploads and storage:** races between upload and confirmation are locked; there is a size cap; a failed save no longer leaves an orphan object; migrations take an advisory lock.
- **Containers:** they run as non-root.

## Rulings made by the user during the phase

Also in PRD #4's comments. Code comments cite them as "ruling N".

1. Lead score = chance × the advertiser's Typical deal size, set by a person; this also closed START_HERE open decision 2 and is recorded in decision 0003.
2. Learn only from Contact attempted onwards. A lead never attempted is left out, and the Submit score's chance is the product of the four Transitions from Contact attempted to Won.
3. New words: Mapping, CRM stage, Training run, Typical deal size; later also Data source, Leads file, Stage-history file.
4. Training runs inside the request in phase 1.
5. Railway: created by the session, EU, open.
6. Results are labelled with the Data source picked at upload.
7. Status-quo comparison: every lead given the training win rate; paired Brier difference, 95% bootstrap interval, pass when above zero.
8. A Transition is learned only with at least 10 made and 10 failed.
9. A confirmed Mapping is final; a wrong one means a new advertiser.
10. Phones are resolved deterministically: `+`/`00`, then the lead's country, then a currency used in only one country, else the flagged hash of the digits. This replaced a first ruling for one country per advertiser.
11. The date order and time zone are part of the Mapping, UTC by default.
12. A missing number input is learned from, as "not given".
13. A Transition with too few leads uses (made + 2p) / (made + failed + 2), with p pooled across the run's four Transitions. Scoring is refused only when no lead finished any Transition.
14. The Backtest evaluates every lead with a known Outcome, Neglected leads included. The first hand-made result stands.

## Approval

The user approved phase 1 on 2026-10-01, with three rulings, carried out in the close-out pull request:

1. **Calibration slope.** Kept as built: the slope is fitted over individual leads, and deciles are only how calibration is shown. The 0.8 to 1.2 range applies to synthetic, public and real data alike. Decision 0005 is amended to say so.
2. **Outcome rules.** A later Stage after Lost reopens the lead, and Won is final for now; `ladder.py` cites this. What happens to a won deal later cancelled or refunded is START_HERE open decision 4, to be settled in phase 2.
3. **Repair code deleted.** The test data on Railway and locally was wiped, so the code that handled data from earlier in the phase went: re-formatting a mapping confirmed before formatting existed, training's check for a confirmed mapping without formatting, leads files without column facts, runs without a Backtest, and models without `any_given`. Migration 0006 makes `uploaded_file.column_facts` and `training_run.backtest_key` required.

## Still open

Settled at approval (see above): the calibration slope method (decision 0005, amended), the Outcome rules (`ladder.py`, START_HERE open decision 4) and the repair code (deleted, migration 0006).

Decisions for the user:
- **Neglected leads in the Backtest (ruling 14).** The model's chance assumes a Contact attempt, so grading it against never-contacted losses may make Emva look over-confident. This is a known risk, kept by your ruling.
- **Phase 2 already listed:** deal size stated on the form entering the score (the scored lead stated 18,500 but 12,000 was used); a lead's country used only to read its phone, never as a score input (decision 0008).

Smaller items:
- `mapping_api.py` does several jobs: drafts, confirmation, formatting and deletion. Worth splitting when phase 2 touches it.
- Storage errors are answered three ways (409 upload again, 503 try again, 200 with "results unavailable"), and upload errors can still surface as 500.
- The data-source choices on the upload form now read "on hand-made test data", the label form, which reads oddly as a choice.
- GBP stays on the single-country currency list although a few British territories also use it. NOK, MAD, TRY, ILS, ZAR, INR, CHF, AUD, NZD, DKK, EUR and USD are left out.
- IP-address lookup for a phone's country is issue [#18](https://github.com/dsj-emva/emva-app/issues/18), outside phase 1.
- CI starts Postgres and object storage with docker compose rather than GitHub service containers. The effect is the same.
- The browser check sent files from a script into the screen's file input, not through the OS picker.

## New decisions or words

- Words added to `CONTEXT.md`: **CRM stage**, **Mapping**, **Typical deal size**, **Training run**, **Data source**, **Leads file**, **Stage-history file**.
- Decision 0003 amended: the typical deal size is set by a person, never learned. START_HERE open decision 2 is closed.
- No new decision records. The rulings above live in this report and in PRD #4.
