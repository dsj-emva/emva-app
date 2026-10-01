import type { components } from '@emva/api-client'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { fakeService } from './test-service.ts'
import { Training } from './Training.tsx'

type TrainingRunView = components['schemas']['TrainingRunView']

const ID = '7a1d2c3e-0000-4000-8000-000000000001'
const RUNS = `/advertisers/${ID}/training-runs`

const RUN: TrainingRunView = {
  id: '5b2e0c4f-0000-4000-8000-000000000009',
  trained_at: '2026-09-15T08:30:00Z',
  transitions: [
    {
      from_stage: 'contact_attempted',
      to_stage: 'engaged',
      name: 'Contact attempted → Engaged',
      made: 67,
      failed: 16,
      unfinished: 4,
      learned: true,
      observed_rate: 0.807,
    },
    {
      from_stage: 'proposal',
      to_stage: 'won',
      name: 'Proposal → Won',
      made: 18,
      failed: 7,
      unfinished: 4,
      learned: false,
      observed_rate: 0.72,
    },
  ],
}

function notTrainedYet() {
  return Response.json({ detail: 'The model has not been trained yet.' }, { status: 404 })
}

describe('Training', () => {
  it('holds back training until the mapping is confirmed and its data formatted', () => {
    const service = fakeService({})
    render(<Training client={service.client} advertiserId={ID} ready={false} />)

    const train = screen.getByRole('button', { name: 'Train the model' })
    expect(train).toBeDisabled()
    expect(train).toHaveAccessibleDescription(
      'Training opens once the mapping is confirmed and its data formatted.',
    )
    expect(service.sentTo(`GET ${RUNS}/latest`)).toEqual([])
  })

  it('trains and shows each transition’s lead counts, exactly as the service returns them', async () => {
    const service = fakeService({
      [`GET ${RUNS}/latest`]: notTrainedYet,
      [`POST ${RUNS}`]: () => Response.json(RUN, { status: 201 }),
    })
    render(<Training client={service.client} advertiserId={ID} ready />)

    fireEvent.click(await screen.findByRole('button', { name: 'Train the model' }))

    const table = await screen.findByRole('table', { name: 'What each transition learned from' })
    const rows = within(table)
      .getAllByRole('row')
      .map((row) => [...row.querySelectorAll('th, td')].map((cell) => cell.textContent))
    expect(rows).toEqual([
      ['Transition', 'Made', 'Failed', 'Left out', 'Model'],
      ['Contact attempted → Engaged', '67', '16', '4', 'Learned'],
      ['Proposal → Won', '18', '7', '4', 'Too few to learn: observed rate 72%'],
    ])
    expect(service.sentTo(`POST ${RUNS}`)).toHaveLength(1)
  })

  it('shows the latest training run when it opens', async () => {
    const service = fakeService({ [`GET ${RUNS}/latest`]: () => Response.json(RUN) })
    render(<Training client={service.client} advertiserId={ID} ready />)

    expect(
      await screen.findByRole('table', { name: 'What each transition learned from' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Train again' })).toBeEnabled()
  })

  it('says when no lead has made or failed a transition yet', async () => {
    const empty = { ...RUN.transitions[1], made: 0, failed: 0, observed_rate: null }
    const service = fakeService({
      [`GET ${RUNS}/latest`]: () => Response.json({ ...RUN, transitions: [empty] }),
    })
    render(<Training client={service.client} advertiserId={ID} ready />)

    expect(
      await screen.findByRole('cell', { name: 'Too few to learn: no lead has finished it yet' }),
    ).toBeInTheDocument()
  })

  it('shows why the service refused to train', async () => {
    const detail = 'The mapping is not confirmed yet. Nothing trains before a person confirms it.'
    const service = fakeService({
      [`GET ${RUNS}/latest`]: notTrainedYet,
      [`POST ${RUNS}`]: () => Response.json({ detail }, { status: 409 }),
    })
    render(<Training client={service.client} advertiserId={ID} ready />)

    fireEvent.click(await screen.findByRole('button', { name: 'Train the model' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
  })
})
