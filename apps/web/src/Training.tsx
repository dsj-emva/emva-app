import type { ApiClient, components } from '@emva/api-client'
import { useEffect, useId, useState } from 'react'

import { refusal, UNREACHABLE } from './service-errors.ts'

type TrainingState = components['schemas']['Training']
type TransitionResult = components['schemas']['TransitionResult']

type Loaded =
  | { state: 'loading' }
  | { state: 'failed'; problem: string }
  | { state: 'loaded'; training: TrainingState }

export function Training({
  client,
  advertiserId,
  formattedAt,
}: {
  client: ApiClient
  advertiserId: string
  // When the advertiser's data was formatted; whether training can run is asked again when it
  // changes.
  formattedAt: string | null
}) {
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' })
  const [training, setTraining] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const headingId = useId()
  const reasonId = useId()

  useEffect(() => {
    client
      .GET('/advertisers/{advertiser_id}/training', {
        params: { path: { advertiser_id: advertiserId } },
      })
      .then(({ data, error, response }) =>
        setLoaded(
          data
            ? { state: 'loaded', training: data }
            : { state: 'failed', problem: refusal(error, response) },
        ),
      )
      .catch(() => setLoaded({ state: 'failed', problem: UNREACHABLE }))
  }, [client, advertiserId, formattedAt])

  async function train() {
    setTraining(true)
    setProblem(null)
    try {
      const { data, error, response } = await client.POST(
        '/advertisers/{advertiser_id}/training-runs',
        { params: { path: { advertiser_id: advertiserId } } },
      )
      if (data) setLoaded({ state: 'loaded', training: data })
      else setProblem(refusal(error, response))
    } catch {
      setProblem(UNREACHABLE)
    } finally {
      setTraining(false)
    }
  }

  return (
    <section className="training" aria-labelledby={headingId}>
      <h3 id={headingId}>Train the model</h3>
      {loaded.state === 'loading' && <p className="muted">Reading the training…</p>}
      {loaded.state === 'failed' && (
        <p className="problem" role="alert">
          {loaded.problem}
        </p>
      )}
      {loaded.state === 'loaded' && (
        <>
          <p className="muted">{loaded.training.rule}</p>
          <div className="training-action">
            <button
              type="button"
              className="primary"
              disabled={!loaded.training.trainable || training}
              aria-describedby={loaded.training.trainable ? undefined : reasonId}
              onClick={train}
            >
              {training ? 'Training…' : loaded.training.latest ? 'Train again' : 'Train the model'}
            </button>
            {loaded.training.not_trainable_because && (
              <p id={reasonId} className="muted">
                {loaded.training.not_trainable_because}
              </p>
            )}
            {loaded.training.latest && (
              <p className="muted" aria-live="polite">
                Trained{' '}
                <time dateTime={loaded.training.latest.trained_at}>
                  {formatTime(loaded.training.latest.trained_at)}
                </time>
                .
              </p>
            )}
          </div>
          {problem && (
            <p className="problem" role="alert">
              {problem}
            </p>
          )}
          {loaded.training.latest && (
            <Transitions transitions={loaded.training.latest.transitions} />
          )}
        </>
      )}
    </section>
  )
}

function Transitions({ transitions }: { transitions: TransitionResult[] }) {
  return (
    <div className="table-scroll">
      <table>
        <caption>What each transition learned from</caption>
        <thead>
          <tr>
            <th scope="col">Transition</th>
            <th scope="col" className="number">
              Made
            </th>
            <th scope="col" className="number">
              Failed
            </th>
            <th scope="col" className="number">
              Left out
            </th>
            <th scope="col">Model</th>
          </tr>
        </thead>
        <tbody>
          {transitions.map((t) => (
            <tr key={t.transition.name}>
              <th scope="row">{t.transition.name}</th>
              <td className="number data">{t.made}</td>
              <td className="number data">{t.failed}</td>
              <td className="number data">{t.unfinished}</td>
              <td>
                <span className={t.fitted ? 'learned' : 'too-few'}>
                  {t.verdict}
                  {!t.fitted &&
                    t.smoothed_rate !== null &&
                    `: smoothed rate ${formatRate(t.smoothed_rate)}`}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">
        Left out: leads that reached the transition but have neither made nor failed it yet.
        Neglected leads, never attempted, are left out of every transition.
      </p>
    </div>
  )
}

function formatRate(rate: number): string {
  return new Intl.NumberFormat(undefined, { style: 'percent', maximumFractionDigits: 0 }).format(
    rate,
  )
}

function formatTime(iso: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(iso),
  )
}
