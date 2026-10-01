import type { components } from '@emva/api-client'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ReviewStep } from './ReviewStep.tsx'
import { fakeService } from './test-service.ts'

type Advertiser = components['schemas']['Advertiser']
type Mapping = components['schemas']['Mapping']
type MappingReview = components['schemas']['MappingReview']

const ID = '7a1d2c3e-0000-4000-8000-000000000001'
const ADVERTISER = `/advertisers/${ID}`

const BOTH_UPLOADED: Advertiser = {
  id: ID,
  name: 'Savanna Journeys',
  data_source: 'hand_made_test',
  leads_file: {
    kind: 'leads',
    file_name: 'leads.csv',
    uploaded_at: '2026-09-15T08:45:00Z',
    row_count: 101,
    column_names: ['Lead ID', 'Created Date', 'Email', 'Trip Type'],
  },
  stage_history_file: {
    kind: 'stage-history',
    file_name: 'stage_history.csv',
    uploaded_at: '2026-09-15T08:46:00Z',
    row_count: 418,
    column_names: ['Lead ID', 'Stage', 'Changed At', 'Deal Value'],
  },
  review_available: true,
}

const EMPTY: Mapping = {
  leads: {
    lead_id: null,
    submitted_at: null,
    name: null,
    email: null,
    phone: null,
    inputs: {},
  },
  stage_history: { lead_id: null, crm_stage: null, changed_at: null, deal_value: null },
  crm_stages: {},
  typical_deal_size: null,
}

const PLACES: MappingReview['places'] = [
  { place: 'submitted', name: 'Submitted' },
  { place: 'contact_attempted', name: 'Contact attempted' },
  { place: 'engaged', name: 'Engaged' },
  { place: 'qualified', name: 'Qualified' },
  { place: 'proposal', name: 'Proposal' },
  { place: 'won', name: 'Won' },
  { place: 'lost', name: 'Lost' },
]

const CRM_STAGES = [
  { name: 'New enquiry', row_count: 98 },
  { name: 'Closed won', row_count: 19 },
]

function review(mapping: Mapping, rest: Partial<MappingReview> = {}): MappingReview {
  return {
    mapping,
    confirmed_at: null,
    problems: ['Enter the typical deal size.'],
    crm_stages: mapping.stage_history.crm_stage ? CRM_STAGES : [],
    places: PLACES,
    ...rest,
  }
}

// A service that keeps the draft it is sent, as the real one does.
function draftService(start: MappingReview = review(EMPTY)) {
  let current = start
  const service = fakeService({
    [`GET ${ADVERTISER}/files/leads/columns`]: () =>
      Response.json([
        { name: 'Lead ID', examples: ['L-1001'] },
        { name: 'Created Date', examples: ['2024-01-04 09:12'] },
        { name: 'Email', examples: ['ada.fenwick@example.com'] },
        { name: 'Trip Type', examples: ['Safari', 'Family holiday'] },
      ]),
    [`GET ${ADVERTISER}/files/stage-history/columns`]: () =>
      Response.json([
        { name: 'Lead ID', examples: ['L-1001'] },
        { name: 'Stage', examples: ['New enquiry'] },
        { name: 'Changed At', examples: ['2024-01-04 09:12'] },
        { name: 'Deal Value', examples: ['19250'] },
      ]),
    [`GET ${ADVERTISER}/mapping`]: () => Response.json(current),
    [`PUT ${ADVERTISER}/mapping`]: async (request) => {
      current = review((await request.json()) as Mapping)
      return Response.json(current)
    },
  })
  return service
}

async function lastSaved(service: ReturnType<typeof draftService>): Promise<Mapping> {
  await waitFor(() => expect(service.sentTo(`PUT ${ADVERTISER}/mapping`).length).toBeGreaterThan(0))
  const saves = service.sentTo(`PUT ${ADVERTISER}/mapping`)
  return (await saves[saves.length - 1].clone().json()) as Mapping
}

async function region(name: string) {
  return within(await screen.findByRole('region', { name }))
}

const LEADS = 'Leads file: leads.csv'
const HISTORY = 'Stage-history file: stage_history.csv'

function choose(control: HTMLElement, value: string) {
  fireEvent.change(control, { target: { value } })
}

