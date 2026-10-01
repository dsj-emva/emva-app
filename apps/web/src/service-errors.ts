// What a proxy in front of the service answers when it cannot reach it.
const GATEWAY_FAILURES = new Set([502, 503, 504])

export const UNREACHABLE = 'Service unreachable'
export const ANSWERED_WITH_ERROR = 'Service answered with an error'

// The message to show when the service did not do what was asked: its own reason when it gave
// one (it may answer 503 itself), otherwise whether it could be reached at all.
export function refusal(error: unknown, response: Response): string {
  if (typeof error === 'object' && error !== null && 'detail' in error) {
    const { detail } = error
    if (typeof detail === 'string') return detail
  }
  return isGatewayFailure(response) ? UNREACHABLE : ANSWERED_WITH_ERROR
}

export function isGatewayFailure(response: Response): boolean {
  return GATEWAY_FAILURES.has(response.status)
}
