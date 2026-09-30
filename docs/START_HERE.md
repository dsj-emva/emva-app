# Start here: how Emva is built

This file is the build plan and the prompts that start each phase. It was written at the end of the planning
session of 2026-09-30. The rulings behind it are in `CONTEXT.md` (the word list) and `docs/adr/` (the decisions).

## 1. What to read, and in what order

Every working session, in either repository, starts by reading, in this order:

1. `CLAUDE.md` of the repository you are in (how to work there).
2. `emva-app/CONTEXT.md`: the word list. Use its words exactly, in code, tests, screens and messages. If a word
   you need is missing, or you want to use a word the list says to avoid, stop and ask.
3. The decisions in `emva-app/docs/adr/` that the task touches (the table below says which).
4. This file, for the phase you are in (`emva-app` only). `emva-sim` sessions never read this file; the rules
   they need, including the skills and helper agents rules of section 3, are written in `emva-sim/CLAUDE.md`,
   and their phase prompt comes from the user.

Rules that keep the documents and the code in step:

- A new term goes into `CONTEXT.md` in the same change that introduces it. `CONTEXT.md` holds meanings only,
  never implementation detail.
- A decision that is hard to reverse, surprising without context, and a real trade-off gets a new numbered file in
  `docs/adr/`. Anything less does not.
- If the code and a decision disagree, stop and ask. Do not quietly pick one.
- The old project (`~/Library/Mobile Documents/com~apple~CloudDocs/code/EMVA/learning-modal`) is reference only.
  Take from it only what decision 0011 names, one piece per commit, naming the source file.

| decision | read it when working on |
|---|---|
| 0001 Python owns the logic, TypeScript owns the screens; one repository; hosting | anything structural, any screen |
| 0002 Stage-by-stage model; neglected leads | labels, training, scoring |
| 0003 What the lead score is (chance times stated size, one scale) | scoring, anything sent to a platform |
| 0004 What the AI models may and may not do | formatter drafts, explanations, judgments, notes |
| 0005 The trust gate, written before results | evaluation, the results screen |
| 0006 Lead simulator and the injected clock | anything that needs "now", intake endpoints |
| 0007 Industry profiles as ranges; the simulator kept apart | `emva-sim`, synthetic data |
| 0008 Personal traits (under review) | features, the formatter, compliance |
| 0009 Simple model by default, complex challenger | training, evaluation |
| 0010 Personal data protected from day one | formatter, storage, anything sent to an AI model |
| 0011 What comes over from the old project | before copying anything |
| 0012 Which event the platform learns from | the live connection to the platforms |

## 2. Decisions still open (ask before building anything that depends on them)

1. Personal traits switch: its default and who may flip it (decision 0008).
2. A lead that states nothing about deal size: use the advertiser's typical deal size so every lead is on one
   scale (decision 0003). Proposed, not yet confirmed by the user.
3. The exact volume and timing thresholds for moving the platform's learning event to a later stage, per platform,
   checked against current platform guidance (decision 0012). Needed only in phase 6.
4. Which pilot advertiser, and so which industry first (planned hospitality proposed, then real estate).

## 3. Rules that prevent confusion and technical debt

- Build in thin end-to-end slices. Each slice works from the screen to the model and back, is one branch and one
  pull request, and leaves `main` working. The user merges; no agent pushes to `main`.
- Tests first where mistakes are expensive: mapping sales steps onto the standard ladder, neglected leads, the
  injected clock, the score formula, personal data removal. Hand-made test cases at the edges.
- One place per idea. The formatter, features and scoring code are the same code in training and in live scoring.
  The screens compute nothing; every number on screen comes from the Python service.
- The TypeScript types for the service are generated from its schema, never written by hand. Continuous
  integration fails if they are out of date.
- Nothing reads the system clock directly; time comes from the injected clock (decision 0006).
- Nothing keeps state on local disk; files go to object storage, records to Postgres.
- No speculative options, no dead code, no commented-out code. If something is not needed by the current slice,
  it is not built.
- Pass-or-fail criteria are written before results are seen. A failed check is reported, never tuned away.
- Every number from synthetic data is labelled "on simulated data"; from public data, "on public data".
- Commits are small, and each ends with the co-author line the tooling asks for.

### Skills and helper agents

