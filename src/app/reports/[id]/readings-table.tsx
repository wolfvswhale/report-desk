'use client'

import { useState } from 'react'

type Reading = { recorded_at: string; pci: number }

export default function ReadingsTable({
  readings,
  caution,
  action,
}: {
  readings: Reading[]
  caution: number
  action: number
}) {
  const [open, setOpen] = useState(false)

  if (!readings.length) return null

  const values = readings.map((r) => Number(r.pci))
  const high = Math.max(...values)
  const low = Math.min(...values)
  const peak = Math.max(high, action)
  const shown = open ? readings : readings.slice(0, 12)

  function tone(v: number) {
    if (v >= action) return 'text-red-700'
    if (v >= caution) return 'text-amber-700'
    return 'text-stone-700'
  }

  return (
    <section className="mt-8 pb-10">
      <div className="flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-stone-900">
          Hourly readings
        </h2>
        <p className="text-xs text-stone-500">
          {readings.length} readings · high {high} · low {low} pCi/L
        </p>
      </div>

      <p className="mt-1 text-xs text-stone-400">
        The numbers the PDF was built from. Check the math without opening the
        file.
      </p>

      <div className="mt-3 flex h-24 items-end gap-[3px] rounded-xl border border-stone-200 bg-white p-3">
        {values.map((v, i) => (
          <div
            key={i}
            title={`${v} pCi/L`}
            style={{ height: `${Math.max(4, (v / peak) * 100)}%` }}
            className={`flex-1 rounded-sm ${
              v >= action
                ? 'bg-red-400'
                : v >= caution
                  ? 'bg-amber-400'
                  : 'bg-stone-300'
            }`}
          />
        ))}
      </div>

      <div className="mt-3 overflow-hidden rounded-xl border border-stone-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-stone-100 text-left text-xs uppercase tracking-wide text-stone-400">
              <th className="px-5 py-2.5 font-medium">Time</th>
              <th className="px-5 py-2.5 text-right font-medium">pCi/L</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => (
              <tr key={i} className="border-b border-stone-50 last:border-0">
                <td className="px-5 py-2 text-stone-600">
                  {new Date(r.recorded_at).toLocaleString()}
                </td>
                <td
                  className={`px-5 py-2 text-right tabular-nums ${tone(Number(r.pci))}`}
                >
                  {r.pci}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {readings.length > 12 && (
          <button
            onClick={() => setOpen(!open)}
            className="w-full border-t border-stone-100 px-5 py-3 text-sm text-stone-500 hover:bg-stone-50 hover:text-stone-900"
          >
            {open
              ? 'Show fewer'
              : `Show all ${readings.length} readings`}
          </button>
        )}
      </div>
    </section>
  )
}
