import type { components } from '@emva/api-client'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Scoring } from './Scoring.tsx'
import { fakeService } from './test-service.ts'

type ScoringForm = components['schemas']['ScoringForm']
type ScoredLead = components['schemas']['ScoredLead']

const ID = '7a1d2c3e-0000-4000-8000-000000000001'
const FORM_PATH = `/advertisers/${ID}/scoring-form`
const SCORES = `/advertisers/${ID}/scores`

const FORM: ScoringForm = {
  inputs: [
    {
      column: 'Trip Type',
      kind: 'category',
      typical: 'Safari',
      typical_choice: 'Safari',
      choices: [
        { value: 'Safari', label: 'Safari' },
        { value: 'Honeymoon', label: 'Honeymoon' },
      ],
    },
    {
      column: 'Budget (GBP)',
      kind: 'number',
      typical: '9,250',
      typical_choice: null,
      choices: null,
    },
  ],
}

const SCORED: ScoredLead = {
  data_source: 'hand_made_test',
  chance_of_winning: 0.125,
  typical_deal_size: 12000,
  lead_score: 1500,
  explanation: {
    typical_chance: 0.2,
    steps: [
      {
        input: 'Trip Type',
        typical: 'Safari',
        value: 'Honeymoon',
        before: 0.2,
        after: 0.15,
        change: -0.05,
      },
      {
        input: 'Budget (GBP)',
        typical: '9,250',
        value: 'not given',
        before: 0.15,
        after: 0.125,
        change: -0.025,
      },
    ],
  },
}

function renderScoring(client: ReturnType<typeof fakeService>['client']) {
  render(<Scoring client={client} advertiserId={ID} />)
}

