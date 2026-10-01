import type { ApiClient, components } from '@emva/api-client'
import { type ReactNode, useEffect, useId, useRef, useState } from 'react'

import { refusal, UNREACHABLE } from './service-errors.ts'
import { Training } from './Training.tsx'
import { FILES } from './uploaded-files.ts'

type Advertiser = components['schemas']['Advertiser']
type Summary = components['schemas']['Summary']
type StageOrLostChoice = components['schemas']['StageOrLostChoice']
type DateOrder = components['schemas']['DateOrder']
type DateOrderChoice = components['schemas']['DateOrderChoice']
type Column = components['schemas']['Column']
type ColumnKind = components['schemas']['ColumnKind']
type FileKind = components['schemas']['FileKind']
type FileProfile = components['schemas']['FileProfile']
type Mapping = components['schemas']['Mapping']
type MappingReview = components['schemas']['MappingReview']
type LeadsColumns = components['schemas']['LeadsColumns']
type InputKindChoice = components['schemas']['InputKindChoice']
type StageOrLost = components['schemas']['StageOrLost']

// How long typing pauses before the draft is saved.
const TYPING_PAUSE_MS = 400

type Loaded =
  | { state: 'loading' }
  | { state: 'failed'; problem: string }
  | { state: 'loaded'; review: MappingReview; mapping: Mapping }

type Saving = { state: 'saved' } | { state: 'saving' } | { state: 'failed'; problem: string }

