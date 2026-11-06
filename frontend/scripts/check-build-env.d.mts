// Types for check-build-env.mjs, so vite.config.ts can import it under tsc -b.
type Env = Record<string, string | undefined>

export function apiBaseUrlError(value: string | undefined): string | null
export function supabaseUrlError(value: string | undefined): string | null
export function supabaseAnonKeyError(value: string | undefined): string | null
export function buildEnvErrors(env: Env): string[]
export function assertBuildEnv(env: Env): void