- Use a skill wherever one fits, in every phase, instead of working it out from scratch:
  - `/tdd` to build every feature and fix, test first.
  - `/code-review` on every branch before it is handed to the user to merge.
  - `/research` for industry profiles, platform rules and anything that needs cited sources.
  - `/diagnose` for any bug, failing test or slowdown.
  - `/frontend-design` for every screen.
  - `/to-prd` and `/to-issues` at the start of each phase, to turn its section of this file into issues.
  - If a skill you want is not installed, say so and carry on without it; never invent one.
- Hand work to helper agents (sub-agents) for searches across many files, reviews, research and independent tasks
  that can run in parallel. Keep the main session for decisions, for talking to the user and for putting the
  results together. A helper agent is told which files of section 1 to read, gets a self-contained task, and
  reports back; its findings are checked before they are acted on. Helper agents working in `emva-app` never read
  `emva-sim`, and the other way round.

## 4. Phases

Every phase from 2 onwards starts with `/to-prd` and `/to-issues` on its section below, builds each issue with
`/tdd`, uses `/frontend-design` for any screen, `/research` for any platform rule or outside fact, `/diagnose` for
any bug, and `/code-review` before each branch is handed over, handing searches, reviews and parallel work to
helper agents (section 3).

Two repositories under `~/code/emva/`:

- `emva-app`: the product. Screens (Vite and React, TypeScript), the Python service and workers (FastAPI),
  and the generated client. Holds `CONTEXT.md` and `docs/adr/`.
- `emva-sim`: industry profiles, the data generator, the lead simulator and the hidden truth. Built in separate
  sessions that never read `emva-app` code; `emva-app` sessions never read `emva-sim` (decision 0007).

Phase 0 comes first. After it, the product track (phases 1 to 3) and the simulator track (phase S) run in
parallel, in separate sessions. They meet in phase 4.

### Phase 0: set-up (one session, in `~/code/emva`)

Goal: two empty but working repositories, with the rules written down where every later session will find them.

Prompt:

