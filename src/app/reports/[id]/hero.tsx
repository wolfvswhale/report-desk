'use client'

import { useEffect, useState } from 'react'

// Counts up from zero on load. The number is the whole point of the screen.
export function HeroNumber({ value }: { value: number }) {
  const [n, setN] = useState(0)

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setN(value)
      return
    }
    const t0 = performance.now()
    let raf = 0
    const tick = (t: number) => {
      const p = Math.min(1, (t - t0) / 1100)
      setN(value * (1 - Math.pow(1 - p, 3)))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value])

  return (
    <span
      className="rd-num font-extrabold text-white"
      style={{
        fontSize: 'clamp(72px, 13vw, 132px)',
        lineHeight: 0.82,
        letterSpacing: '-0.045em',
        textShadow: '0 0 60px rgba(18,200,224,.28)',
      }}
    >
      {n.toFixed(1)}
    </span>
  )
}
