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
  columns: [
    { name: 'Lead ID', examples: ['L-1001', 'L-1002', 'L-1003'] },
    { name: 'Trip Type', examples: ['Safari', 'Family holiday'] },
  ],
}
const STAGE_HISTORY_FILE: FileProfile = {
  kind: 'stage-history',
  file_name: 'stage_history.csv',
  uploaded_at: '2026-09-15T08:46:00Z',
  row_count: 418,
  columns: [
    { name: 'Lead ID', examples: ['L-1001'] },
    { name: 'Stage', examples: ['New enquiry', 'Call attempted'] },
  ],
}

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
    })
    render(<AdvertiserPage client={service.client} />)
    await nameTheAdvertiser()

    fireEvent.click(screen.getByRole('button', { name: /Review/ }))

    const leads = await screen.findByRole('region', { name: 'Leads file: leads.csv' })
    expect(within(leads).getByText('101 rows')).toBeInTheDocument()
    const tripType = within(leads).getByRole('row', { name: /Trip Type/ })
    expect(tripType).toHaveTextContent('Safari')
    expect(tripType).toHaveTextContent('Family holiday')
    const history = screen.getByRole('region', { name: 'Stage-history file: stage_history.csv' })
    expect(within(history).getByText('418 rows')).toBeInTheDocument()
  })

  it('lists every CRM stage name in the column the person picks, with its row count', async () => {
    const service = fakeService({
      'POST /advertisers': () => Response.json(BOTH_UPLOADED, { status: 201 }),
      [`GET ${ADVERTISER}/files/stage-history/crm-stages`]: (request) =>
        new URL(request.url).searchParams.get('column') === 'Stage'
          ? Response.json([
              { name: 'New enquiry', row_count: 98 },
              { name: 'Closed won', row_count: 19 },
            ])
          : Response.json({ detail: 'No such column' }, { status: 400 }),
    })
    render(<AdvertiserPage client={service.client} />)
    await nameTheAdvertiser()
    fireEvent.click(screen.getByRole('button', { name: /Review/ }))

    fireEvent.change(await screen.findByLabelText('Column holding the CRM stage'), {
      target: { value: 'Stage' },
    })

    const stages = await screen.findByRole('table', { name: 'CRM stages' })
    expect(within(stages).getByRole('row', { name: 'New enquiry 98' })).toBeInTheDocument()
    expect(within(stages).getByRole('row', { name: 'Closed won 19' })).toBeInTheDocument()
  })
})