export function ReviewStep({
  client,
  advertiser,
  onChanged,
}: {
  client: ApiClient
  advertiser: Advertiser
  // Called after confirming, which changes the advertiser (its files, once deleted).
  onChanged: () => void
}) {
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' })
  const [saving, setSaving] = useState<Saving>({ state: 'saved' })
  const [confirming, setConfirming] = useState(false)
  const [confirmProblem, setConfirmProblem] = useState<string | null>(null)
  const sending = useRef(false)
  const queued = useRef<Mapping | null>(null)
  const typing = useRef<{ timer: ReturnType<typeof setTimeout>; flush: () => void } | null>(null)
  const path = { params: { path: { advertiser_id: advertiser.id } } }

  // A draft still waiting for typing to pause is saved when the person leaves the screen.
  useEffect(
    () => () => {
      if (!typing.current) return
      clearTimeout(typing.current.timer)
      typing.current.flush()
    },
    [],
  )

  useEffect(() => {
    client
      .GET('/advertisers/{advertiser_id}/mapping', {
        params: { path: { advertiser_id: advertiser.id } },
      })
      .then(({ data, error, response }) =>
        setLoaded(
          data
            ? { state: 'loaded', review: data, mapping: data.mapping }
            : { state: 'failed', problem: refusal(error, response) },
        ),
      )
      .catch(() => setLoaded({ state: 'failed', problem: UNREACHABLE }))
  }, [client, advertiser.id])

  // Drafts are sent one at a time, newest last, so the service always keeps the latest.
  async function save(draft: Mapping) {
    queued.current = draft
    if (sending.current) return
    sending.current = true
    setSaving({ state: 'saving' })
    let outcome: Saving = { state: 'saved' }
    while (queued.current) {
      const body = queued.current
      queued.current = null
      try {
        const { data, error, response } = await client.PUT('/advertisers/{advertiser_id}/mapping', {
          ...path,
          body,
        })
        if (data) {
          outcome = { state: 'saved' }
          const latest = queued.current === null
          if (latest) setLoaded((now) => (now.state === 'loaded' ? { ...now, review: data } : now))
        } else {
          outcome = { state: 'failed', problem: refusal(error, response) }
        }
      } catch {
        outcome = { state: 'failed', problem: UNREACHABLE }
      }
    }
    sending.current = false
    setSaving(outcome)
  }

  function change(draft: Mapping, { typed = false } = {}) {
    setLoaded((now) => (now.state === 'loaded' ? { ...now, mapping: draft } : now))
    if (typing.current) clearTimeout(typing.current.timer)
    typing.current = null
    if (!typed) return void save(draft)
    setSaving({ state: 'saving' })
    const flush = () => {
      typing.current = null
      void save(draft)
    }
    typing.current = { flush, timer: setTimeout(flush, TYPING_PAUSE_MS) }
  }

  // Confirming may stop part-way (formatted, but a raw file not yet deleted), so whatever it
  // answers, the mapping and the advertiser are read again as the service now has them.
  async function confirm() {
    setConfirming(true)
    setConfirmProblem(null)
    try {
      const { data, error, response } = await client.POST(
        '/advertisers/{advertiser_id}/mapping/confirmation',
        path,
      )
      if (data) setLoaded({ state: 'loaded', review: data, mapping: data.mapping })
      else {
        setConfirmProblem(refusal(error, response))
        const now = await client.GET('/advertisers/{advertiser_id}/mapping', path)
        if (now.data) setLoaded({ state: 'loaded', review: now.data, mapping: now.data.mapping })
      }
    } catch {
      setConfirmProblem(UNREACHABLE)
    } finally {
      setConfirming(false)
      onChanged()
    }
  }

  if (loaded.state === 'loading') return <p className="muted">Reading the mapping…</p>
  if (loaded.state === 'failed')
    return (
      <p className="problem" role="alert">
        {loaded.problem}
      </p>
    )

  const { review, mapping } = loaded
  const confirmed = review.confirmed_at !== null
  // Training waits for both, as the service does.
  const formatted = confirmed && review.formatting !== null
  const leads = mapping.leads
  const history = mapping.stage_history
  const inputs = leads.inputs ?? {}
  const placed = mapping.crm_stages ?? {}

  function setLeads(next: Partial<LeadsColumns>) {
    change({ ...mapping, leads: { ...leads, ...next } })
  }

  function setInput(column: string, kind: ColumnKind | '') {
    const { [column]: _dropped, ...others } = inputs
    setLeads({ inputs: kind ? { ...others, [column]: kind } : others })
  }

  function place(name: string, where: StageOrLost | '') {
    const { [name]: _dropped, ...others } = placed
    change({ ...mapping, crm_stages: where ? { ...others, [name]: where } : others })
  }

  return (
    <div className="review">
      {confirmed && <Confirmed at={review.confirmed_at!} />}
      {review.still_to_do && (
        <StillToDo
          what={review.still_to_do}
          confirming={confirming}
          problem={confirmProblem}
          finish={confirm}
        />
      )}
      {review.formatting && (
        <Formatted
          summary={review.formatting}
          stages={review.stages_and_lost}
          rawFilesDeleted={review.still_to_do === null}
        />
      )}
      {formatted && <Training client={client} advertiserId={advertiser.id} ready />}
      <fieldset className="mapping" disabled={confirmed}>
        <legend className="visually-hidden">Mapping</legend>
        {advertiser.leads_file && (
          <FileColumns
            client={client}
            advertiserId={advertiser.id}
            rawDeleted={!advertiser.leads_file.raw_kept}
            kind="leads"
            label="Leads file"
            file={advertiser.leads_file}
            roles={
              <RoleChoices
                legend="What the leads file's columns hold"
                hint="Every column not marked here, and not an input to the score, is dropped."
                columns={advertiser.leads_file.column_names}
                roles={review.leads_roles.map(({ role, label }) => ({
                  label,
                  value: leads[role] ?? null,
                  choose: (column) => setLeads({ [role]: column }),
                }))}
              />
            }
            columnControl={{
              heading: 'Input to the score',
              control: (column) => (
                <InputKind
                  kinds={review.input_kinds}
                  column={column}
                  kind={inputs[column] ?? ''}
                  choose={(kind) => setInput(column, kind)}
                />
              ),
            }}
          />
        )}
        {advertiser.stage_history_file && (
          <FileColumns
            client={client}
            advertiserId={advertiser.id}
            rawDeleted={!advertiser.stage_history_file.raw_kept}
            kind="stage-history"
            label="Stage-history file"
            file={advertiser.stage_history_file}
            roles={
              <RoleChoices
                legend="What the stage-history file's columns hold"
                columns={advertiser.stage_history_file.column_names}
                roles={review.stage_history_roles.map(({ role, label }) => ({
                  label,
                  value: history[role] ?? null,
                  choose: (column) =>
                    change({ ...mapping, stage_history: { ...history, [role]: column } }),
                }))}
              />
            }
          >
            <CrmStages review={review} placed={placed} place={place} />
          </FileColumns>
        )}
        <HowTimesAreWritten
          orders={review.date_orders}
          order={mapping.date_order ?? null}
          zone={mapping.time_zone ?? 'UTC'}
          chooseOrder={(order) => change({ ...mapping, date_order: order })}
          chooseZone={(zone) => change({ ...mapping, time_zone: zone }, { typed: true })}
        />
        <TypicalDealSize
          size={mapping.typical_deal_size ?? null}
          choose={(size) => change({ ...mapping, typical_deal_size: size }, { typed: true })}
        />
      </fieldset>
      {!confirmed && (
        <Confirmation
          problems={review.problems}
          saving={saving}
          confirming={confirming}
          problem={confirmProblem}
          confirm={confirm}
        />
      )}
      {!formatted && <Training client={client} advertiserId={advertiser.id} ready={false} />}
    </div>
  )
}

