import { useState, useEffect } from 'react'

const API = import.meta.env.VITE_API_URL ?? ''

export function useReleves(slug, period) {
  const [releves, setReleves] = useState([])

  useEffect(() => {
    if (!slug) return
    async function fetch() {
      try {
        const res = await window.fetch(`${API}/api/releves/${slug}?period=${period}`)
        if (res.ok) setReleves(await res.json())
      } catch {}
    }
    fetch()
  }, [slug, period])

  return { releves }
}
