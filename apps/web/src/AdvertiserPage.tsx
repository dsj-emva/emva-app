import type { ApiClient, components } from '@emva/api-client'
import { useState } from 'react'

import { AdvertiserForm } from './AdvertiserForm.tsx'
import { dataSourceLabel } from './data-sources.ts'
import { ReviewStep } from './ReviewStep.tsx'
import { ServiceStatus } from './ServiceStatus.tsx'
import { UploadStep } from './UploadStep.tsx'

type Advertiser = components['schemas']['Advertiser']
type Step = 'upload' | 'review'

export function AdvertiserPage({ client }: { client: ApiClient }) {
  const [advertiser, setAdvertiser] = useState<Advertiser | null>(null)
  const [step, setStep] = useState<Step>('upload')
  const reviewAvailable = advertiser?.review_available ?? false

  return (
    <div className="shell">
      <header className="masthead">
        <p className="wordmark">Emva</p>
        <nav aria-label="Steps" className="steps">
          <ol>
            <li>
              <button
                type="button"
                aria-current={step === 'upload' ? 'step' : undefined}
                onClick={() => setStep('upload')}
              >
                <span className="step-number">1</span> Upload
              </button>
            </li>
            <li>
              <button
                type="button"
                aria-current={step === 'review' ? 'step' : undefined}
                aria-describedby={reviewAvailable ? undefined : 'review-closed'}
                disabled={!reviewAvailable}
                onClick={() => setStep('review')}
              >
                <span className="step-number">2</span> Review
              </button>
            </li>
          </ol>
          {!reviewAvailable && (
            <p id="review-closed" className="muted step-hint">
              Review opens once both files are uploaded.
            </p>
          )}
        </nav>
      </header>

      <main className="content">
        {advertiser === null ? (
          <>
            <h1>Bring in an advertiser's history</h1>
            <p className="lede">
              Name the advertiser and pick its data source, then upload its leads file and
              stage-history file exactly as they were exported.
            </p>
            <AdvertiserForm client={client} onCreated={setAdvertiser} />
          </>
        ) : (
          <>
            <p className="eyebrow">{dataSourceLabel(advertiser.data_source)}</p>
            <h2 className="advertiser-name">{advertiser.name}</h2>
            {step === 'upload' ? (
              <UploadStep client={client} advertiser={advertiser} onChanged={setAdvertiser} />
            ) : (
              <ReviewStep
                client={client}
                advertiser={advertiser}
                onChanged={() => {
                  client
                    .GET('/advertisers/{advertiser_id}', {
                      params: { path: { advertiser_id: advertiser.id } },
                    })
                    .then(({ data }) => data && setAdvertiser(data))
                    .catch(() => undefined)
                }}
              />
            )}
          </>
        )}
      </main>

      <footer className="footer">
        <ServiceStatus client={client} />
      </footer>
    </div>
  )
}
