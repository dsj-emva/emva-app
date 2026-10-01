import type { components } from '@emva/api-client'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { fakeService } from './test-service.ts'
import { Training } from './Training.tsx'

type TrainingState = components['schemas']['Training']
type TrainingRunView = components['schemas']['TrainingRunView']

const ID = '7a1d2c3e-0000-4000-8000-000000000001'
const TRAINING = `/advertisers/${ID}/training`
const RUNS = `/advertisers/${ID}/training-runs`
const RULE = 'A transition’s model is learned only from at least 10 leads that made it.'

const RUN: TrainingRunView = {
  id: '5b2e0c4f-0000-4000-8000-000000000009',
  trained_at: '2026-09-15T08:30:00Z',
  transitions: [
    {
      transition: {
        from_stage: 'contact_attempted',
        to_stage: 'engaged',
        name: 'Contact attempted → Engaged',
      },
      made: 67,
      failed: 16,
      unfinished: 4,
      fitted: true,
      verdict: 'Learned',
      smoothed_rate: 0.8,
    },
    {
      transition: { from_stage: 'proposal', to_stage: 'won', name: 'Proposal → Won' },
      made: 18,
      failed: 7,
      unfinished: 4,
      fitted: false,
      verdict: 'Too few to learn',
      smoothed_rate: 0.72,
    },
  ],
}

const TRAINABLE: TrainingState = {
  trainable: true,
  not_trainable_because: null,
  rule: RULE,
  latest: null,
}

function renderTraining(client: ReturnType<typeof fakeService>['client']) {
  render(<Training client={client} advertiserId={ID} formattedAt="2026-09-15T08:00:00Z" />)
}

describe('Training', () => {
  it('holds back training, saying why, while the service says it cannot train', async () => {
    const because = 'The mapping is not confirmed yet. Nothing trains before a person confirms it.'
    const service = fakeService({
      [`GET ${TRAINING}`]: () =>
        Response.json({ ...TRAINABLE, trainable: false, not_trainable_because: because }),
    })
    renderTraining(service.client)

    const train = await screen.findByRole('button', { name: 'Train the model' })
    expect(train).toBeDisabled()
    expect(train).toHaveAccessibleDescription(because)
    expect(screen.getByText(RULE)).toBeInTheDocument()
  })

  it('trains and shows each transition’s lead counts, exactly as the service returns them', async () => {
    const service = fakeService({
      [`GET ${TRAINING}`]: () => Response.json(TRAINABLE),
      [`POST ${RUNS}`]: () => Response.json({ ...TRAINABLE, latest: RUN }, { status: 201 }),
    })
    renderTraining(service.client)

    fireEvent.click(await screen.findByRole('button', { name: 'Train the model' }))

    const table = await screen.findByRole('table', { name: 'What each transition learned from' })
    const rows = within(table)
      .getAllByRole('row')
      .map((row) => [...row.querySelectorAll('th, td')].map((cell) => cell.textContent))
    expect(rows).toEqual([
      ['Transition', 'Made', 'Failed', 'Left out', 'Model'],
      ['Contact attempted → Engaged', '67', '16', '4', 'Learned'],
      ['Proposal → Won', '18', '7', '4', 'Too few to learn: smoothed rate 72%'],
    ])
    expect(service.sentTo(`POST ${RUNS}`)).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Train again' })).toBeEnabled()
  })

  it('shows the latest training run when it opens', async () => {
    const service = fakeService({
      [`GET ${TRAINING}`]: () => Response.json({ ...TRAINABLE, latest: RUN }),
    })
    renderTraining(service.client)

    expect(
      await screen.findByRole('table', { name: 'What each transition learned from' }),
    ).toBeInTheDocument()
  })

  it('shows why the training could not be read, and offers no training', async () => {
    const detail = "The latest Training run's model could not be read from storage. Try again."
    const service = fakeService({
      [`GET ${TRAINING}`]: () => Response.json({ detail }, { status: 503 }),
    })
    renderTraining(service.client)

    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows why the service refused to train', async () => {
    const detail = 'The mapping is not confirmed yet. Nothing trains before a person confirms it.'
    const service = fakeService({
      [`GET ${TRAINING}`]: () => Response.json(TRAINABLE),
      [`POST ${RUNS}`]: () => Response.json({ detail }, { status: 409 }),
    })
    renderTraining(service.client)

    fireEvent.click(await screen.findByRole('button', { name: 'Train the model' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
  })
})
