'use client'

import { useState } from 'react'

type Reading = { recorded_at: string; pci: number }

const W = 980, H = 250, PL = 46, PR = 20, PT = 18, PB = 30
const iw = W - PL - PR, ih = H - PT - PB

export function Trace({
  readings, caution, action,
}: { readings: Reading[]; caution: number; action: number }) {
  const [hover, setHover] = useState<number | null>(null)
  if (!readings.length) return null

  const vals = readings.map((r) => Number(r.pci))
  const hi = Math.max(...vals), lo = Math.min(...vals)
  const yMax = Math.max(action + 0.8, hi + 0.6)
  const x = (i: number) => PL + (i / (readings.length - 1)) * iw
  const y = (v: number) => PT + ih - (v / yMax) * ih

  const line = vals.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')
  const ticks = [0, Math.floor(readings.length / 4), Math.floor(readings.length / 2),
                 Math.floor((readings.length * 3) / 4), readings.length - 1]
  const when = (s: string) =>
    new Date(s).toLocaleString([], { month: 'numeric', day: 'numeric', hour: 'numeric' })

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="block w-full"
        role="img"
        aria-label={`Radon concentration over ${readings.length} hours. High ${hi}, low ${lo} pCi per litre.`}>
        <defs>
          <linearGradient id="rdfill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="#12c8e0" stopOpacity=".38" />
            <stop offset="1" stopColor="#12c8e0" stopOpacity="0" />
          </linearGradient>
        </defs>

        <rect x={PL} y={y(action)} width={iw} height={Math.max(0, y(caution) - y(action))}
          fill="rgba(250,178,25,.07)" />

        {[0, 2, 4].filter((v) => v <= yMax).map((v) => (
          <g key={v}>
            <line x1={PL} x2={W - PR} y1={y(v)} y2={y(v)} stroke="rgba(255,255,255,.07)" />
            <text x={PL - 10} y={y(v) + 4} textAnchor="end" fontSize="10" fill="#7d8798"
              fontFamily="ui-monospace, monospace">{v}</text>
          </g>
        ))}

        <path className="rd-fade" d={`${line}L${x(vals.length - 1)},${y(0)}L${PL},${y(0)}Z`} fill="url(#rdfill)" />
        <path className="rd-trace" d={line} fill="none" stroke="#12c8e0" strokeWidth="2.5"
          strokeLinejoin="round" strokeLinecap="round"
          style={{ filter: 'drop-shadow(0 0 7px rgba(18,200,224,.65))' }} />

        <line x1={PL} x2={W - PR} y1={y(action)} y2={y(action)} stroke="#d03b3b" strokeWidth="1.5" strokeDasharray="6 5" />
        <text x={W - PR} y={y(action) - 8} textAnchor="end" fontSize="10" fontWeight="700" fill="#d03b3b" letterSpacing="1">
          ACTION LEVEL {action}
        </text>
        <line x1={PL} x2={W - PR} y1={y(caution)} y2={y(caution)} stroke="#fab219" strokeWidth="1.5" strokeDasharray="3 5" />
        <text x={W - PR} y={y(caution) + 15} textAnchor="end" fontSize="10" fontWeight="700" fill="#fab219" letterSpacing="1">
          CAUTION {caution}
        </text>

        {ticks.map((i) => (
          <text key={i} x={x(i)} y={H - 9} textAnchor="middle" fontSize="10" fill="#7d8798"
            fontFamily="ui-monospace, monospace">{when(readings[i].recorded_at)}</text>
        ))}

        {hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={PT} y2={PT + ih} stroke="rgba(255,255,255,.28)" />
            <circle cx={x(hover)} cy={y(vals[hover])} r="5" fill="#12c8e0" stroke="#060a13" strokeWidth="2" />
          </g>
        )}

        {readings.map((_, i) => (
          <rect key={i} x={x(i) - iw / readings.length / 2} y={PT}
            width={iw / readings.length} height={ih} fill="transparent"
            onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} />
        ))}
      </svg>

      <p className="mt-1 h-5 text-center text-[12px] font-bold tracking-[0.06em]" style={{ color: 'var(--dim)' }}>
        {hover !== null
          ? `${when(readings[hover].recorded_at)}:00 — ${vals[hover].toFixed(1)} pCi/L`
          : `HIGH ${hi.toFixed(1)} · LOW ${lo.toFixed(1)} · ${readings.length} READINGS`}
      </p>
    </div>
  )
}
