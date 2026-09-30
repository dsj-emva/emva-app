# A lead simulator exercises the live intake on a simulated clock; Emva never reads the wall clock directly

Phase 1 includes a lead simulator that sends synthetic leads to the same intake endpoint real leads will use,
then sends their stage changes through a CRM-update endpoint, on a clock running faster than real time, so a
trained model is graded on unseen leads arriving as they would in production within hours rather than months.
The simulator's CRM behaviour must be realistic (delays, neglect, skipped stages, sloppy or late entries), not
tidy. Its hidden truth goes to an evaluation-only store that the scoring code cannot read.

Consequence: every part of Emva that needs "now" (maturity, momentum, time at a stage, when a stage score is
due) takes time from an injected clock rather than the system clock, so the same code runs in simulated and real
time. A real-time run of the simulator remains available as a soak test.
