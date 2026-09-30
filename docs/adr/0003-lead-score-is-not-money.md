# The lead score is chance to win times the lead's own stated deal size, on one stable scale

- Status: amended by ADR 0012 (each stage event carries the lead's full score at that moment)

EMVA sends the platforms a lead score on a fixed, stable scale. The platforms' conversion value and currency
fields carry it because they require them; the platforms will display and optimise it as money (return on ad
spend = score / spend), so its scale must not drift between retrains, and revenue reporting always uses recorded
deal values, never scores.

The submit score is the chance the lead wins times its likely deal size, where the size comes only from what the
lead itself states on the form (a budget, a number of seats, a number of nights). When the lead states nothing that
sizes the deal, the advertiser's typical deal size is used, so every lead sits on the same scale. Size is never
guessed at submission from outside data (company lookups) or from weak proxies. Margin is not applied: it is one
setting per advertiser and would scale every lead alike. Later stage scores replace the stated size with what the
CRM reveals (a quote, the won amount).

We chose this over chance alone (which wastes the strongest signal in forms that state a budget, as planned
hospitality enquiries do) and over chance times a predicted size (the previous project's approach: a weak guess
that needs outside data).

## Considered options

- Expected deal value in money with margin, sized at submit from company data: rejected.
- Chance only at submit, size added later: rejected, discards stated budgets.

## Consequences

- The advertiser's target return on ad spend is set against the score's scale, so a change of scale is a breaking
  change.
