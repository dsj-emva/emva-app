import type { components } from '@emva/api-client'

type Advertiser = components['schemas']['Advertiser']
type FileKind = components['schemas']['FileKind']
type FileProfile = components['schemas']['FileProfile']

// The two files an advertiser uploads, in the order they are shown.
export const FILES: { kind: FileKind; label: string; holds: string }[] = [
  { kind: 'leads', label: 'Leads file', holds: 'One row per lead, as the CRM or form tool writes it.' },
  {
    kind: 'stage-history',
    label: 'Stage-history file',
    holds: "One row per change of a lead's CRM stage.",
  },
]

export function fileOf(advertiser: Advertiser, kind: FileKind): FileProfile | null {
  return kind === 'leads' ? advertiser.leads_file : advertiser.stage_history_file
}
