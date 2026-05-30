import { useState, useEffect } from 'react'

const API = import.meta.env.VITE_API_URL ?? ''

export function useMeteo() {
  const [meteo, setMeteo] = useState(null)

  useEffect(() => {
    let timer
    async function fetch() {
      try {
        const res = await window.fetch(`${API}/api/meteo`)
        if (res.ok) setMeteo(await res.json())
      } catch {}
      timer = setTimeout(fetch, 30_000)
    }
    fetch()
    return () => clearTimeout(timer)
  }, [])

  return { meteo }
}