function Confirmed({ at }: { at: string }) {
  const headingId = useId()
  return (
    <section className="confirmed" role="status" aria-labelledby={headingId}>
      <h3 id={headingId}>Mapping confirmed</h3>
      <p>
        Confirmed <time dateTime={at}>{formatTime(at)}</time>. The mapping can no longer be changed.
      </p>
    </section>
  )
}

function StillToDo({
  what,
  confirming,
  problem,
  finish,
}: {
  what: string
  confirming: boolean
  problem: string | null
  finish: () => void
}) {
  const headingId = useId()
  return (
    <section className="still-to-do" aria-labelledby={headingId}>
      <h3 id={headingId}>Confirming is not finished</h3>
      <p>{what}</p>
      <button type="button" className="primary" disabled={confirming} onClick={finish}>
        {confirming ? 'Finishing…' : 'Finish confirming'}
      </button>
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
    </section>
  )
}

function Formatted({
  summary,
  stages,
  rawFilesDeleted,
}: {
  summary: Summary
  stages: StageOrLostChoice[]
  rawFilesDeleted: boolean
}) {
  const headingId = useId()
  const countsId = useId()
  const nameOf = (value: StageOrLostChoice['value']) =>
    stages.find((stage) => stage.value === value)?.name ?? value
  const counts = [
    { label: 'Leads', count: summary.lead_count },
    { label: nameOf('won'), count: summary.won },
    { label: nameOf('lost'), count: summary.lost },
    { label: 'No outcome yet', count: summary.no_outcome_yet },
    { label: 'Neglected leads', count: summary.neglected },
    { label: 'Phones without a country', count: summary.phones_without_country },
  ]
  return (
    <section className="formatted" aria-labelledby={headingId}>
      <h3 id={headingId}>What was formatted</h3>
      <p className="muted">
        Names were removed; identifiers, emails and phones scrambled; every unmarked column
        dropped{rawFilesDeleted ? '; and the raw files deleted.' : '.'}
      </p>
      <p id={countsId} className="visually-hidden">
        Leads by outcome
      </p>
      <ul className="outcome-counts" aria-labelledby={countsId}>
        {counts.map(({ label, count }) => (
          <li key={label}>
            <span className="count data">{count}</span>
            <span className="count-label">{label}</span>
          </li>
        ))}
      </ul>
      {summary.unreadable.length === 0 ? (
        <p>Every row could be read.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <caption>Rows that could not be read</caption>
            <thead>
              <tr>
                <th scope="col">File</th>
                <th scope="col">Why</th>
                <th scope="col" className="number">
                  Rows
                </th>
                <th scope="col">First rows</th>
              </tr>
            </thead>
            <tbody>
              {summary.unreadable.map((rows) => (
                <tr key={`${rows.file} ${rows.reason}`}>
                  <td>{FILE_LABELS[rows.file]}</td>
                  <td>{rows.reason}</td>
                  <td className="number data">{rows.count}</td>
                  <td className="data">
                    {rows.first_rows.join(', ')}
                    {rows.count > rows.first_rows.length && '…'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

const FILE_LABELS = Object.fromEntries(FILES.map(({ kind, label }) => [kind, label])) as Record<
  FileKind,
  string
>

function RoleChoices({
  legend,
  hint,
  columns,
  roles,
}: {
  legend: string
  hint?: string
  columns: string[]
  roles: { label: string; value: string | null; choose: (column: string | null) => void }[]
}) {
  return (
    <fieldset className="roles">
      <legend>{legend}</legend>
      {hint && <p className="muted">{hint}</p>}
      <div className="role-grid">
        {roles.map((role) => (
          <ColumnChoice key={role.label} columns={columns} {...role} />
        ))}
      </div>
    </fieldset>
  )
}

function ColumnChoice({
  label,
  columns,
  value,
  choose,
}: {
  label: string
  columns: string[]
  value: string | null
  choose: (column: string | null) => void
}) {
  const id = useId()
  // A column the draft names that the file no longer has stays visible until it is changed.
  const offered = value === null || columns.includes(value) ? columns : [...columns, value]
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value ?? ''} onChange={(event) => choose(event.target.value || null)}>
        <option value="">Not marked</option>
        {offered.map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
    </div>
  )
}

function InputKind({
  kinds,
  column,
  kind,
  choose,
}: {
  kinds: InputKindChoice[]
  column: string
  kind: ColumnKind | ''
  choose: (kind: ColumnKind | '') => void
}) {
  return (
    <select
      aria-label={`“${column}” as an input`}
      value={kind}
      onChange={(event) => choose(event.target.value as ColumnKind | '')}
    >
      <option value="">Not an input</option>
      {kinds.map(({ kind: value, label }) => (
        <option key={value} value={value}>
          {label}
        </option>
      ))}
    </select>
  )
}

type Columns =
  | { state: 'loading' }
  | { state: 'listed'; columns: Column[] }
  | { state: 'failed'; problem: string }

function FileColumns({
  client,
  advertiserId,
  rawDeleted,
  kind,
  label,
  file,
  roles,
  columnControl,
  children,
}: {
  client: ApiClient
  advertiserId: string
  // Once the mapping is confirmed the raw file is formatted and deleted, so only its column
  // names remain; its example values are not asked for.
  rawDeleted: boolean
  kind: FileKind
  label: string
  file: FileProfile
  roles: ReactNode
  columnControl?: { heading: string; control: (column: string) => ReactNode }
  children?: ReactNode
}) {
  const [fetched, setColumns] = useState<Columns>({ state: 'loading' })
  const columns: Columns = rawDeleted
    ? { state: 'listed', columns: file.column_names.map((name) => ({ name, examples: [] })) }
    : fetched

  useEffect(() => {
    if (rawDeleted) return
    client
      .GET('/advertisers/{advertiser_id}/files/{kind}/columns', {
        params: { path: { advertiser_id: advertiserId, kind } },
      })
      .then(({ data, error, response }) =>
        setColumns(
          data
            ? { state: 'listed', columns: data }
            : { state: 'failed', problem: refusal(error, response) },
        ),
      )
      .catch(() => setColumns({ state: 'failed', problem: UNREACHABLE }))
  }, [client, advertiserId, kind, rawDeleted])

  return (
    <section className="file-review" aria-label={`${label}: ${file.file_name}`}>
      <header className="file-review-head">
        <h3>{label}</h3>
        <p className="data">{file.file_name}</p>
        <p className="data">{file.row_count} rows</p>
        <p className="data">{file.column_names.length} columns</p>
      </header>
      {roles}
      {columns.state === 'loading' && <p className="muted">Reading the columns…</p>}
      {columns.state === 'failed' && (
        <p className="problem" role="alert">
          {columns.problem}
        </p>
      )}
      {rawDeleted && (
        <p className="muted">
          The raw file was deleted once it was formatted, so its example values are gone.
        </p>
      )}
      {columns.state === 'listed' && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Column</th>
                {!rawDeleted && <th scope="col">Example values</th>}
                {columnControl && <th scope="col">{columnControl.heading}</th>}
              </tr>
            </thead>
            <tbody>
              {columns.columns.map((column) => (
                <tr key={column.name}>
                  <th scope="row">{column.name}</th>
                  {!rawDeleted && (
                    <td>
                      {column.examples.length === 0 ? (
                        <span className="muted">No values</span>
                      ) : (
                        <ul className="examples">
                          {column.examples.map((example) => (
                            <li key={example} className="data">
                              {example}
                            </li>
                          ))}
                        </ul>
                      )}
                    </td>
                  )}
                  {columnControl && <td>{columnControl.control(column.name)}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {children}
    </section>
  )
}

function CrmStages({
  review,
  placed,
  place,
}: {
  review: MappingReview
  placed: Record<string, StageOrLost>
  place: (name: string, where: StageOrLost | '') => void
}) {
  return (
    <div className="crm-stages">
      <h4>CRM stages on the Canonical ladder</h4>
      {review.crm_stages.length === 0 ? (
        <p className="muted">
          Mark the column holding the CRM stage to see every name the CRM uses.
        </p>
      ) : (
        <>
          <p className="muted">
            Place each CRM stage on a stage of the ladder, or on Lost. Several may share a stage.
          </p>
          <div className="table-scroll">
            <table aria-label="CRM stages">
              <thead>
                <tr>
                  <th scope="col">CRM stage</th>
                  <th scope="col" className="number">
                    Rows
                  </th>
                  <th scope="col">On the ladder</th>
                </tr>
              </thead>
              <tbody>
                {review.crm_stages.map((stage) => (
                  <tr key={stage.name}>
                    <th scope="row">{stage.name}</th>
                    <td className="number data">{stage.row_count}</td>
                    <td>
                      <select
                        aria-label={`“${stage.name}” on the ladder`}
                        value={placed[stage.name] ?? ''}
                        onChange={(event) =>
                          place(stage.name, event.target.value as StageOrLost | '')
                        }
                      >
                        <option value="">Not placed</option>
                        {review.stages_and_lost.map(({ value, name }) => (
                          <option key={value} value={value}>
                            {name}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

function HowTimesAreWritten({
  orders,
  order,
  zone,
  chooseOrder,
  chooseZone,
}: {
  orders: DateOrderChoice[]
  order: DateOrder | null
  zone: string
  chooseOrder: (order: DateOrder | null) => void
  chooseZone: (zone: string) => void
}) {
  const orderId = useId()
  const zoneId = useId()
  const zoneHintId = useId()
  const [zoneText, setZoneText] = useState(zone)
  return (
    <fieldset className="roles times">
      <legend>How both files write times</legend>
      <div className="role-grid">
        <div className="field">
          <label htmlFor={orderId}>Date order</label>
          <select
            id={orderId}
            value={order ?? ''}
            onChange={(event) => chooseOrder((event.target.value || null) as DateOrder | null)}
          >
            <option value="">Not picked</option>
            {orders.map(({ value, label }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor={zoneId}>Time zone</label>
          <input
            id={zoneId}
            type="text"
            autoComplete="off"
            spellCheck={false}
            aria-describedby={zoneHintId}
            value={zoneText}
            onChange={(event) => {
              setZoneText(event.target.value)
              chooseZone(event.target.value)
            }}
          />
          <p id={zoneHintId} className="muted">
            Times written without a zone are read in it, such as Europe/London or UTC.
          </p>
        </div>
      </div>
    </fieldset>
  )
}

function TypicalDealSize({
  size,
  choose,
}: {
  size: number | null
  choose: (size: number | null) => void
}) {
  const id = useId()
  const hintId = useId()
  const [text, setText] = useState(size === null ? '' : String(size))
  return (
    <section className="deal-size">
      <div className="field">
        <label htmlFor={id}>Typical deal size</label>
        <p id={hintId} className="muted">
          The size of deal this advertiser usually makes. It sizes every lead that states none.
        </p>
        <input
          id={id}
          type="number"
          inputMode="decimal"
          aria-describedby={hintId}
          value={text}
          onChange={(event) => {
            setText(event.target.value)
            choose(event.target.value === '' ? null : Number(event.target.value))
          }}
        />
      </div>
    </section>
  )
}

function Confirmation({
  problems,
  saving,
  confirming,
  problem,
  confirm,
}: {
  problems: string[]
  saving: Saving
  confirming: boolean
  problem: string | null
  confirm: () => void
}) {
  const listId = useId()
  return (
    <section className="confirmation" aria-label="Confirm the mapping">
      <p className="save-state muted" aria-live="polite">
        {saving.state === 'saving' && 'Saving the draft…'}
        {saving.state === 'saved' && 'Draft saved.'}
      </p>
      {saving.state === 'failed' ? (
        <p className="problem" role="alert">
          The draft was not saved: {saving.problem} Change any field to try again.
        </p>
      ) : problems.length > 0 ? (
        <div className="to-do" aria-live="polite">
          <h3 id={listId}>Before you can confirm</h3>
          <ul aria-labelledby={listId}>
            {problems.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p>
          Every column and CRM stage is mapped. Once confirmed, the mapping can no longer be
          changed.
        </p>
      )}
      <button
        type="button"
        className="primary"
        disabled={problems.length > 0 || saving.state !== 'saved' || confirming}
        onClick={confirm}
      >
        {confirming ? 'Confirming…' : 'Confirm the mapping'}
      </button>
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
    </section>
  )
}

function formatTime(iso: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(iso),
  )
}
