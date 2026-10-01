import type { components } from '@emva/api-client'
import { useId } from 'react'

type Backtest = components['schemas']['Backtest']
type Check = components['schemas']['Check']
type Group = components['schemas']['Group']
type Comparison = components['schemas']['Comparison']
type Wording = components['schemas']['Wording']

// The results of a Training run's Backtest. Every number, label and threshold comes from the
// service; the screen only draws and formats them.
export function BacktestResults({
  backtest,
  dataSource,
}: {
  backtest: Backtest
  // The label every number carries, e.g. "on hand-made test data".
  dataSource: string
}) {
  const headingId = useId()
  const aucId = useId()
  return (
    <section className="results" aria-labelledby={headingId}>
      <div className="results-head">
        <h3 id={headingId}>Backtest results</h3>
        <p className="source-label">Every number here is {dataSource}</p>
      </div>

      <TrustGate checks={backtest.checks} passed={backtest.passed} />

      <div className="results-grid">
        <Calibration
          groups={backtest.groups}
          slope={backtest.slope}
          slopeMissingBecause={backtest.slope_missing_because}
          wording={backtest.wording}
          dataSource={dataSource}
        />
        <div className="results-side">
          <StatusQuo
            comparison={backtest.comparison}
            wording={backtest.wording}
            dataSource={dataSource}
          />
          <figure className="figure" aria-labelledby={aucId}>
            <figcaption id={aucId}>Ranking (AUC) {dataSource}</figcaption>
            <p className="figure-value data">{backtest.auc === null ? '—' : fixed(backtest.auc)}</p>
            <p className="muted">
              {backtest.auc === null ? backtest.wording.auc_missing : backtest.wording.auc}
            </p>
          </figure>
        </div>
      </div>

      <Counts counts={backtest.counts} dataSource={dataSource} asOf={backtest.as_of} />

      <details className="rules">
        <summary>How the Backtest is run</summary>
        <ul>
          {backtest.rules.map((rule) => (
            <li key={rule}>{rule}</li>
          ))}
        </ul>
      </details>
    </section>
  )
}

