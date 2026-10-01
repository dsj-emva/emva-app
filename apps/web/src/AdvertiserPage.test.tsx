import type { components } from '@emva/api-client'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AdvertiserPage } from './AdvertiserPage.tsx'
import { fakeService } from './test-service.ts'

type Advertiser = components['schemas']['Advertiser']
type FileProfile = components['schemas']['FileProfile']

const ID = '7a1d2c3e-0000-4000-8000-000000000001'
const ADVERTISER = `/advertisers/${ID}`

const LEADS_FILE: FileProfile = {
  kind: 'leads',
  file_name: 'leads.csv',
  uploaded_at: '2026-09-15T08:45:00Z',
  row_count: 101,
  column_names: ['Lead ID', 'Trip Type'],
}
const STAGE_HISTORY_FILE: FileProfile = {
  kind: 'stage-history',
  file_name: 'stage_history.csv',
  uploaded_at: '2026-09-15T08:46:00Z',
  row_count: 418,
  column_names: ['Lead ID', 'Stage'],
}
const LEADS_COLUMNS = [
  { name: 'Lead ID', examples: ['L-1001', 'L-1002', 'L-1003'] },
  { name: 'Trip Type', examples: ['Safari', 'Family holiday'] },
]
const STAGE_HISTORY_COLUMNS = [
  { name: 'Lead ID', examples: ['L-1001'] },
  { name: 'Stage', examples: ['New enquiry', 'Call attempted'] },
]

function advertiser(files: Partial<Advertiser> = {}): Advertiser {
  return {
    id: ID,
    name: 'Savanna Journeys',
    data_source: 'hand_made_test',
    leads_file: null,
    stage_history_file: null,
    review_available: false,
    ...files,
  }
}

const BOTH_UPLOADED = advertiser({
  leads_file: LEADS_FILE,
  stage_history_file: STAGE_HISTORY_FILE,
  review_available: true,
})

function csv(name: string) {
  return new File(['Lead ID\nL-1001\n'], name, { type: 'text/csv' })
}

