import type { components } from '@emva/api-client'

export type DataSource = components['schemas']['DataSource']

export const DATA_SOURCES: { value: DataSource; label: string }[] = [
  { value: 'hand_made_test', label: 'Hand-made test data' },
  { value: 'simulated', label: 'Simulated data' },
  { value: 'public', label: 'Public data' },
  { value: 'private', label: 'Private export' },
]

export function dataSourceLabel(source: DataSource): string {
  return DATA_SOURCES.find(({ value }) => value === source)?.label ?? source
}
