import type { ApiClient, components } from '@emva/api-client'
import { useEffect, useId, useState } from 'react'

import { refusal, UNREACHABLE } from './service-errors.ts'

type TrainingRunView = components['schemas']['TrainingRunView']
type TransitionResult = components['schemas']['TransitionResult']

type Latest =
  | { state: 'closed' }
  | { state: 'loading' }
  | { state: 'none' }
  | { state: 'trained'; run: TrainingRunView }

export function Training({
  client,
  advertiserId,
  ready,
}: {
  client: ApiClient
  advertiserId: string
  // Whether the mapping is confirmed and its data formatted, as the service says.
  ready: boolean
}) {
  const [latest, setLatest] = useState<Latest>({ state: ready ? 'loading' : 'closed' })
  const [training, setTraining] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const headingId = useId()
  const hintId = useId()
  const path = { params: { path: { advertiser_id: advertiserId } } }

  useEffect(() => {
    if (!ready) return
    client
      .GET('/advertisers/{advertiser_id}/training-runs/latest', {
        params: { path: { advertiser_id: advertiserId } },
      })
      .then(({ data }) => setLatest(data ? { state: 'trained', run: data } : { state: 'none' }))
      .catch(() => setLatest({ state: 'none' }))
  }, [client, advertiserId, ready])

  async function train() {
    setTraining(true)
    setProblem(null)
    try {
      const { data, error, response } = await client.POST(
        '/advertisers/{advertiser_id}/training-runs',
        path,
      )
      if (data) setLatest({ state: 'trained', run: data })
      else setProblem(refusal(error, response))
    } catch {
      setProblem(UNREACHABLE)
    } finally {
      setTraining(false)
    }
  }

  const trained = latest.state === 'trained'
  return (
    <section className="training" aria-labelledby={headingId}>
      <h3 id={headingId}>Train the model</h3>
      <p className="muted">
        One model per transition, from Contact attempted to Won, learned from the formatted
        leads. A transition is learned only from at least 10 leads that made it and 10 that
        failed it.
      </p>
      <div className="training-action">
        <button
          type="button"
          className="primary"
          disabled={!ready || training || latest.state === 'loading'}
          aria-describedby={ready ? undefined : hintId}
          onClick={train}
        >
          {training ? 'Training…' : trained ? 'Train again' : 'Train the model'}
        </button>
        {!ready && (
          <p id={hintId} className="muted">
            Training opens once the mapping is confirmed and its data formatted.
          </p>
        )}
        {trained && (
          <p className="muted" aria-live="polite">
            Trained <time dateTime={latest.run.trained_at}>{formatTime(latest.run.trained_at)}</time>
            .
          </p>
        )}
      </div>
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
      {trained && <Transitions transitions={latest.run.transitions} />}
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
            <tr key={t.name}>
              <th scope="row">{t.name}</th>
              <td className="number data">{t.made}</td>
              <td className="number data">{t.failed}</td>
              <td className="number data">{t.unfinished}</td>
              <td>
                {t.learned ? (
                  <span className="learned">Learned</span>
                ) : (
                  <span className="too-few">
                    Too few to learn:{' '}
                    {t.observed_rate === null
                      ? 'no lead has finished it yet'
                      : `observed rate ${formatRate(t.observed_rate)}`}
                  </span>
                )}
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