async function nameTheAdvertiser() {
  fireEvent.change(screen.getByLabelText('Advertiser name'), {
    target: { value: 'Savanna Journeys' },
  })
  fireEvent.click(screen.getByLabelText('Hand-made test data'))
  expect(screen.getByRole('group', { name: 'Data source' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Start' }))
  await screen.findByRole('heading', { name: 'Savanna Journeys' })
}

function chooseFile(label: string, file: File) {
  fireEvent.change(screen.getByLabelText(label), { target: { files: [file] } })
}

describe('AdvertiserPage', () => {
  it('creates the advertiser with its name and data source', async () => {
    const service = fakeService({
      'POST /advertisers': () => Response.json(advertiser(), { status: 201 }),
    })
    render(<AdvertiserPage client={service.client} />)

    await nameTheAdvertiser()

    expect(await service.sentTo('POST /advertisers')[0].json()).toEqual({
      name: 'Savanna Journeys',
      data_source: 'hand_made_test',
    })
    expect(screen.getByText('Hand-made test data')).toBeInTheDocument()
  })

  it('uploads a chosen file as it is and shows its name and row count', async () => {
    const service = fakeService({
      'POST /advertisers': () => Response.json(advertiser(), { status: 201 }),
      [`PUT ${ADVERTISER}/files/leads`]: () => Response.json(LEADS_FILE),
      [`GET ${ADVERTISER}`]: () => Response.json(advertiser({ leads_file: LEADS_FILE })),
    })
    render(<AdvertiserPage client={service.client} />)
    await nameTheAdvertiser()

    chooseFile('Choose the leads file', csv('leads.csv'))

    const panel = await screen.findByRole('region', { name: 'Leads file' })
    expect(await within(panel).findByText('leads.csv')).toBeInTheDocument()
    expect(within(panel).getByText('101 rows')).toBeInTheDocument()
    const [upload] = service.sentTo(`PUT ${ADVERTISER}/files/leads`)
    expect(new URL(upload.url).searchParams.get('file_name')).toBe('leads.csv')
    expect(upload.headers.get('Content-Type')).toBe('text/csv')
    expect(await upload.text()).toBe('Lead ID\nL-1001\n')
  })

  it('shows why the service refused a file', async () => {
    const service = fakeService({
      'POST /advertisers': () => Response.json(advertiser(), { status: 201 }),
      [`PUT ${ADVERTISER}/files/stage-history`]: () =>
        Response.json({ detail: 'The file is empty.' }, { status: 400 }),
    })
    render(<AdvertiserPage client={service.client} />)
    await nameTheAdvertiser()

    chooseFile('Choose the stage-history file', csv('empty.csv'))

    const panel = screen.getByRole('region', { name: 'Stage-history file' })
    expect(await within(panel).findByRole('alert')).toHaveTextContent('The file is empty.')
  })

  it('keeps the review closed until the service says both files are uploaded', async () => {
    const service = fakeService({
      'POST /advertisers': () => Response.json(advertiser(), { status: 201 }),
      [`PUT ${ADVERTISER}/files/leads`]: () => Response.json(LEADS_FILE),
      [`PUT ${ADVERTISER}/files/stage-history`]: () => Response.json(STAGE_HISTORY_FILE),
      [`GET ${ADVERTISER}`]: () => Response.json(advertiser({ leads_file: LEADS_FILE })),
    })
    render(<AdvertiserPage client={service.client} />)
    await nameTheAdvertiser()
    expect(screen.getByRole('button', { name: /Review/ })).toBeDisabled()

    chooseFile('Choose the leads file', csv('leads.csv'))
    await screen.findByText('101 rows')
    expect(screen.getByRole('button', { name: /Review/ })).toBeDisabled()
  })

  it('opens the review once both files are uploaded', async () => {
    const service = fakeService({
      'POST /advertisers': () => Response.json(advertiser({ leads_file: LEADS_FILE }), { status: 201 }),
      [`PUT ${ADVERTISER}/files/stage-history`]: () => Response.json(STAGE_HISTORY_FILE),
      [`GET ${ADVERTISER}`]: () => Response.json(BOTH_UPLOADED),
    })
    render(<AdvertiserPage client={service.client} />)
    await nameTheAdvertiser()

    chooseFile('Choose the stage-history file', csv('stage_history.csv'))

    expect(await screen.findByRole('button', { name: /Review/ })).toBeEnabled()
  })

  it("reviews each file's row count and columns with example values", async () => {
    const service = fakeService({
      'POST /advertisers': () => Response.json(BOTH_UPLOADED, { status: 201 }),
      [`GET ${ADVERTISER}/files/leads/columns`]: () => Response.json(LEADS_COLUMNS),
      [`GET ${ADVERTISER}/files/stage-history/columns`]: () => Response.json(STAGE_HISTORY_COLUMNS),
      [`GET ${ADVERTISER}/mapping`]: () =>
        Response.json({
          mapping: { leads: {}, stage_history: {} },
          confirmed_at: null,
          problems: [],
          crm_stages: [],
          places: [],
        }),
    })
    render(<AdvertiserPage client={service.client} />)
    await nameTheAdvertiser()

    fireEvent.click(screen.getByRole('button', { name: /Review/ }))

    const leads = await screen.findByRole('region', { name: 'Leads file: leads.csv' })
    expect(within(leads).getByText('101 rows')).toBeInTheDocument()
    const tripType = await within(leads).findByRole('row', { name: /Trip Type/ })
    expect(tripType).toHaveTextContent('Safari')
    expect(tripType).toHaveTextContent('Family holiday')
    const history = screen.getByRole('region', { name: 'Stage-history file: stage_history.csv' })
    expect(within(history).getByText('418 rows')).toBeInTheDocument()
  })

  it('replaces an uploaded file with the one the person picks next', async () => {
    const replaced = { ...LEADS_FILE, file_name: 'right-export.csv', row_count: 99 }
    const service = fakeService({
      'POST /advertisers': () => Response.json(advertiser({ leads_file: LEADS_FILE }), { status: 201 }),
      [`PUT ${ADVERTISER}/files/leads`]: () => Response.json(replaced),
      [`GET ${ADVERTISER}`]: () => Response.json(advertiser({ leads_file: replaced })),
    })
    render(<AdvertiserPage client={service.client} />)
    await nameTheAdvertiser()

    chooseFile('Replace the leads file', csv('right-export.csv'))

    const panel = screen.getByRole('region', { name: 'Leads file' })
    expect(await within(panel).findByText('right-export.csv')).toBeInTheDocument()
    expect(within(panel).getByText('99 rows')).toBeInTheDocument()
  })

  it('keeps the draft mapping when the person leaves the review and comes back', async () => {
    let kept: unknown = null
    const draft = (mapping: unknown) => ({
      mapping: mapping ?? {
        leads: { inputs: {} },
        stage_history: {},
        crm_stages: {},
        typical_deal_size: null,
      },
      confirmed_at: null,
      problems: ['Enter the typical deal size.'],
      crm_stages: [],
      places: [],
    })
    const service = fakeService({
      'POST /advertisers': () => Response.json(BOTH_UPLOADED, { status: 201 }),
      [`GET ${ADVERTISER}/files/leads/columns`]: () => Response.json(LEADS_COLUMNS),
      [`GET ${ADVERTISER}/files/stage-history/columns`]: () => Response.json(STAGE_HISTORY_COLUMNS),
      [`GET ${ADVERTISER}/mapping`]: () => Response.json(draft(kept)),
      [`PUT ${ADVERTISER}/mapping`]: async (request) => {
        kept = await request.json()
        return Response.json(draft(kept))
      },
    })
    render(<AdvertiserPage client={service.client} />)
    await nameTheAdvertiser()
    fireEvent.click(screen.getByRole('button', { name: /Review/ }))
    fireEvent.change(await screen.findByLabelText('Typical deal size'), {
      target: { value: '12000' },
    })
    await screen.findByText('Draft saved.')

    fireEvent.click(screen.getByRole('button', { name: /Upload/ }))
    fireEvent.click(screen.getByRole('button', { name: /Review/ }))

    expect(await screen.findByLabelText('Typical deal size')).toHaveValue(12000)
  })
})
