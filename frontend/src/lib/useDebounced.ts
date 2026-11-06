import { useEffect, useState } from 'react'

/** Text input that only commits its value after typing pauses. */
export function useDebounced(value: string, onCommit: (v: string) => void, delay = 300) {
  const [draft, setDraft] = useState(value)
  const [committed, setCommitted] = useState(value)
  // The URL value changed elsewhere (e.g. "Clear filters"): show it.
  if (value !== committed) {
    setCommitted(value)
    setDraft(value)
  }
  useEffect(() => {
    if (draft === value) return
    const timer = setTimeout(() => onCommit(draft), delay)
    return () => clearTimeout(timer)
  }, [draft, value, onCommit, delay])
  return [draft, setDraft] as const
}

