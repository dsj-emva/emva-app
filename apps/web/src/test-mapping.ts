import type { components } from '@emva/api-client'

type MappingReview = components['schemas']['MappingReview']

// What the service says each column can hold and where a CRM stage can be placed.
export const CHOICES: Pick<
  MappingReview,
  'leads_roles' | 'stage_history_roles' | 'input_kinds' | 'stages_and_lost' | 'date_orders'
> = {
  date_orders: [
    { value: 'year_month_day', label: 'Year-month-day (2024-01-05)' },
    { value: 'day_month_year', label: 'Day-month-year (05/01/2024)' },
    { value: 'month_day_year', label: 'Month-day-year (01/05/2024)' },
  ],
  leads_roles: [
    { role: 'lead_id', label: 'Lead identifier' },
    { role: 'submitted_at', label: 'Submission time' },
    { role: 'name', label: 'Name (removed)' },
    { role: 'email', label: 'Email (scrambled)' },
    { role: 'phone', label: 'Phone (scrambled)' },
    { role: 'country', label: 'Country (reads the phone)' },
    { role: 'currency', label: 'Currency (reads the phone)' },
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