function TrustGate({ checks, passed }: { checks: Check[]; passed: boolean }) {
  return (
    <div className="trust-gate">
      <p className="gate-verdict">
        Trust gate: <Mark passed={passed} />
      </p>
      <ul className="checks" aria-label="Checks of the Trust gate">
        {checks.map((check) => (
          <li key={check.name}>
            <Mark passed={check.passed} />
            <span>
              <strong>{check.name}</strong>
              <span className="muted"> {check.threshold}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

function Mark({ passed }: { passed: boolean }) {
  return (
    <span className={passed ? 'mark pass' : 'mark fail'}>
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
        {passed ? (
          <path d="M3 8.5l3 3 7-7" fill="none" stroke="currentColor" strokeWidth="2" />
        ) : (
          <path d="M4 4l8 8M12 4l-8 8" fill="none" stroke="currentColor" strokeWidth="2" />
        )}
      </svg>
      {passed ? 'Passed' : 'Failed'}
    </span>
  )
}

// The chart's frame, in SVG units.
const SIZE = 320
const PAD = { left: 48, right: 16, top: 16, bottom: 44 }
const PLOT = SIZE - PAD.left - PAD.right
const TICKS = [0, 0.25, 0.5, 0.75, 1]

function x(chance: number): number {
  return PAD.left + chance * PLOT
}

function y(rate: number): number {
  return PAD.top + (1 - rate) * PLOT
}

function Calibration({
  groups,
  slope,
  slopeMissingBecause,
  wording,
  dataSource,
}: {
  groups: Group[]
  slope: number | null
  slopeMissingBecause: string | null
  wording: Wording
  dataSource: string
}) {
  const titleId = useId()
  return (
    <figure className="figure calibration" aria-labelledby={titleId}>
      <figcaption id={titleId}>Calibration {dataSource}</figcaption>
      <p className="figure-value data">
        Slope {slope === null ? '—' : fixed(slope, 3)}
      </p>
      {slopeMissingBecause && <p className="muted">{slopeMissingBecause}</p>}
      {groups.length === 0 ? (
        <p className="muted">No lead was scored, so there is nothing to draw.</p>
      ) : (
        <>
          <svg
            className="calibration-chart"
            viewBox={`0 0 ${SIZE} ${SIZE}`}
            role="img"
            aria-labelledby={titleId}
            aria-describedby={`${titleId}-summary`}
          >
            {TICKS.map((tick) => (
              <g key={tick}>
                <line className="grid" x1={x(0)} x2={x(1)} y1={y(tick)} y2={y(tick)} />
                <line className="grid" x1={x(tick)} x2={x(tick)} y1={y(0)} y2={y(1)} />
                <text className="tick" x={PAD.left - 8} y={y(tick)} textAnchor="end" dy="0.32em">
                  {percent(tick)}
                </text>
                <text className="tick" x={x(tick)} y={y(0) + 18} textAnchor="middle">
                  {percent(tick)}
                </text>
              </g>
            ))}
            <line className="axis" x1={x(0)} x2={x(1)} y1={y(0)} y2={y(0)} />
            <line className="reference" x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} />
            <text
              className="reference-label"
              transform={`translate(${x(0.78)} ${y(0.78)}) rotate(-45)`}
              dy={-6}
              textAnchor="middle"
            >
              Perfect calibration
            </text>
            {groups.map((group, i) => (
              <circle
                key={i}
                className="point"
                cx={x(group.predicted)}
                cy={y(group.actual)}
                r={5}
                tabIndex={0}
                aria-label={groupLabel(group)}
              >
                <title>{groupLabel(group)}</title>
              </circle>
            ))}
            <text className="axis-title" x={x(0.5)} y={SIZE - 6} textAnchor="middle">
              Predicted chance of winning
            </text>
            <text
              className="axis-title"
              transform={`translate(12 ${y(0.5)}) rotate(-90)`}
              textAnchor="middle"
            >
              Actual win rate
            </text>
          </svg>
          <p id={`${titleId}-summary`} className="muted">
            {wording.calibration}
          </p>
          <div className="table-scroll">
            <table>
              <caption>Calibration groups {dataSource}</caption>
              <thead>
                <tr>
                  <th scope="col" className="number">
                    Leads
                  </th>
                  <th scope="col" className="number">
                    Predicted
                  </th>
                  <th scope="col" className="number">
                    Actual
                  </th>
                </tr>
              </thead>
              <tbody>
                {groups.map((group, i) => (
                  <tr key={i}>
                    <td className="number data">{group.leads}</td>
                    <td className="number data">{percent(group.predicted)}</td>
                    <td className="number data">{percent(group.actual)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </figure>
  )
}

function StatusQuo({
  comparison,
  wording,
  dataSource,
}: {
  comparison: Comparison | null
  wording: Wording
  dataSource: string
}) {
  const captionId = useId()
  return (
    <figure className="figure" aria-labelledby={captionId}>
      <figcaption id={captionId}>Against the Status-quo signal {dataSource}</figcaption>
      {comparison === null ? (
        <p className="muted">No lead was scored, so there is nothing to compare.</p>
      ) : (
        <>
          <p className="figure-value data">{signed(comparison.difference)}</p>
          <p className="data">
            95% interval {signed(comparison.interval_low)} to {signed(comparison.interval_high)}
          </p>
          <Interval comparison={comparison} betterSide={wording.better_side} />
          <dl className="briers">
            <div>
              <dt>Emva’s Brier score</dt>
              <dd className="data">{fixed(comparison.emva_brier, 3)}</dd>
            </div>
            <div>
              <dt>Status quo’s Brier score</dt>
              <dd className="data">{fixed(comparison.status_quo_brier, 3)}</dd>
            </div>
          </dl>
          <p className="muted">{wording.comparison}</p>
        </>
      )}
    </figure>
  )
}

// The interval drawn against zero, on a scale wide enough for both.
function Interval({ comparison, betterSide }: { comparison: Comparison; betterSide: string }) {
  const width = 280
  const pad = 12
  const reach = Math.max(Math.abs(comparison.interval_low), Math.abs(comparison.interval_high))
  const at = (value: number) => pad + ((value / (reach || 1) + 1) / 2) * (width - 2 * pad)
  return (
    <svg className="interval" viewBox={`0 0 ${width} 48`} aria-hidden="true">
      <line className="zero" x1={at(0)} x2={at(0)} y1={6} y2={30} />
      <text className="tick" x={at(0)} y={44} textAnchor="middle">
        0
      </text>
      <text className="tick" x={width - pad} y={44} textAnchor="end">
        {betterSide}
      </text>
      <line
        className="range"
        x1={at(comparison.interval_low)}
        x2={at(comparison.interval_high)}
        y1={18}
        y2={18}
      />
      <circle className="point" cx={at(comparison.difference)} cy={18} r={5} />
    </svg>
  )
}

function Counts({
  counts,
  dataSource,
  asOf,
}: {
  counts: Backtest['counts']
  dataSource: string
  asOf: string
}) {
  return (
    <div className="table-scroll">
      <table className="backtest-counts">
        <caption>Leads in the Backtest {dataSource}</caption>
        <tbody>
          <tr>
            <th scope="row">All leads</th>
            <td className="number data">{counts.leads}</td>
          </tr>
          <tr>
            <th scope="row">First fold: trained on, never scored</th>
            <td className="number data">{counts.training_only}</td>
          </tr>
          <tr>
            <th scope="row">Left out: no Outcome yet</th>
            <td className="number data">{counts.no_outcome_yet}</td>
          </tr>
          {counts.refused.map((refused) => (
            <tr key={refused.reason}>
              <th scope="row">Refused: {refused.reason}</th>
              <td className="number data">{refused.leads}</td>
            </tr>
          ))}
          <tr className="total">
            <th scope="row">Scored and compared</th>
            <td className="number data">{counts.scored}</td>
          </tr>
        </tbody>
      </table>
      <p className="muted">
        Outcomes as known on <time dateTime={asOf}>{formatTime(asOf)}</time>.
      </p>
    </div>
  )
}

function groupLabel(group: Group): string {
  return `${group.leads} leads: predicted ${percent(group.predicted)}, won ${percent(group.actual)}`
}

function percent(rate: number): string {
  return new Intl.NumberFormat(undefined, { style: 'percent', maximumFractionDigits: 0 }).format(
    rate,
  )
}

function fixed(value: number, digits = 2): string {
  return value.toFixed(digits)
}

function signed(value: number): string {
  return `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value).toFixed(3)}`
}

function formatTime(iso: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(iso),
  )
}
