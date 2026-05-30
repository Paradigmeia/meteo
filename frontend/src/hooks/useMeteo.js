import { useState, useEffect } from 'react'

const API = import.meta.env.VITE_API_URL ?? ''

export function useMeteo() {
  const [meteo, setMeteo] = useState(null)

  useEffect(() => {
    let cancelled = false
    let timer

    async function load() {
      try {
        const res = await window.fetch(`${API}/api/meteo`)
        if (res.ok && !cancelled) setMeteo(await res.json())
      } catch {}
      if (!cancelled) timer = setTimeout(load, 30_000)
    }
    load()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [])

  return { meteo }
}
