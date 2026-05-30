import { useState, useEffect } from 'react'

const API = import.meta.env.VITE_API_URL ?? ''

export function useSondes() {
  const [sondes, setSondes] = useState([])

  useEffect(() => {
    let timer
    async function fetch() {
      try {
        const res = await window.fetch(`${API}/api/sondes`)
        if (res.ok) setSondes(await res.json())
      } catch {}
      timer = setTimeout(fetch, 30_000)
    }
    fetch()
    return () => clearTimeout(timer)
  }, [])

  return { sondes }
}