> Read `~/code/emva/emva-app/docs/START_HERE.md`, `CONTEXT.md` and every file in `docs/adr/`. Then set up the two
> repositories exactly as section 4 of START_HERE describes. Do not build any product feature.
>
> In `emva-app`: `git init`; a `CLAUDE.md` that tells every session to follow section 1 and section 3 of
> START_HERE (including its skills and helper agents rules) and summarises the layout; the folders `apps/web` (Vite, React, TypeScript, strict mode),
> `services/api` (Python 3.12, FastAPI, managed with uv; ruff and pytest), `packages/api-client` (generated from
> the service's schema); one health-check endpoint shown on one page, proving the generated client works; a
> Makefile or task runner with `test`, `lint`, `generate-client` and `dev`; continuous integration that runs tests
> and lint and fails when the generated client is stale; `.claude/settings.json` denying reads of `../emva-sim/**`;
> `.gitignore` covering `.env`, data files and build output; Postgres and object storage for local development
> (a compose file).
>
> In `emva-sim`: `git init`; a `CLAUDE.md` saying it builds industry profiles, the generator and the lead
> simulator, follows the skills and helper agents rules in section 3 of START_HERE, uses the vocabulary of `../emva-app/CONTEXT.md` (the only file of `emva-app` it may read), follows
> decision 0007, and talks to Emva only through uploaded files and the intake endpoints; `.claude/settings.json`
> denying reads of `../emva-app/**` except `../emva-app/CONTEXT.md` and `../emva-app/docs/adr/**`; Python with uv,
> ruff, pytest.
>
> Use `/tdd` for the health-check path, hand independent set-up work to helper agents where it saves time, and
> run `/code-review` before handing it over. Commit each repository in small commits. Ask me before creating any
> remote repository.

Done when: both repositories have a first commit, tests and lint pass, the health-check page shows data from the
service through the generated client.

### Phase 1: the first thin slice (product track, `emva-app`)

Goal: a spreadsheet goes in, a model is trained, its trust-gate results appear, and one new lead gets a score
with its explanation. Deliberately simple everywhere.

Start the session with `/to-prd` using this section and the decisions it names, then `/to-issues` to cut it
into issues, then build issue by issue with `/tdd`.

Prompt:

> Read `CLAUDE.md`, `CONTEXT.md`, START_HERE and decisions 0001, 0002, 0003, 0005, 0006, 0010. Build phase 1 of
> START_HERE as one thin slice: upload a leads file and a stage-history file; a formatter with a mapping the user
> fills in by hand on a review screen (no AI yet), including mapping the business's sales steps onto the standard
> ladder, confirmed by a person before anything trains; personal data removed or scrambled at the formatter;
> training of the stage-by-stage model with the simple model only; a results screen showing calibration and the
> comparison with the status-quo signal on a time-ordered backtest; a scoring screen that scores one lead and
> shows its score explanation. Use a small hand-made test dataset inside the repository's tests; do not write a
> data generator (that is `emva-sim`'s job). Use the words of CONTEXT.md exactly. List anything the decisions do
> not answer and ask me before building it. Build with `/tdd`, design the screens with `/frontend-design`, and run
> `/code-review` before each branch is handed over.

Done when: the whole path works in the browser on the test dataset, with tests.

Then deploy to Railway (Europe region) so later slices are tested where they will run.

### Phase S: first industry profile and generator (simulator track, `emva-sim`, parallel with phases 1 to 3)

Goal: messy, realistic synthetic data for planned hospitality, then real estate, then insurance.

Prompt:

> Read `CLAUDE.md`, `../emva-app/CONTEXT.md` and decision 0007. Use `/research` (with helper agents in parallel,
> one per topic) and write the industry profile for
> planned hospitality (tailor-made safari-style trips; also corporate trips and events): form fields, sales steps
> as the business's own sales system would name them, sales-cycle length, deal sizes, neglect rates, how enquiries
> and sales notes are written, loss reasons. Every uncertain number is a range with a confidence (sourced,
> estimated, guessed) and its source. Then build the generator: it writes files in the shape a real sales system
> export would have (not Emva's standard shape), with realistic mess (missing values, skipped steps, late
> entries, duplicates, bots), plants effects that are not all simple or additive, and keeps the hidden truth in a
> separate file. You never see Emva's model code. Generate datasets at the low, middle and high ends of each range.

Done when: the profile is reviewed by the user, and datasets exist at each end of each range.

### Phase 2: deepen the model (product track)

Adds, one slice each: neglected leads and contact attempts; milestones declared per business; time at a stage
and momentum; the complex challenger model and the rule for when it wins; the full trust gate with its criteria
written before results; the personal-traits switch, refusal and proxy check (decision 0008); deal size from the
form into the score (decision 0003). Read decisions 0002, 0003, 0005, 0008, 0009 first.

### Phase 3: the AI jobs (product track)

Adds, one slice each: formatter drafts from redacted column descriptions, confirmed by a person; plain-words
explanations of a score; judgments from the lead's free text (Claude Haiku 4.5 compared with Jev on the same
texts, each judgment kept only if its weight holds up); spam, bot, duplicate and fake-contact checks; sales notes
and loss reasons read into judgments for later scores. Model responses are cached and never made up. Read
decisions 0004 and 0010 first.

### Phase 4: the live intake and the simulator (both tracks meet)

`emva-app` adds the lead intake endpoint and the stage-update endpoint, both on the injected clock, and the
screen that shows scores arriving. `emva-sim` adds the lead simulator: it sends leads and plays a realistic sales
team on a sped-up clock, then grades Emva's scores against the hidden truth (the grading lives in `emva-sim`, so
the hidden truth never enters `emva-app`). Read decision 0006 first.

Done when: a simulated month of leads runs in minutes and the grading report passes or fails the trust gate.

### Phase 5: climb the evidence ladder

Public real-world data through the same formatter and model, then a pilot business's own past leads (first
hospitality or real estate). Real estate and insurance profiles are added in `emva-sim`. Nothing is claimed
until the trust gate passes on real data. Private data needs per-business encryption first (decision 0010).

### Phase 6: the live connection to the platforms

Google first, then Meta, TikTok and LinkedIn. For each: write valid upload files, then send to test accounts,
then to a real account only with the pilot business's consent. Each update is its own event carrying the full
score; one event per campaign is the one the platform learns from, moving to a later stage when the checked
volume and timing thresholds are met. Every platform limit is checked against current platform documentation and
cited. Read decisions 0003 and 0012 first.
