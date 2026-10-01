# Trusting the model is a pre-registered pass/fail gate per evidence rung; the business claim needs a live experiment

- Status: amended on 2026-10-01 (the user's ruling on approving phase 1): the calibration slope is fitted over
  individual leads, not over deciles, and its 0.8 to 1.2 range applies on every rung

The model is trusted on a rung of the evidence ladder only when it passes criteria written down before any result
is seen, and a failed gate is reported, never tuned away. On adversarial synthetic data: every planted effect
recovered with the right sign and within its interval; a calibration slope within 0.8 to 1.2, fitted over
individual leads (deciles are only how calibration is shown, never what the slope is fitted on); a paired
interval above zero against a status-quo hand rule on a time-ordered backtest; planted-good neglected leads not
scored down; and stage scores calibrated at every stage (leads that reached a stage win at the rate their stage score
predicts). On public and private
real data: the calibration slope, fitted over individual leads and within the same 0.8 to 1.2, and the status-quo
comparison only, labelled with their source. Ranking accuracy (AUC) is
reported, not gated, because on synthetic data it mostly measures how hard the generator was made.

The promise to an advertiser is that Emva gives their ad platforms a more accurate good-lead / bad-lead signal,
learned from their own data, than the status-quo signal the platforms receive today (usually every form fill
sent alike, or the advertiser's hand-built lead-score rule). That is proven by a backtest on the advertiser's own
history. Better conversion rates and more efficient ad spend are the expected consequence and are not claimed;
claiming them would need a live, platform-randomised split test, which remains an option, not the gate.
