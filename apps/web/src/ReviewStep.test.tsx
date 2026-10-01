import type { components } from '@emva/api-client'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ReviewStep } from './ReviewStep.tsx'
import { CHOICES } from './test-mapping.ts'
import { fakeService } from './test-service.ts'

type Advertiser = components['schemas']['Advertiser']
type Summary = components['schemas']['Summary']
type Mapping = components['schemas']['Mapping']
type MappingReview = components['schemas']['MappingReview']

const ID = '7a1d2c3e-0000-4000-8000-000000000001'
const ADVERTISER = `/advertisers/${ID}`

const BOTH_UPLOADED: Advertiser = {
  id: ID,
  name: 'Savanna Journeys',
  data_source: 'hand_made_test',
  data_source_label: 'on hand-made test data',
  leads_file: {
    kind: 'leads',
    file_name: 'leads.csv',
    uploaded_at: '2026-09-15T08:45:00Z',
    row_count: 101,
    column_names: ['Lead ID', 'Created Date', 'Email', 'Trip Type'],
    raw_kept: true,
  },
  stage_history_file: {
    kind: 'stage-history',
    file_name: 'stage_history.csv',
    uploaded_at: '2026-09-15T08:46:00Z',
    row_count: 418,
    column_names: ['Lead ID', 'Stage', 'Changed At', 'Deal Value'],
    raw_kept: true,
  },
  review_available: true,
  mapping_confirmed_at: null,
}

const FORMATTED_AND_DELETED: Advertiser = {
  ...BOTH_UPLOADED,
  leads_file: { ...BOTH_UPLOADED.leads_file!, raw_kept: false },
  stage_history_file: { ...BOTH_UPLOADED.stage_history_file!, raw_kept: false },
  mapping_confirmed_at: '2026-09-20T16:30:00Z',
}

const EMPTY: Mapping = {
  leads: {
    lead_id: null,
    submitted_at: null,
    name: null,
    email: null,
    phone: null,
    country: null,
    currency: null,
    inputs: {},
  },
  stage_history: { lead_id: null, crm_stage: null, changed_at: null, deal_value: null },
  crm_stages: {},
  typical_deal_size: null,
  date_order: null,
  time_zone: 'UTC',
}

const CRM_STAGES = [
  { name: 'New enquiry', row_count: 98 },
  { name: 'Closed won', row_count: 19 },
]

const FORMATTED: Summary = {
  lead_count: 100,
  won: 18,
  lost: 58,
  no_outcome_yet: 24,
  neglected: 13,
  phones_without_country: 2,
  unreadable: [
    {
      file: 'leads',
      reason: 'The submission time cannot be read.',
      count: 1,
      first_rows: [101],
    },
    {
      file: 'stage-history',
      reason: 'The lead is not in the leads file.',
      count: 12,
      first_rows: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    },
  ],
}

function review(mapping: Mapping, rest: Partial<MappingReview> = {}): MappingReview {
  return {
    mapping,
    confirmed_at: null,
    formatted_at: null,
    formatting: null,
    personal_data: null,
    still_to_do: null,
    problems: ['Enter the typical deal size.'],
    crm_stages: mapping.stage_history.crm_stage ? CRM_STAGES : [],
    ...CHOICES,
    ...rest,
  }
}

const NOT_TRAINABLE = {
  trainable: false,
  not_trainable_because:
    'The mapping is not confirmed yet. Nothing trains before a person confirms it.',
  rule: 'A transition’s model is learned only from at least 10 leads that made it.',
  left_out: 'Left out: leads that have neither made nor failed it yet.',
  latest: null,
}

// The service, answering whether training can run unless a test says otherwise.
function reviewService(routes: Parameters<typeof fakeService>[0]) {
  return fakeService({
    [`GET ${ADVERTISER}/training`]: () => Response.json(NOT_TRAINABLE),
    ...routes,
  })
}

