import { useState, useEffect } from 'react'

const API = import.meta.env.VITE_API_URL ?? ''

export function useSondes() {
  const [sondes, setSondes] = useState([])

  useEffect(() => {
    let cancelled = false
    let timer

    async function load() {
      try {
        const res = await window.fetch(`${API}/api/sondes`)
        if (res.ok && !cancelled) setSondes(await res.json())
      } catch {}
      if (!cancelled) timer = setTimeout(load, 30_000)
    }
    load()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [])

  return { sondes }
}
