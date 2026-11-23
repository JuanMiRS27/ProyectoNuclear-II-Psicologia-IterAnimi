import { useEffect, useRef, useState } from 'react'

/** Cuenta atrás de presentación hacia una fecha límite. La fecha y el cierre los decide siempre el servidor. */
export function useCountdown(deadline: number, onZero: () => void) {
  const [now, setNow] = useState(() => Date.now())
  const zeroRef = useRef(onZero)
  const firedFor = useRef<number | null>(null)
  useEffect(() => {
    zeroRef.current = onZero
  })
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])
  const left = Math.max(0, Math.ceil((deadline - now) / 1000))
  useEffect(() => {
    if (left === 0 && firedFor.current !== deadline) {
      firedFor.current = deadline
      zeroRef.current()
    }
  }, [left, deadline])
  return left
}
