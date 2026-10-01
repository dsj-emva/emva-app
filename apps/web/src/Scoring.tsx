import type { ApiClient, components } from '@emva/api-client'
import { type FormEvent, useEffect, useId, useState } from 'react'

import { dataSourceLabel } from './data-sources.ts'
import { refusal, UNREACHABLE } from './service-errors.ts'

type ScoringForm = components['schemas']['ScoringForm']
type ScoringInput = components['schemas']['ScoringInput']
type ScoredLead = components['schemas']['ScoredLead']

type Loaded =
  | { state: 'loading' }
  | { state: 'failed'; problem: string }
  | { state: 'loaded'; form: ScoringForm }

// Scores one new lead with the latest Training run and shows its Score explanation. Every number
// comes from the service; the screen only lays them out. Rendered afresh for each Training run.
export function Scoring({ client, advertiserId }: { client: ApiClient; advertiserId: string }) {
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' })
  const [values, setValues] = useState<Record<string, string>>({})
  const [scoring, setScoring] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [scored, setScored] = useState<ScoredLead | null>(null)
  const headingId = useId()
  const blankId = useId()

  useEffect(() => {
    client
      .GET('/advertisers/{advertiser_id}/scoring-form', {
        params: { path: { advertiser_id: advertiserId } },
      })
      .then(({ data, error, response }) => {
        if (!data) {
          setLoaded({ state: 'failed', problem: refusal(error, response) })
          return
        }
        setLoaded({ state: 'loaded', form: data })
        // Categories start at the typical lead's choice; numbers start blank.
        setValues(
          Object.fromEntries(data.inputs.map((input) => [input.column, input.typical_choice ?? ''])),
        )
      })
      .catch(() => setLoaded({ state: 'failed', problem: UNREACHABLE }))
  }, [client, advertiserId])

  async function score(event: FormEvent) {
    event.preventDefault()
    setScoring(true)
    setProblem(null)
    try {
      const { data, error, response } = await client.POST('/advertisers/{advertiser_id}/scores', {
        params: { path: { advertiser_id: advertiserId } },
        body: { inputs: values },
      })
      if (data) setScored(data)
      else {
        setScored(null)
        setProblem(refusal(error, response))
      }
    } catch {
      setScored(null)
      setProblem(UNREACHABLE)
    } finally {
      setScoring(false)
    }
  }

  return (
    <section className="scoring" aria-labelledby={headingId}>
      <h3 id={headingId}>Score one lead</h3>
      {loaded.state === 'loading' && <p className="muted">Reading the scoring form…</p>}
      {loaded.state === 'failed' && (
        <p className="problem" role="alert">
          {loaded.problem}
        </p>
      )}
      {loaded.state === 'loaded' && (
        <>
          <p className="muted">
            Enter what a new lead states on the form. It is scored with the latest training run and
            not kept.
          </p>
          <form className="scoring-form" onSubmit={score}>
            <div className="scoring-inputs">
              {loaded.form.inputs.map((input) => (
                <InputField
                  key={input.column}
                  input={input}
                  value={values[input.column] ?? ''}
                  change={(value) => setValues({ ...values, [input.column]: value })}
                />
              ))}
            </div>
            <NotGiven
              id={blankId}
              columns={loaded.form.inputs
                .map((input) => input.column)
                .filter((column) => (values[column] ?? '') === '')}
            />
            <button
              type="submit"
              className="primary"
              disabled={scoring}
              aria-describedby={blankId}
            >
              {scoring ? 'Scoring…' : 'Score this lead'}
            </button>
          </form>
          {problem && (
            <p className="problem" role="alert">
              {problem}
            </p>
          )}
          {scored && <Result scored={scored} />}
        </>
      )}
    </section>
  )
}

// The inputs left blank, which the service scores as not given (ruling 12), named before the
// person scores, so a score built on blanks is no surprise.
function NotGiven({ id, columns }: { id: string; columns: string[] }) {
  return (
    <p id={id} className="not-given" role="status">
      {columns.length > 0 && `Not given, and scored as not given: ${columns.join(', ')}.`}
    </p>
  )
}

