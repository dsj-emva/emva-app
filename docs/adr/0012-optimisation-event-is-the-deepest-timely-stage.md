# The platform optimises on the deepest stage that still arrives in time and in volume; every event carries the lead's full score

Amends ADR 0003 (stage scores as increments).

The goal is the most signal the ad platform will accept and learn from within its window. Each advertiser runs
value-based bidding. For every lead Emva sends one event per stage reached ("lead submitted", "Emva engaged",
"Emva qualified", ...), each carrying the lead's full score at that moment (likelihood given the stage reached,
plus deal size once the CRM reveals it), not an increment. Per campaign, exactly one event is the optimisation
event the platform bids on (Google: primary conversion action); the others are observed only (secondary), so
nothing is counted twice.

A new account optimises on "lead submitted", the only event that is always timely. Emva recommends moving the
optimisation event to a deeper stage once that stage's events, per campaign over 30 days, meet the platform's
volume guidance for value bidding and mostly arrive within its conversion window and quickly enough to learn from;
the thresholds are fixed in advance per platform (to be verified against current platform guidance) and the
recommendation is shown with its evidence. Before the switch, deeper events steer nothing; they build history.

Increments were rejected because a platform bidding on one event would see only a fragment of the lead's worth.
Google is the first platform (search intent dominates considered-sale research), then Meta, TikTok and LinkedIn.
