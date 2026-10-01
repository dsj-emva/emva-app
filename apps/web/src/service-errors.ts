// What a proxy in front of the service answers when it cannot reach it.
const GATEWAY_FAILURES = new Set([502, 503, 504])

export const UNREACHABLE = 'Service unreachable'

// The message to show when the service did not do what was asked: its own reason when it gave one.
export function refusal(error: unknown, response: Response): string {
  if (GATEWAY_FAILURES.has(response.status)) return UNREACHABLE
  if (typeof error === 'object' && error !== null && 'detail' in error) {
    const { detail } = error
    if (typeof detail === 'string') return detail
  }
  return 'Service answered with an error'
}

export function isGatewayFailure(response: Response): boolean {
  return GATEWAY_FAILURES.has(response.status)
}
