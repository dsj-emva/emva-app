import type { ApiClient, components } from '@emva/api-client'
import { type FormEvent, useState } from 'react'

import { DATA_SOURCES, type DataSource } from './data-sources.ts'
import { refusal, UNREACHABLE } from './service-errors.ts'

type Advertiser = components['schemas']['Advertiser']

export function AdvertiserForm({
  client,
  onCreated,
}: {
  client: ApiClient
  onCreated: (advertiser: Advertiser) => void
}) {
  const [name, setName] = useState('')
  const [source, setSource] = useState<DataSource | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [sending, setSending] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (source === null) return
    setSending(true)
    setProblem(null)
    try {
      const { data, error, response } = await client.POST('/advertisers', {
        body: { name, data_source: source },
      })
      if (data) onCreated(data)
      else setProblem(response.status === 422 ? 'Give the advertiser a name.' : refusal(error, response))
    } catch {
      setProblem(UNREACHABLE)
    } finally {
      setSending(false)
    }
  }

  return (
    <form className="advertiser-form" onSubmit={submit}>
      <div className="field">
        <label htmlFor="advertiser-name">Advertiser name</label>
        <input
          id="advertiser-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          autoComplete="organization"
          required
        />
      </div>
      <fieldset className="field">
        <legend>Where the data comes from</legend>
        <div className="choices">
          {DATA_SOURCES.map(({ value, label }) => (
            <label key={value} className="choice">
              <input
                type="radio"
                name="data-source"
                value={value}
                checked={source === value}
                onChange={() => setSource(value)}
                required
              />
              <span>{label}</span>
            </label>
          ))}
        </div>
      </fieldset>
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
      <button type="submit" className="primary" disabled={sending}>
        Start
      </button>
    </form>
  )
}
