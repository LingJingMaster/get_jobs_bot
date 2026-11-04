/** Public backend URL; configure NEXT_PUBLIC_API_BASE before building. */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:9527'

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`
}
