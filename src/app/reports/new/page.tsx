'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Backdrop, Mark } from '@/components/shell'

function Drop({
  label, hint, accept, file, onPick, glyph,
}: {
  label: string; hint: string; accept: string
  file: File | null; onPick: (f: File | null) => void; glyph: string
}) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const filled = file !== null

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setOver(true) }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onPick(e.dataTransfer.files?.[0] ?? null) }}
      onClick={() => input.current?.click()}
      className="cursor-pointer rounded-2xl p-7 text-center transition-all"
      style={{
        border: `1px ${filled ? 'solid' : 'dashed'} ${over || filled ? 'var(--accent)' : 'var(--edge)'}`,
        background: over ? 'rgba(18,200,224,.09)' : filled ? 'rgba(18,200,224,.05)' : 'var(--glass)',
      }}
    >
      <div className="text-2xl" style={{ color: filled ? 'var(--accent)' : 'var(--dim)' }}>
        {filled ? '✓' : glyph}
      </div>
      <p className="mt-2 text-[11px] font-extrabold uppercase tracking-[0.14em] text-white">{label}</p>
      <p className="mt-1 text-[13px]" style={{ color: filled ? 'var(--accent)' : 'var(--dim)' }}>
        {file ? file.name : hint}
      </p>
      <input ref={input} type="file" accept={accept} className="hidden"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)} />
    </div>
  )
}

export default function NewReportPage() {
  const router = useRouter()
  const [pdf, setPdf] = useState<File | null>(null)
  const [photo, setPhoto] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ready = pdf !== null && photo !== null && !busy

  useEffect(() => { fetch('/api/warm', { method: 'POST' }).catch(() => {}) }, [])

  async function loadSamples() {
    setError(null); setBusy(true)
    try {
      const [p, h] = await Promise.all([
        fetch('/samples/sample-monitor-data.pdf').then((r) => r.blob()),
        fetch('/samples/sample-house.jpg').then((r) => r.blob()),
      ])
      setPdf(new File([p], 'sample-monitor-data.pdf', { type: 'application/pdf' }))
      setPhoto(new File([h], 'sample-house.jpg', { type: 'image/jpeg' }))
    } catch { setError('could not load the sample files') }
    setBusy(false)
  }

  async function submit() {
    if (!pdf || !photo) return
    setBusy(true); setError(null)
    const body = new FormData()
    body.append('raw_pdf', pdf)
    body.append('house_photo', photo)
    const res = await fetch('/api/reports', { method: 'POST', body })
    const json = await res.json()
    if (!res.ok) { setError(json.error ?? 'something went wrong'); setBusy(false); return }
    router.push(`/reports/${json.id}`)
    router.refresh()
  }

  return (
    <main className="relative min-h-screen overflow-hidden" style={{ background: 'var(--base)' }}>
      <Backdrop />
      <div className="relative z-10 mx-auto max-w-xl px-6 py-10 sm:py-14">
        <div className="flex items-center justify-between">
          <Mark small />
          <Link href="/reports" className="text-[11px] font-bold uppercase tracking-[0.14em]" style={{ color: 'var(--dim)' }}>
            ← Reports
          </Link>
        </div>

        <div className="rd-rise mt-10 flex gap-5">
          <div className="rd-bar" />
          <div>
            <h1 className="rd-h1">New report</h1>
            <p className="mt-3 text-sm leading-relaxed" style={{ color: 'var(--body)' }}>
              Two files in, seven pages out. Address, dates, serial number and
              every hourly reading are pulled from the monitor file — you type nothing.
            </p>
          </div>
        </div>

        <div className="rd-rise mt-8 grid gap-3" style={{ animationDelay: '.1s' }}>
          <Drop glyph="▤" label="Monitor data PDF" hint="The file the SunRADON unit prints"
            accept="application/pdf" file={pdf} onPick={setPdf} />
          <Drop glyph="▦" label="House photo" hint="Goes on the cover"
            accept="image/*" file={photo} onPick={setPhoto} />
        </div>

        <button type="button" onClick={loadSamples} disabled={busy}
          className="mt-4 text-[13px] underline underline-offset-4 disabled:opacity-40"
          style={{ color: 'var(--dim)' }}>
          No monitor file? Use the sample pair
        </button>

        {error && (
          <p className="mt-4 rounded-lg px-3 py-2 text-sm"
            style={{ background: 'rgba(208,59,59,.12)', color: '#ff9a9a' }}>
            {error}
          </p>
        )}

        <button onClick={submit} disabled={!ready} className="rd-btn mt-6 w-full justify-center">
          {busy ? 'Building the report…' : 'Generate report'}
        </button>

        {busy && (
          <p className="mt-3 text-center text-[11px] font-bold uppercase tracking-[0.13em]" style={{ color: 'var(--dim)' }}>
            Reading the file · pulling outdoor weather · drawing seven pages
          </p>
        )}
      </div>
    </main>
  )
}
