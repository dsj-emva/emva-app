# Emva

Emva scores inbound leads for advertisers and sends each lead's score back to the ad platforms (Google Ads,
Meta, TikTok and others), so the platforms bid for leads that become customers rather than for form fills.

## Language

### Leads and scores

**Lead**:
One enquiry submitted by a prospective customer of an advertiser, traced from submission to its outcome.
_Avoid_: contact, prospect, form fill

**Outcome**:
What finally happened to a lead in the advertiser's sales process: won (with when, and the **Deal value**) or
not won. Used to train; never known when a lead is first scored.
_Avoid_: label (a label is what training derives from an outcome), conversion

**Lead score**:
The number Emva sends the ad platforms for a lead: a relative measure of quality on a fixed, stable scale,
never money. The platforms require a currency alongside it; that is a formality.
_Avoid_: lead value, conversion value (the platforms' name for the field that carries it)

**Submit score**:
The **Lead score** sent the moment a lead arrives: how likely the lead is to win, predicted only from what is
known at submission, times its likely deal size. The size comes only from what the lead states (a budget, a
number of seats, a number of nights); when it states nothing, the advertiser's **Typical deal size** is used,
so every lead is on the same scale. Never guessed from outside data at submission.
_Avoid_: submit value

**Stage score**:
A further **Lead score** sent, as its own event, when a lead reaches a later **Stage**: the lead's full score at
that moment (its new likelihood and, once the CRM reveals it, the deal's size). It sits beside the **Submit
score** and never edits it.
_Avoid_: updated value, close value

**Optimisation event**:
The one event per campaign the ad platform bids on. Starts as "lead submitted"; moves to the deepest **Stage**
whose events reach the platform in time and in enough volume for it to learn from.
_Avoid_: primary conversion (Google's name for the same role)

**Observed event**:
Any other event Emva sends: reported and building history, not bid on.
_Avoid_: secondary conversion

**Deal value**:
The money a won (or quoted) deal is worth, as recorded in the advertiser's CRM. Real currency; used for
learning and reporting, and enters **Lead scores** only through **Stage scores**.

**Typical deal size**:
The size of deal an advertiser usually makes, set by a person (not worked out from recorded **Deal values**),
used as a lead's size when the lead states none. Being set, not learned, it does not move between retrains.

### Sales process

**Stage**:
One step of an advertiser's sales process that a lead can reach (e.g. contacted, qualified, proposal, won),
expressed on the **Canonical ladder** whatever the advertiser's CRM calls it.
_Avoid_: status, step

**Canonical ladder**:
The fixed, ordered set of **Stages** every advertiser's sales process is expressed on: Submitted, Contact
attempted, Engaged, Qualified, Proposal, Won (Lost can follow any stage). Shared across advertisers so
industry models can be reused.

**CRM stage**:
The advertiser's own name for a point in its sales process, as its CRM records it, before the **Formatter**
places it on a **Stage** of the **Canonical ladder** or on Lost.
_Avoid_: CRM status

**Milestone**:
An advertiser-specific step that sits inside one **Canonical ladder** stage (e.g. "quote sent" within
Proposal, "valuation booked" within Qualified). Adds signal for that advertiser without changing the ladder.
A person declares that a milestone exists and where it sits; how much it matters is learned from the
advertiser's history, never set by hand.
_Avoid_: custom stage, sub-stage

**Transition**:
A lead moving from one **Stage** to the next. A lead's chance of winning is the chance of making every
transition still ahead of it.

**Contact attempt**:
The advertiser trying to reach a lead. Whether an attempt happens is the advertiser's behaviour, not the
lead's quality; a lead's quality counts only from the first attempt on.

**Neglected lead**:
A lead the advertiser never attempted to contact. It says nothing about its own quality: its first
**Transition** is unfinished, not failed.
_Avoid_: ghosted (ambiguous: who ghosted whom?)

**Sales notes**:
What the advertiser's team writes about a lead after contact (call notes, logged emails). Read by a language
model into **Judgments** that inform **Stage scores**.

**Loss reason**:
Why the advertiser says a lead did not win (price, timing, never a real buyer, could not reach them). Teaches
the model different things: "never a real buyer" says the lead was poor; "could not reach them" may say the
handling was.

**Score explanation**:
For one lead at one **Stage**: the typical lead's chance, then each signal that pushed it up or down, ending at
this lead's chance and its **Lead score**. Shown for every score.

**Momentum**:
How fast and how far a lead is moving through the **Stages**; a lead that sits at one stage has none.
Known only after submission, so it informs **Stage scores**, never the **Submit score**.

### Data

**Data source**:
Where a set of an advertiser's data came from (hand-made test data, simulated data, public data, or the
advertiser's private export), carried as a label on every number Emva shows from it.

**Leads file**:
The advertiser's export with one row per **Lead**, as its CRM or form tool writes it.

**Stage-history file**:
The advertiser's export with one row per change of a lead's **CRM stage**.

**Formatter**:
The step that turns an advertiser's data, in whatever shape it arrives (spreadsheet, CRM export), into
Emva's canonical structure, outcome included.
_Avoid_: converter, adapter, importer

**Mapping**:
The instructions that tell the **Formatter** what each column of an advertiser's data means and where each
**CRM stage** sits on the **Canonical ladder**. Filled in by hand or drafted by a language model, and always
confirmed by a person before it is used.

**Judgment**:
A category a language model assigns after reading a lead's own words (e.g. urgency: high / low / unclear).
May become an input to the scoring model; never a score itself.
_Avoid_: LLM score, rating

**Industry profile**:
Every industry-specific fact the generator and **Lead simulator** need (what the form asks, sales-cycle length,
deal sizes, **Stage** and neglect rates, how leads write, which effects are planted), kept in one place so the
rest stays industry-neutral. The seed of that industry's model. Every uncertain fact is a range with a
confidence (sourced, estimated, guessed), and a model must pass its **Trust gate** across the whole range, so no
single benchmark can decide the result.

**Considered sale**:
A sale where the advertiser's team has to do work between the enquiry and the sale: a plan, an assessment, a
quote or a proposal. Where Emva fits; a purchase completed online without a salesperson is not one.
_Avoid_: high-touch sale, B2B sale

**Target industries**:
The three industries Emva is built to serve, chosen because their sales processes sit far apart: insurance,
real estate, and planned hospitality. One is chosen first for the pilot. Within each, only **Considered
sales** are in scope (insurance: adviser-led life, protection and health, and broker-led cover; not policies
bought online).

**Planned hospitality**:
Travel or hospitality that a sales team or concierge has to plan with the customer after a detailed enquiry
(e.g. a tailor-made safari: nights, budget, camp style, location, luxury level, the experience wanted; also
corporate trips, events, weddings). A direct room booking is a purchase, not a **Lead**.
_Avoid_: hotel bookings

**Prohibited input**:
Something the **Lead score** may never be learned from: a protected trait (age, gender, ethnicity, religion,
disability), any mention of pregnancy or sexual orientation, or a near-proxy for a protected trait or for national
origin (precise postcode, name-based inference; country of residence, phone country code, enquiry language). Ages
are not an **Intent signal**. Listed per **Industry profile**.

**Intent signal**:
What a lead says about the purchase itself (budget, property value, cover amount, nights, number of adults and
of children, luxury level, urgency, how specific the enquiry is). Always allowed, even where it correlates with a
protected trait.

**Advertiser history**:
One advertiser's own past **Leads** with their **Stages** and **Outcomes**: what a new lead is compared
against when it is scored.

**Cross-advertiser history**:
What Emva has seen across all its advertisers (e.g. the same person enquiring with several of them). Needs
several advertisers and contract terms that allow it.

### Models

**Industry model**:
A model trained for one industry that can be reused for every advertiser in that industry.

**Challenger**:
A more complex model fitted beside the default on every run; it replaces the default only by beating it on the
**Backtest** under rules fixed in advance.

**Training run**:
One fit of the models (the default and, once it exists, the **Challenger**) on one set of data, together with
its **Backtest**.

**Customer adjustment**:
The fitting of an industry model to one advertiser's own data.
_Avoid_: fine-tune (ambiguous with LLM fine-tuning)

### Evidence

**Evidence ladder**:
The three kinds of data a model is proven on, in order of how much they prove: adversarial synthetic data
(how the model behaves and what inputs it needs), public real-world data (real outcomes, real mess), and an
advertiser's private historical export (the real test).

**Lead simulator**:
A bot that plays both the advertiser's website and their CRM: it sends synthetic leads to Emva as real ones
would arrive, then sends their **Stage** changes as a realistic sales team would record them (delays, neglect,
skipped stages, sloppy entries), on a **Simulated clock**.

**Simulated clock**:
The time a simulation runs on, faster than real time (e.g. one day per minute). Everything Emva records during
a simulation is in simulated time.

**Hidden truth**:
What the generator or **Lead simulator** knows about each synthetic lead (its real quality, its eventual
**Outcome**) and Emva must not. Read only when grading Emva.
_Avoid_: ground truth (the previous project's name; same idea)

**Trust gate**:
The pass/fail criteria, written before any result is seen, that a model must meet on a rung of the
**Evidence ladder** before it is trusted there.

**Status-quo signal**:
What an advertiser's ad platforms receive today instead of Emva's scores: usually every form fill sent as the
same conversion, sometimes a hand-built lead-score rule. Emva's promise is to be more accurate than it.

**Backtest**:
Scoring an advertiser's past leads with a model trained only on leads before them, then comparing with how
they actually ended. Shows the scores predict; cannot show that ad spend improved.

## Relationships

- A **Lead** receives one **Submit score** and zero or more **Stage scores**, then has one **Outcome**
- Training learns from **Outcomes**, **Deal values** and every **Stage** a lead reached, including leads not
  yet finished; scoring predicts the **Outcome**
- A lead's **Momentum** and, once known, its **Deal value** shape its **Stage scores**
- Each campaign has exactly one **Optimisation event**; every other event is an **Observed event**
- An **Industry model** plus a **Customer adjustment** scores one advertiser's **Leads**
- Every model climbs the same **Evidence ladder**

## Flagged ambiguities

- "Winning category / cohort" was used for the submit-time cross-check; resolved: the **Submit score** is a
  prediction learned from past **Outcomes**, and the resembling cohort is only its explanation.
- "Value" was used both for the number sent to the platforms and for deal money; resolved: the platforms get a
  **Lead score** (unitless), money is **Deal value**.
