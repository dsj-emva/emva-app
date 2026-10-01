import type { components } from '@emva/api-client'

type MappingReview = components['schemas']['MappingReview']

// What the service says each column can hold and where a CRM stage can be placed.
export const CHOICES: Pick<
  MappingReview,
  'leads_roles' | 'stage_history_roles' | 'input_kinds' | 'stages_and_lost'
> = {
  leads_roles: [
    { role: 'lead_id', label: 'Lead identifier' },
    { role: 'submitted_at', label: 'Submission time' },
    { role: 'name', label: 'Name (removed)' },
    { role: 'email', label: 'Email (scrambled)' },
    { role: 'phone', label: 'Phone (scrambled)' },
  ],
  stage_history_roles: [
    { role: 'lead_id', label: 'Lead identifier' },
    { role: 'crm_stage', label: 'CRM stage' },
    { role: 'changed_at', label: 'When the change happened' },
    { role: 'deal_value', label: 'Deal value' },
  ],
  input_kinds: [
    { kind: 'number', label: 'Number' },
    { kind: 'category', label: 'Category' },
  ],
  stages_and_lost: [
    { value: 'submitted', name: 'Submitted' },
    { value: 'contact_attempted', name: 'Contact attempted' },
    { value: 'engaged', name: 'Engaged' },
    { value: 'qualified', name: 'Qualified' },
    { value: 'proposal', name: 'Proposal' },
    { value: 'won', name: 'Won' },
    { value: 'lost', name: 'Lost' },
  ],
}