// A service that keeps the draft it is sent, as the real one does.
function draftService(start: MappingReview = review(EMPTY)) {
  let current = start
  const service = reviewService({
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

function renderReview(
  client: ReturnType<typeof fakeService>['client'],
  onChanged = () => {},
  advertiser: Advertiser = BOTH_UPLOADED,
) {
  render(<ReviewStep client={client} advertiser={advertiser} onChanged={onChanged} />)
}

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
    renderReview(draftService(review(saved)).client)

    const leads = await region(LEADS)
    expect(await leads.findByLabelText('Lead identifier')).toHaveValue('Lead ID')
    expect(await leads.findByLabelText('“Trip Type” as an input')).toHaveValue('category')
    expect(screen.getByLabelText('“Closed won” on the ladder')).toHaveValue('won')
    expect(screen.getByLabelText('“New enquiry” on the ladder')).toHaveValue('')
    expect(screen.getByLabelText('Typical deal size')).toHaveValue(12000)
  })

  it('saves the draft as the person marks each column', async () => {
    const service = draftService()
    renderReview(service.client)
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
    renderReview(service.client)
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
    renderReview(service.client)

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
        onChanged={() => {}}
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
    const onChanged = vi.fn()
    const routes = reviewService({
      [`GET ${ADVERTISER}/files/leads/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/files/stage-history/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/mapping`]: () => Response.json(review(EMPTY, { problems: [] })),
      [`POST ${ADVERTISER}/mapping/confirmation`]: () => Response.json(confirmed),
    })
    renderReview(routes.client, onChanged)
    expect(routes.sentTo(`POST ${ADVERTISER}/mapping/confirmation`)).toHaveLength(0)

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm the mapping' }))

    const status = await screen.findByRole('status', { name: 'Mapping confirmed' })
    expect(status).toHaveTextContent('Confirmed')
    expect(status).toHaveTextContent('2026')
    expect(status).toHaveTextContent('can no longer be changed')
    expect(screen.getByLabelText('Typical deal size')).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Confirm the mapping' })).not.toBeInTheDocument()
    expect(onChanged).toHaveBeenCalledOnce()
  })

  it('offers training as the service says, once, above the mapping', async () => {
    renderReview(draftService().client)

    const training = await region('Train the model')
    expect(await training.findByRole('button', { name: 'Train the model' })).toBeDisabled()
    expect(screen.getAllByRole('region', { name: 'Train the model' })).toHaveLength(1)
  })

  it('asks again whether training can run once confirming has formatted the data', async () => {
    const confirmed = review(EMPTY, {
      problems: [],
      confirmed_at: '2026-09-20T16:30:00Z',
      formatted_at: '2026-09-20T16:30:00Z',
      formatting: FORMATTED,
    })
    let trainable = false
    const service = reviewService({
      [`GET ${ADVERTISER}/files/leads/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/files/stage-history/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/mapping`]: () => Response.json(review(EMPTY, { problems: [] })),
      [`POST ${ADVERTISER}/mapping/confirmation`]: () => {
        trainable = true
        return Response.json(confirmed)
      },
      [`GET ${ADVERTISER}/training`]: () =>
        Response.json(
          trainable ? { ...NOT_TRAINABLE, trainable, not_trainable_because: null } : NOT_TRAINABLE,
        ),
    })
    renderReview(service.client)
    const training = await region('Train the model')
    expect(await training.findByRole('button', { name: 'Train the model' })).toBeDisabled()

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm the mapping' }))

    await waitFor(() =>
      expect(training.getByRole('button', { name: 'Train the model' })).toBeEnabled(),
    )
  })

  it('shows the summary of what was formatted, exactly as the service returns it', async () => {
    const confirmed = review(EMPTY, {
      problems: [],
      confirmed_at: '2026-09-20T16:30:00Z',
      formatting: FORMATTED,
      personal_data: 'Names were removed; and the raw files deleted.',
    })
    const service = reviewService({
      [`GET ${ADVERTISER}/files/leads/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/files/stage-history/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/mapping`]: () => Response.json(review(EMPTY, { problems: [] })),
      [`POST ${ADVERTISER}/mapping/confirmation`]: () => Response.json(confirmed),
    })
    renderReview(service.client)

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm the mapping' }))

    const summary = await region('What was formatted')
    const counts = summary.getByRole('list', { name: 'Leads by outcome' })
    expect(
      within(counts)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual([
      '100Leads',
      '18Won',
      '58Lost',
      '24No outcome yet',
      '13Neglected leads',
      '2Phones without a country',
    ])
    const rows = summary.getByRole('table', { name: 'Rows that could not be read' })
    expect(
      within(rows)
        .getAllByRole('row')
        .slice(1)
        .map((row) => row.textContent),
    ).toEqual([
      'Leads fileThe submission time cannot be read.1101',
      'Stage-history fileThe lead is not in the leads file.122, 3, 4, 5, 6, 7, 8, 9, 10, 11…',
    ])
    expect(
      summary.getByText('Names were removed; and the raw files deleted.'),
    ).toBeInTheDocument()
  })

  it('names the ladder stages in the summary as the service names them', async () => {
    const named = CHOICES.stages_and_lost.map((choice) =>
      choice.value === 'won' ? { ...choice, name: 'Won (booked)' } : choice,
    )
    const confirmed = review(EMPTY, {
      confirmed_at: '2026-09-20T16:30:00Z',
      formatting: FORMATTED,
      stages_and_lost: named,
    })
    const service = reviewService({ [`GET ${ADVERTISER}/mapping`]: () => Response.json(confirmed) })
    renderReview(service.client, () => {}, FORMATTED_AND_DELETED)

    const counts = (await region('What was formatted')).getByRole('list', {
      name: 'Leads by outcome',
    })

    expect(within(counts).getByText('Won (booked)')).toBeInTheDocument()
  })

  it('once the raw files are deleted, lists the columns without asking for them', async () => {
    const confirmed = review(EMPTY, {
      problems: [],
      confirmed_at: '2026-09-20T16:30:00Z',
      formatting: FORMATTED,
    })
    const service = reviewService({ [`GET ${ADVERTISER}/mapping`]: () => Response.json(confirmed) })
    renderReview(service.client, () => {}, FORMATTED_AND_DELETED)

    const leads = await region(LEADS)

    expect(leads.getByRole('row', { name: /Trip Type/ })).toBeInTheDocument()
    expect(leads.getByText(/raw file was deleted/)).toBeInTheDocument()
    expect(service.sentTo(`GET ${ADVERTISER}/files/leads/columns`)).toHaveLength(0)
    expect(service.sentTo(`GET ${ADVERTISER}/files/stage-history/columns`)).toHaveLength(0)
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('says what confirming still has to do, never that the raw files are deleted', async () => {
    const stillToDo =
      'The data is formatted, but the raw files are not all deleted yet. Confirm again to delete them.'
    const interrupted = review(EMPTY, {
      confirmed_at: '2026-09-20T16:30:00Z',
      formatting: FORMATTED,
      personal_data: 'Names were removed.',
      still_to_do: stillToDo,
    })
    const done = { ...interrupted, still_to_do: null }
    const onChanged = vi.fn()
    const service = reviewService({
      [`GET ${ADVERTISER}/files/stage-history/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/mapping`]: () => Response.json(interrupted),
      [`POST ${ADVERTISER}/mapping/confirmation`]: () => Response.json(done),
    })
    const partly: Advertiser = {
      ...FORMATTED_AND_DELETED,
      stage_history_file: { ...BOTH_UPLOADED.stage_history_file!, raw_kept: true },
    }
    renderReview(service.client, onChanged, partly)

    const notFinished = await region('Confirming is not finished')
    expect(notFinished.getByText(stillToDo)).toBeInTheDocument()
    expect(screen.getByText('Names were removed.')).toBeInTheDocument()
    expect(screen.queryByText(/the raw files deleted/)).not.toBeInTheDocument()
    expect(service.sentTo(`GET ${ADVERTISER}/files/leads/columns`)).toHaveLength(0)
    expect(service.sentTo(`GET ${ADVERTISER}/files/stage-history/columns`)).toHaveLength(1)

    fireEvent.click(notFinished.getByRole('button', { name: 'Finish confirming' }))

    await waitFor(() =>
      expect(screen.queryByRole('region', { name: 'Confirming is not finished' })).toBeNull(),
    )
    expect(service.sentTo(`POST ${ADVERTISER}/mapping/confirmation`)).toHaveLength(1)
    expect(onChanged).toHaveBeenCalled()
  })

  it('after a refused confirmation, shows the mapping as the service now has it', async () => {
    let confirmedNow = false
    const service = reviewService({
      [`GET ${ADVERTISER}/files/leads/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/files/stage-history/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/mapping`]: () =>
        Response.json(
          confirmedNow
            ? review(EMPTY, {
                confirmed_at: '2026-09-20T16:30:00Z',
                formatting: FORMATTED,
                still_to_do: 'Confirm again to delete them.',
              })
            : review(EMPTY, { problems: [] }),
        ),
      [`POST ${ADVERTISER}/mapping/confirmation`]: () => {
        confirmedNow = true
        return Response.json({ detail: 'The raw files could not all be deleted yet.' }, { status: 503 })
      },
    })
    const onChanged = vi.fn()
    renderReview(service.client, onChanged)

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm the mapping' }))

    expect(await screen.findByRole('status', { name: 'Mapping confirmed' })).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The raw files could not all be deleted yet.',
    )
    expect(onChanged).toHaveBeenCalled()
  })

  it('saves the date order and time zone the person picks', async () => {
    const service = draftService()
    renderReview(service.client)

    choose(await screen.findByLabelText('Date order'), 'day_month_year')
    await waitFor(async () =>
      expect((await lastSaved(service)).date_order).toBe('day_month_year'),
    )
    fireEvent.change(screen.getByLabelText('Time zone'), { target: { value: 'Europe/London' } })

    await waitFor(async () => expect((await lastSaved(service)).time_zone).toBe('Europe/London'))
    expect(screen.getByRole('option', { name: 'Day-month-year (05/01/2024)' })).toBeInTheDocument()
  })

  it('shows why the service refused to confirm', async () => {
    const service = reviewService({
      [`GET ${ADVERTISER}/files/leads/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/files/stage-history/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/mapping`]: () => Response.json(review(EMPTY, { problems: [] })),
      [`POST ${ADVERTISER}/mapping/confirmation`]: () =>
        Response.json({ detail: 'The mapping is already confirmed.' }, { status: 409 }),
    })
    renderReview(service.client)

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm the mapping' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('The mapping is already confirmed.')
  })

  it('saves the typed deal size once typing pauses, not on every key', async () => {
    const service = draftService()
    renderReview(service.client)
    const size = await screen.findByLabelText('Typical deal size')

    for (const typed of ['1', '12', '125', '1250', '12500']) {
      fireEvent.change(size, { target: { value: typed } })
    }

    await waitFor(async () => expect((await lastSaved(service)).typical_deal_size).toBe(12500))
    expect(service.sentTo(`PUT ${ADVERTISER}/mapping`)).toHaveLength(1)
  })

  it('ends overlapping saves with the newest draft', async () => {
    let releaseFirst = () => {}
    const firstAnswered = new Promise<void>((resolve) => (releaseFirst = resolve))
    let saves = 0
    const service = reviewService({
      [`GET ${ADVERTISER}/files/leads/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/files/stage-history/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/mapping`]: () => Response.json(review(EMPTY)),
      [`PUT ${ADVERTISER}/mapping`]: async (request) => {
        const draft = (await request.json()) as Mapping
        saves += 1
        if (saves === 1) await firstAnswered
        return Response.json(review(draft, { problems: [`saved ${draft.leads.lead_id}`] }))
      },
    })
    renderReview(service.client)
    const leadId = (await region(LEADS)).getByLabelText('Lead identifier')

    choose(leadId, 'Lead ID')
    await waitFor(() => expect(saves).toBe(1))
    choose(leadId, 'Email')
    choose(leadId, 'Trip Type')
    releaseFirst()

    expect(await screen.findByText('saved Trip Type')).toBeInTheDocument()
    const sent = service.sentTo(`PUT ${ADVERTISER}/mapping`)
    expect(sent).toHaveLength(2)
    expect(((await sent[1].json()) as Mapping).leads.lead_id).toBe('Trip Type')
    expect(leadId).toHaveValue('Trip Type')
  })

  it('says the draft was not saved, instead of showing reasons that may be out of date', async () => {
    const service = reviewService({
      [`GET ${ADVERTISER}/files/leads/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/files/stage-history/columns`]: () => Response.json([]),
      [`GET ${ADVERTISER}/mapping`]: () => Response.json(review(EMPTY)),
      [`PUT ${ADVERTISER}/mapping`]: () =>
        Response.json({ detail: 'The stage-history file is not uploaded.' }, { status: 404 }),
    })
    renderReview(service.client)
    await screen.findByRole('list', { name: 'Before you can confirm' })

    choose((await region(LEADS)).getByLabelText('Lead identifier'), 'Lead ID')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The draft was not saved: The stage-history file is not uploaded.',
    )
    expect(screen.queryByRole('list', { name: 'Before you can confirm' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm the mapping' })).toBeDisabled()
  })
})
