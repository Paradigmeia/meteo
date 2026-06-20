import { useState, useEffect } from 'react'

export function useIsDesktop(minWidth = 768) {
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= minWidth)

  useEffect(() => {
    const mq = window.matchMedia(`(min-width: ${minWidth}px)`)
    const handler = () => setIsDesktop(mq.matches)
    handler()
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [minWidth])

  return isDesktop
}
