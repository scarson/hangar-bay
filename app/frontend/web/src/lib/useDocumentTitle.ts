import { useEffect } from 'react'

const SUFFIX = 'Hangar Bay'

/**
 * Sets a descriptive per-view document title (WCAG 2.4.2). Every route names
 * itself so bookmarks/history/tab labels describe the view — not the Vite
 * scaffold's static "web" — and shareable URLs (PRODUCT principle #2) carry a
 * meaningful title. Pass the page-specific part; the brand suffix is appended.
 */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    document.title = title ? `${title} — ${SUFFIX}` : SUFFIX
  }, [title])
}
