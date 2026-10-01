import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { BacktestResults } from './BacktestResults.tsx'
import { BACKTEST } from './test-backtest.ts'

const SOURCE = 'on hand-made test data'

function cells(table: HTMLElement): (string | null)[][] {
  return within(table)
    .getAllByRole('row')
    .map((row) => [...row.querySelectorAll('th, td')].map((cell) => cell.textContent))
}

describe('BacktestResults', () => {
  it('draws the calibration chart with a dot per group, its slope and the data source', () => {
    render(<BacktestResults backtest={BACKTEST} dataSource={SOURCE} />)

    const chart = screen.getByRole('img', { name: 'Calibration on hand-made test data' })
    expect(within(chart).getByLabelText('29 leads: predicted 12%, won 10%')).toBeInTheDocument()
    expect(within(chart).getByLabelText('29 leads: predicted 40%, won 55%')).toBeInTheDocument()
    expect(screen.getByText('Slope 1.218')).toBeInTheDocument()
    expect(cells(screen.getByRole('table', { name: `Calibration groups ${SOURCE}` }))).toEqual([
      ['Leads', 'Predicted', 'Actual'],
      ['29', '12%', '10%'],
      ['29', '40%', '55%'],
    ])
    expect(screen.getByText(`Every number here is ${SOURCE}`)).toBeInTheDocument()
    expect(screen.getByText(BACKTEST.wording.calibration)).toBeInTheDocument()
  })

  it('shows the comparison with the Status-quo signal and its interval, and AUC', () => {
    render(<BacktestResults backtest={BACKTEST} dataSource={SOURCE} />)

    const comparison = screen.getByRole('figure', {
      name: `Against the Status-quo signal ${SOURCE}`,
    })
    expect(within(comparison).getByText('+0.022')).toBeInTheDocument()
    expect(within(comparison).getByText('95% interval −0.010 to +0.056')).toBeInTheDocument()
    expect(within(comparison).getByText('0.162')).toBeInTheDocument()
    expect(within(comparison).getByText('0.183')).toBeInTheDocument()
    const ranking = screen.getByRole('figure', { name: `Ranking (AUC) ${SOURCE}` })
    expect(within(ranking).getByText('0.72')).toBeInTheDocument()
    expect(within(ranking).getByText(BACKTEST.wording.auc)).toBeInTheDocument()
    expect(within(comparison).getByText(BACKTEST.wording.comparison)).toBeInTheDocument()
    expect(within(comparison).getByText(BACKTEST.wording.better_side)).toBeInTheDocument()
  })

  it('marks a failed check as failed, as the service says', () => {
    render(<BacktestResults backtest={BACKTEST} dataSource={SOURCE} />)

    expect(screen.getByText('Trust gate:')).toHaveTextContent('Trust gate: Failed')
    const checks = within(screen.getByRole('list', { name: 'Checks of the Trust gate' }))
      .getAllByRole('listitem')
      .map((item) => item.textContent)
    expect(checks).toEqual([
      'FailedCalibration Calibration slope within 0.8 to 1.2',
      'FailedBetter than the Status-quo signal The 95% interval of the Brier difference ' +
        '(status quo minus Emva) is above zero',
    ])
  })

  it('marks passed checks as passed', () => {
    const passing = {
      ...BACKTEST,
      checks: BACKTEST.checks.map((check) => ({ ...check, passed: true })),
      passed: true,
    }
    render(<BacktestResults backtest={passing} dataSource={SOURCE} />)

    expect(screen.getByText('Trust gate:')).toHaveTextContent('Trust gate: Passed')
    expect(screen.queryByText('Failed')).not.toBeInTheDocument()
  })

  it('counts the leads scored, left out and refused, with each reason', () => {
    render(<BacktestResults backtest={BACKTEST} dataSource={SOURCE} />)

    expect(cells(screen.getByRole('table', { name: `Leads in the Backtest ${SOURCE}` }))).toEqual([
      ['All leads', '100'],
      ['First fold: trained on, never scored', '20'],
      ['Left out: no Outcome yet', '20'],
      ['Refused: “Trip Type” is “Cruise”, which no training lead had.', '2'],
      ['Scored and compared', '58'],
    ])
  })

  it('says why there is nothing to draw when no lead was scored', () => {
    const empty = {
      ...BACKTEST,
      groups: [],
      slope: null,
      slope_missing_because: 'No lead was scored.',
      comparison: null,
      auc: null,
    }
    render(<BacktestResults backtest={empty} dataSource={SOURCE} />)

    expect(screen.getByText('No lead was scored, so there is nothing to draw.')).toBeInTheDocument()
    expect(
      screen.getByText('No lead was scored, so there is nothing to compare.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('No lead was scored.')).toBeInTheDocument()
    expect(screen.getByText(BACKTEST.wording.auc_missing)).toBeInTheDocument()
  })
})
