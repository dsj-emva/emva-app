import type { components } from '@emva/api-client'

// A Backtest as the service returns it, for screen tests: it fails both checks.
export const BACKTEST: components['schemas']['Backtest'] = {
  as_of: '2026-09-15T08:30:00Z',
  rules: ['Leads are put in order of submission and cut into 5 consecutive folds.'],
  counts: {
    leads: 100,
    training_only: 20,
    no_outcome_yet: 20,
    refused: [{ reason: '“Trip Type” is “Cruise”, which no training lead had.', leads: 2 }],
    scored: 58,
  },
  folds: [],
  groups: [
    { leads: 29, predicted: 0.12, actual: 0.1 },
    { leads: 29, predicted: 0.4, actual: 0.55 },
  ],
  slope: 1.2183,
  comparison: {
    emva_brier: 0.1616,
    status_quo_brier: 0.1834,
    difference: 0.0218,
    interval_low: -0.0096,
    interval_high: 0.0559,
  },
  auc: 0.7175,
  checks: [
    { name: 'Calibration', threshold: 'Calibration slope within 0.8 to 1.2', passed: false },
    {
      name: 'Better than the Status-quo signal',
      threshold: 'The 95% interval of the Brier difference (status quo minus Emva) is above zero',
      passed: false,
    },
  ],
  passed: false,
}
