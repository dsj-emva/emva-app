import type { ApiClient, components } from '@emva/api-client'
import { type ChangeEvent, useId, useState } from 'react'

import { refusal, UNREACHABLE } from './service-errors.ts'
import { FILES, fileOf } from './uploaded-files.ts'

type Advertiser = components['schemas']['Advertiser']
type FileProfile = components['schemas']['FileProfile']

export function UploadStep({
  client,
  advertiser,
  onChanged,
}: {
  client: ApiClient
  advertiser: Advertiser
  onChanged: (advertiser: Advertiser) => void
}) {
  return (
    <div className="upload-grid">
      {FILES.map(({ kind, label, holds }, index) => (
        <FilePanel
          key={kind}
          number={index + 1}
          label={label}
          holds={holds}
          file={fileOf(advertiser, kind)}
          upload={async (file) => {
            const { data, error, response } = await client.PUT(
              '/advertisers/{advertiser_id}/files/{kind}',
              {
                params: {
                  path: { advertiser_id: advertiser.id, kind },
                  query: { file_name: file.name },
                },
                body: file,
                bodySerializer: (body) => body,
                headers: { 'Content-Type': 'text/csv' },
              },
            )
            if (!data) return refusal(error, response)
            const latest = await client.GET('/advertisers/{advertiser_id}', {
              params: { path: { advertiser_id: advertiser.id } },
            })
            if (!latest.data) return refusal(latest.error, latest.response)
            onChanged(latest.data)
            return null
          }}
        />
      ))}
    </div>
  )
}

function FilePanel({
  number,
  label,
  holds,
  file,
  upload,
}: {
  number: number
  label: string
  holds: string
  file: FileProfile | null
  upload: (file: File) => Promise<string | null>
}) {
  const headingId = useId()
  const inputId = useId()
  const [sending, setSending] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  async function choose(event: ChangeEvent<HTMLInputElement>) {
    const chosen = event.target.files?.[0]
    event.target.value = ''
    if (!chosen) return
    setSending(true)
    setProblem(null)
    try {
      setProblem(await upload(chosen))
    } catch {
      setProblem(UNREACHABLE)
    } finally {
      setSending(false)
    }
  }

  return (
    <section className="panel" aria-labelledby={headingId} data-uploaded={file !== null}>
      <p className="panel-number" aria-hidden="true">
        {String(number).padStart(2, '0')}
      </p>
      <h3 id={headingId}>{label}</h3>
      <p className="muted">{holds}</p>
      {file && (
        <dl className="file-facts">
          <div>
            <dt>File</dt>
            <dd className="data">{file.file_name}</dd>
          </div>
          <div>
            <dt>Rows</dt>
            <dd className="data">{file.row_count} rows</dd>
          </div>
          <div>
            <dt>Uploaded</dt>
            <dd className="data">{formatTime(file.uploaded_at)}</dd>
          </div>
        </dl>
      )}
      <div className="file-pick">
        <label htmlFor={inputId} className="secondary" data-busy={sending}>
          {sending
            ? 'Uploading…'
            : `${file ? 'Replace' : 'Choose'} the ${label.toLowerCase()}`}
        </label>
        <input
          id={inputId}
          type="file"
          accept=".csv,text/csv"
          className="visually-hidden"
          disabled={sending}
          onChange={choose}
        />
        {problem && (
          <p className="problem" role="alert">
            {problem}
          </p>
        )}
      </div>
    </section>
  )
}

function formatTime(iso: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(
    new Date(iso),
  )
}