describe('Scoring', () => {
  it('offers exactly the inputs the service describes, categories from training', async () => {
    const service = fakeService({ [`GET ${FORM_PATH}`]: () => Response.json(FORM) })
    renderScoring(service.client)

    const trip = await screen.findByRole('combobox', { name: 'Trip Type' })
    expect(within(trip).getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Safari',
      'Honeymoon',
    ])
    expect(trip).toHaveValue('Safari')
    const budget = screen.getByRole('spinbutton', { name: 'Budget (GBP)' })
    expect(budget).toHaveValue(null)
    expect(budget).toHaveAccessibleDescription(
      'Typical: 9,250. Leave blank if the lead did not say.',
    )
  })

  it('starts each category at the typical choice by its value, not its label', async () => {
    const labelled: ScoringForm = {
      inputs: [
        {
          column: 'Enquiry Channel',
          kind: 'category',
          typical: 'Web form',
          typical_choice: 'web',
          choices: [
            { value: 'phone', label: 'By phone' },
            { value: 'web', label: 'Through the web form' },
          ],
        },
      ],
    }
    const service = fakeService({ [`GET ${FORM_PATH}`]: () => Response.json(labelled) })
    renderScoring(service.client)

    const channel = await screen.findByRole('combobox', { name: 'Enquiry Channel' })
    expect(channel).toHaveValue('web')
  })

  it('says before scoring which inputs are blank and will count as not given', async () => {
    const service = fakeService({ [`GET ${FORM_PATH}`]: () => Response.json(FORM) })
    renderScoring(service.client)

    const button = await screen.findByRole('button', { name: 'Score this lead' })
    expect(button).toHaveAccessibleDescription(
      'Not given, and scored as not given: Budget (GBP).',
    )

    fireEvent.change(screen.getByRole('spinbutton', { name: 'Budget (GBP)' }), {
      target: { value: '9000' },
    })

    expect(button).not.toHaveAccessibleDescription()
    expect(screen.queryByText(/scored as not given/)).not.toBeInTheDocument()
  })

  it('scores the lead and shows its chance, Lead score, deal size and explanation', async () => {
    const service = fakeService({
      [`GET ${FORM_PATH}`]: () => Response.json(FORM),
      [`POST ${SCORES}`]: () => Response.json(SCORED),
    })
    renderScoring(service.client)

    fireEvent.change(await screen.findByRole('combobox', { name: 'Trip Type' }), {
      target: { value: 'Honeymoon' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Score this lead' }))

    const explanation = await screen.findByRole('figure', { name: /Score explanation/ })
    const [sent] = service.sentTo(`POST ${SCORES}`)
    expect(await sent!.json()).toEqual({ inputs: { 'Trip Type': 'Honeymoon', 'Budget (GBP)': '' } })

    const figures = within(document.querySelector<HTMLElement>('.score-figures')!)
    expect(figures.getByText('Chance of winning').nextSibling).toHaveTextContent('12.5%')
    expect(figures.getByText('Submit score').nextSibling).toHaveTextContent('1,500')
    expect(
      figures.getByText('A Lead score: a relative measure of quality, not money.'),
    ).toBeInTheDocument()
    expect(figures.getByText('Typical deal size used').nextSibling).toHaveTextContent('12,000')
    expect(screen.getByText('On hand-made test data')).toBeInTheDocument()

    const rows = within(explanation)
      .getAllByRole('listitem')
      .filter((item) => item.classList.contains('waterfall-row'))
      .map((row) => row.textContent)
    expect(rows).toEqual([
      'Typical leadEvery number at its training mean, every category at its most common value20%',
      'Trip TypeSafari → Honeymoon−5 pts',
      'Budget (GBP)9,250 → not given−2.5 pts',
      'This leadSubmit score 1,50012.5%',
    ])
  })

  it('shows a lead equal to the typical one as no change', async () => {
    const still = {
      ...SCORED,
      chance_of_winning: 0.2,
      explanation: {
        typical_chance: 0.2,
        steps: [{ ...SCORED.explanation.steps[0]!, value: 'Safari', after: 0.2, change: 0 }],
      },
    }
    const service = fakeService({
      [`GET ${FORM_PATH}`]: () => Response.json(FORM),
      [`POST ${SCORES}`]: () => Response.json(still),
    })
    renderScoring(service.client)

    fireEvent.click(await screen.findByRole('button', { name: 'Score this lead' }))

    const explanation = await screen.findByRole('figure', { name: /Score explanation/ })
    expect(within(explanation).getByText('Safari, as typical')).toBeInTheDocument()
    expect(within(explanation).getAllByText('No change').length).toBeGreaterThan(0)
  })

  it('shows why the service refused to score the lead, and no score', async () => {
    const detail = '“Trip Type” is “Cruise”, which no training lead had.'
    const service = fakeService({
      [`GET ${FORM_PATH}`]: () => Response.json(FORM),
      [`POST ${SCORES}`]: () => Response.json({ detail }, { status: 400 }),
    })
    renderScoring(service.client)

    fireEvent.click(await screen.findByRole('button', { name: 'Score this lead' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
    expect(screen.queryByRole('figure')).not.toBeInTheDocument()
  })

  it('clears the last score when the next lead is refused', async () => {
    const detail = '“Trip Type” is “Cruise”, which no training lead had.'
    let answers = 0
    const service = fakeService({
      [`GET ${FORM_PATH}`]: () => Response.json(FORM),
      [`POST ${SCORES}`]: () =>
        answers++ === 0 ? Response.json(SCORED) : Response.json({ detail }, { status: 400 }),
    })
    renderScoring(service.client)

    fireEvent.click(await screen.findByRole('button', { name: 'Score this lead' }))
    await screen.findByRole('figure', { name: /Score explanation/ })
    fireEvent.click(screen.getByRole('button', { name: 'Score this lead' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
    expect(screen.queryByRole('figure')).not.toBeInTheDocument()
    expect(screen.queryByText('Submit score')).not.toBeInTheDocument()
  })

  it('says why there is no form before a training run', async () => {
    const detail = 'No Training run yet. Train the model before scoring a lead.'
    const service = fakeService({
      [`GET ${FORM_PATH}`]: () => Response.json({ detail }, { status: 409 }),
    })
    renderScoring(service.client)

    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