describe('ReviewStep', () => {
  it('shows the draft the service kept', async () => {
    const saved = {
      ...EMPTY,
      leads: { ...EMPTY.leads, lead_id: 'Lead ID', inputs: { 'Trip Type': 'category' as const } },
      stage_history: { ...EMPTY.stage_history, crm_stage: 'Stage' },
      crm_stages: { 'Closed won': 'won' as const },
      typical_deal_size: 12000,
    }
    render(<ReviewStep client={draftService(review(saved)).client} advertiser={BOTH_UPLOADED} />)

    const leads = await region(LEADS)
    expect(await leads.findByLabelText('Lead identifier')).toHaveValue('Lead ID')
    expect(await leads.findByLabelText('“Trip Type” as an input')).toHaveValue('category')
    expect(screen.getByLabelText('“Closed won” on the ladder')).toHaveValue('won')
    expect(screen.getByLabelText('“New enquiry” on the ladder')).toHaveValue('')
    expect(screen.getByLabelText('Typical deal size')).toHaveValue(12000)
  })

  it('saves the draft as the person marks each column', async () => {
    const service = draftService()
    render(<ReviewStep client={service.client} advertiser={BOTH_UPLOADED} />)
    const leads = await region(LEADS)

    choose(await leads.findByLabelText('Lead identifier'), 'Lead ID')
    await waitFor(async () => expect((await lastSaved(service)).leads.lead_id).toBe('Lead ID'))
    choose(leads.getByLabelText('Email (scrambled)'), 'Email')
    choose(await leads.findByLabelText('“Trip Type” as an input'), 'category')

    await waitFor(async () =>
      expect((await lastSaved(service)).leads).toEqual({
        ...EMPTY.leads,
        lead_id: 'Lead ID',
        email: 'Email',
        inputs: { 'Trip Type': 'category' },
      }),
    )
  })

  it('places each CRM stage of the marked column on the ladder or on Lost', async () => {
    const service = draftService()
    render(<ReviewStep client={service.client} advertiser={BOTH_UPLOADED} />)
    const history = await region(HISTORY)

    choose(await history.findByLabelText('CRM stage'), 'Stage')
    const stages = await screen.findByRole('table', { name: 'CRM stages' })
    expect(within(stages).getByRole('row', { name: /New enquiry 98/ })).toBeInTheDocument()
    const placeOptions = within(screen.getByLabelText('“Closed won” on the ladder')).getAllByRole(
      'option',
    )
    expect(placeOptions.map((option) => option.textContent)).toEqual([
      'Not placed',
      'Submitted',
      'Contact attempted',
      'Engaged',
      'Qualified',
      'Proposal',
      'Won',
      'Lost',
    ])
    choose(screen.getByLabelText('“Closed won” on the ladder'), 'won')

    await waitFor(async () =>
      expect((await lastSaved(service)).crm_stages).toEqual({ 'Closed won': 'won' }),
    )
  })

  it('saves the typical deal size the person enters', async () => {
    const service = draftService()
    render(<ReviewStep client={service.client} advertiser={BOTH_UPLOADED} />)

    fireEvent.change(await screen.findByLabelText('Typical deal size'), {
      target: { value: '12500' },
    })

    await waitFor(async () => expect((await lastSaved(service)).typical_deal_size).toBe(12500))
  })

  it('shows every reason the service gives for not confirming yet, and holds back confirm', async () => {
    const reasons = [
      "Mark the leads file's column holding the lead identifier.",
      'Place at least one CRM stage on Won.',
    ]
    render(
      <ReviewStep
        client={draftService(review(EMPTY, { problems: reasons })).client}
        advertiser={BOTH_UPLOADED}
      />,
    )

    const list = await screen.findByRole('list', { name: 'Before you can confirm' })
    expect(within(list).getAllByRole('listitem').map((item) => item.textContent)).toEqual(reasons)
    expect(screen.getByRole('button', { name: 'Confirm the mapping' })).toBeDisabled()
  })

  it('confirms as a separate act and then shows the mapping confirmed and when', async () => {
    const confirmed = review(EMPTY, { problems: [], confirmed_at: '2026-09-20T16:30:00Z' })
    const routes = fakeService({
      [`GET ${ADVERTISER}/files/leads/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/files/stage-history/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/mapping`]: () => Response.json(review(EMPTY, { problems: [] })),
      [`POST ${ADVERTISER}/mapping/confirmation`]: () => Response.json(confirmed),
    })
    render(<ReviewStep client={routes.client} advertiser={BOTH_UPLOADED} />)
    expect(routes.sentTo(`POST ${ADVERTISER}/mapping/confirmation`)).toHaveLength(0)

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm the mapping' }))

    const status = await screen.findByRole('status', { name: 'Mapping confirmed' })
    expect(status).toHaveTextContent('Confirmed')
    expect(status).toHaveTextContent('2026')
    expect(status).toHaveTextContent('can no longer be changed')
    expect(screen.getByLabelText('Typical deal size')).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Confirm the mapping' })).not.toBeInTheDocument()
  })

  it('shows why the service refused to confirm', async () => {
    const service = fakeService({
      [`GET ${ADVERTISER}/files/leads/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/files/stage-history/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/mapping`]: () => Response.json(review(EMPTY, { problems: [] })),
      [`POST ${ADVERTISER}/mapping/confirmation`]: () =>
        Response.json({ detail: 'The mapping is already confirmed.' }, { status: 409 }),
    })
    render(<ReviewStep client={service.client} advertiser={BOTH_UPLOADED} />)

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm the mapping' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('The mapping is already confirmed.')
  })
})
