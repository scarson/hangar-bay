// ABOUTME: Wire-shape fixtures for GET /me — the SPA's identity source in the fixture lane.
// ABOUTME: makeCurrentUser overrides let specs vary identity without inventing new wire shapes.
export interface WireCurrentUser {
  character_id: number
  character_name: string
}

export function makeCurrentUser(overrides: Partial<WireCurrentUser> = {}): WireCurrentUser {
  return { character_id: 91_000_001, character_name: 'Sesta Hound', ...overrides }
}
