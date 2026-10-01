import type { ApiClient, components } from '@emva/api-client'
import { type ReactNode, useEffect, useId, useState } from 'react'

import { refusal, UNREACHABLE } from './service-errors.ts'
import { FILES, fileOf } from './uploaded-files.ts'

type Advertiser = components['schemas']['Advertiser']
type Column = components['schemas']['Column']
type CrmStage = components['schemas']['CrmStage']
type FileKind = components['schemas']['FileKind']
type FileProfile = components['schemas']['FileProfile']

export function ReviewStep({ client, advertiser }: { client: ApiClient; advertiser: Advertiser }) {
  return (
    <div className="review">
      {FILES.map(({ kind, label }) => {
        const file = fileOf(advertiser, kind)
        return (
          file && (
            <FileColumns
              key={`${kind} ${file.uploaded_at}`}
              client={client}
              advertiserId={advertiser.id}
              kind={kind}
              label={label}
              file={file}
            >
              {kind === 'stage-history' && (
                <CrmStages client={client} advertiserId={advertiser.id} file={file} />
              )}
            </FileColumns>
          )
        )
      })}
    </div>
  )
}

type Columns =
  | { state: 'loading' }
  | { state: 'listed'; columns: Column[] }
  | { state: 'failed'; problem: string }

function FileColumns({
  client,
  advertiserId,
  kind,
  label,
  file,
  children,
}: {
  client: ApiClient
  advertiserId: string
  kind: FileKind
  label: string
  file: FileProfile
  children?: ReactNode
}) {
  const [columns, setColumns] = useState<Columns>({ state: 'loading' })

  useEffect(() => {
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
  }, [client, advertiserId, kind])

  return (
    <section className="file-review" aria-label={`${label}: ${file.file_name}`}>
      <header className="file-review-head">
        <h3>{label}</h3>
        <p className="data">{file.file_name}</p>
        <p className="data">{file.row_count} rows</p>
        <p className="data">{file.column_names.length} columns</p>
      </header>
      {columns.state === 'loading' && <p className="muted">Reading the columns…</p>}
      {columns.state === 'failed' && (
        <p className="problem" role="alert">
          {columns.problem}
        </p>
      )}
      {columns.state === 'listed' && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Column</th>
                <th scope="col">Example values</th>
              </tr>
            </thead>
            <tbody>
              {columns.columns.map((column) => (
                <tr key={column.name}>
                  <th scope="row">{column.name}</th>
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

type Stages =
  | { state: 'unchosen' }
  | { state: 'loading' }
  | { state: 'listed'; stages: CrmStage[] }
  | { state: 'failed'; problem: string }

function CrmStages({
  client,
  advertiserId,
  file,
}: {
  client: ApiClient
  advertiserId: string
  file: FileProfile
}) {
  const selectId = useId()
  const [column, setColumn] = useState('')
  const [stages, setStages] = useState<Stages>({ state: 'unchosen' })

  async function choose(chosen: string) {
    setColumn(chosen)
    if (!chosen) return setStages({ state: 'unchosen' })
    setStages({ state: 'loading' })
    try {
      const { data, error, response } = await client.GET(
        '/advertisers/{advertiser_id}/files/stage-history/crm-stages',
        { params: { path: { advertiser_id: advertiserId }, query: { column: chosen } } },
      )
      setStages(data ? { state: 'listed', stages: data } : { state: 'failed', problem: refusal(error, response) })
    } catch {
      setStages({ state: 'failed', problem: UNREACHABLE })
    }
  }

  return (
    <div className="crm-stages">
      <h4>CRM stages</h4>
      <p className="muted">
        Pick the column that holds the CRM's own name for each stage to see every name it uses.
      </p>
      <div className="field">
        <label htmlFor={selectId}>Column holding the CRM stage</label>
        <select id={selectId} value={column} onChange={(event) => choose(event.target.value)}>
          <option value="">Choose a column</option>
          {file.column_names.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>
      </div>
      {stages.state === 'loading' && <p className="muted">Reading the stage names…</p>}
      {stages.state === 'failed' && (
        <p className="problem" role="alert">
          {stages.problem}
        </p>
      )}
      {stages.state === 'listed' && (
        <div className="table-scroll">
          <table aria-label="CRM stages">
            <thead>
              <tr>
                <th scope="col">CRM stage</th>
                <th scope="col" className="number">
                  Rows
                </th>
              </tr>
            </thead>
            <tbody>
              {stages.stages.map((stage) => (
                <tr key={stage.name}>
                  <th scope="row">{stage.name}</th>
                  <td className="number data">{stage.row_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