function InputField({
  input,
  value,
  change,
}: {
  input: ScoringInput
  value: string
  change: (value: string) => void
}) {
  const id = useId()
  const hintId = useId()
  return (
    <div className="field">
      <label htmlFor={id}>{input.column}</label>
      {input.choices ? (
        <select id={id} value={value} onChange={(event) => change(event.target.value)}>
          {input.choices.map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </select>
      ) : (
        <>
          <input
            id={id}
            type="number"
            inputMode="decimal"
            step="any"
            aria-describedby={hintId}
            value={value}
            onChange={(event) => change(event.target.value)}
          />
          <p id={hintId} className="muted field-hint">
            Typical: {input.typical}. Leave blank if the lead did not say.
          </p>
        </>
      )}
    </div>
  )
}

function Result({ scored }: { scored: ScoredLead }) {
  return (
    <div className="score-result">
      <p className="eyebrow">On {dataSourceLabel(scored.data_source).toLowerCase()}</p>
      <dl className="score-figures" aria-live="polite">
        <div>
          <dt>Chance of winning</dt>
          <dd className="data">{formatChance(scored.chance_of_winning)}</dd>
        </div>
        <div className="lead-score">
          <dt>Submit score</dt>
          <dd className="data">{formatNumber(scored.lead_score)}</dd>
          <dd className="muted">A Lead score: a relative measure of quality, not money.</dd>
        </div>
        <div>
          <dt>Typical deal size used</dt>
          <dd className="data">{formatNumber(scored.typical_deal_size)}</dd>
        </div>
      </dl>
      <Waterfall scored={scored} />
    </div>
  )
}

type Row = {
  key: string
  name: string
  detail: string
  from: number
  to: number
  kind: 'total' | 'rise' | 'fall' | 'none'
  shown: string
}

function Waterfall({ scored }: { scored: ScoredLead }) {
  const captionId = useId()
  const { typical_chance: typical, steps } = scored.explanation
  const rows: Row[] = [
    {
      key: 'typical',
      name: 'Typical lead',
      detail: 'Every number at its training mean, every category at its most common value',
      from: 0,
      to: typical,
      kind: 'total',
      shown: formatChance(typical),
    },
    ...steps.map(
      (step): Row => ({
        key: step.input,
        name: step.input,
        detail:
          step.typical === step.value ? `${step.value}, as typical` : `${step.typical} → ${step.value}`,
        from: step.before,
        to: step.after,
        kind: step.change > 0 ? 'rise' : step.change < 0 ? 'fall' : 'none',
        shown: step.change === 0 ? 'No change' : formatPoints(step.change),
      }),
    ),
    {
      key: 'lead',
      name: 'This lead',
      detail: `Submit score ${formatNumber(scored.lead_score)}`,
      from: 0,
      to: scored.chance_of_winning,
      kind: 'total',
      shown: formatChance(scored.chance_of_winning),
    },
  ]
  // The axis runs from no chance to the highest chance the walk reaches.
  const top = Math.max(...rows.map((row) => row.to), typical) || 1

  return (
    <figure className="waterfall" aria-labelledby={captionId}>
      <figcaption id={captionId}>
        <strong>Score explanation</strong>
        <span className="muted">
          From the typical lead’s chance, each input changed in turn to this lead’s value, and how
          far it moved the chance of winning.
        </span>
      </figcaption>
      <ul className="waterfall-legend" aria-label="Key">
        <li>
          <span className="swatch" data-kind="total" aria-hidden="true" /> Chance of winning
        </li>
        <li>
          <span className="swatch" data-kind="rise" aria-hidden="true" /> Pushed it up
        </li>
        <li>
          <span className="swatch" data-kind="fall" aria-hidden="true" /> Pulled it down
        </li>
        <li>
          <span className="swatch" data-kind="none" aria-hidden="true" /> No change
        </li>
      </ul>
      <ol className="waterfall-rows">
        {rows.map((row) => (
          <li key={row.key} className="waterfall-row" data-kind={row.kind}>
            <span className="waterfall-label">
              <span className="waterfall-name">{row.name}</span>
              <span className="muted">{row.detail}</span>
            </span>
            <span className="waterfall-track" aria-hidden="true">
              <span
                className="waterfall-bar"
                data-kind={row.kind}
                style={{
                  left: `${(Math.min(row.from, row.to) / top) * 100}%`,
                  width: `${(Math.abs(row.to - row.from) / top) * 100}%`,
                }}
              />
            </span>
            <span className="waterfall-value data">{row.shown}</span>
          </li>
        ))}
      </ol>
      <details className="waterfall-table">
        <summary>Show as a table</summary>
        <div className="table-scroll">
          <table>
            <caption className="visually-hidden">Score explanation, step by step</caption>
            <thead>
              <tr>
                <th scope="col">Input</th>
                <th scope="col">Typical</th>
                <th scope="col">This lead</th>
                <th scope="col" className="number">
                  Chance before
                </th>
                <th scope="col" className="number">
                  Chance after
                </th>
                <th scope="col" className="number">
                  Moved
                </th>
              </tr>
            </thead>
            <tbody>
              {steps.map((step) => (
                <tr key={step.input}>
                  <th scope="row">{step.input}</th>
                  <td>{step.typical}</td>
                  <td>{step.value}</td>
                  <td className="number data">{formatChance(step.before)}</td>
                  <td className="number data">{formatChance(step.after)}</td>
                  <td className="number data">
                    {step.change === 0 ? 'No change' : formatPoints(step.change)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </figure>
  )
}

function formatChance(chance: number): string {
  return new Intl.NumberFormat(undefined, { style: 'percent', maximumFractionDigits: 1 }).format(
    chance,
  )
}

// A move of the chance in percentage points, signed.
function formatPoints(change: number): string {
  const points = new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 2,
    signDisplay: 'always',
  }).format(change * 100)
  return `${points.replace('-', '−')} pts`
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value)
}
