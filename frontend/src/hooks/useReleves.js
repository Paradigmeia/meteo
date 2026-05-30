import { useState, useEffect } from 'react'

const API = import.meta.env.VITE_API_URL ?? ''

export function useReleves(slug, period) {
  const [releves, setReleves] = useState([])

  useEffect(() => {
    if (!slug) return
    let cancelled = false
    let timer

    async function load() {
      try {
        const res = await window.fetch(`${API}/api/releves/${slug}?period=${period}`)
        if (res.ok && !cancelled) setReleves(await res.json())
      } catch {}
      if (!cancelled) timer = setTimeout(load, 30_000)
    }
    load()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [slug, period])

  return { releves }
}
