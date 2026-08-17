'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'

type DropProps = {
  label: string
  hint: string
  accept: string
  file: File | null
  onPick: (f: File | null) => void
}

function DropField({ label, hint, accept, file, onPick }: DropProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault()
        setOver(false)
        onPick(e.dataTransfer.files?.[0] ?? null)
      }}
      onClick={() => inputRef.current?.click()}
      className={`cursor-pointer rounded-xl border-2 border-dashed p-6 text-center transition ${
        over ? 'border-stone-900 bg-stone-100' : 'border-stone-300 bg-white'
      }`}
    >
      <p className="text-sm font-medium text-stone-800">{label}</p>
      <p className="mt-1 text-xs text-stone-500">{file ? file.name : hint}</p>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)}
      />
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

  // Wake the generator while the person is still choosing files.
  useEffect(() => {
    fetch('/api/warm', { method: 'POST' }).catch(() => {})
  }, [])

  // Lets someone without a radon monitor still run the whole thing.
  async function loadSamples() {
    setError(null)
    setBusy(true)
    try {
      const [p, h] = await Promise.all([
        fetch('/samples/sample-monitor-data.pdf').then((r) => r.blob()),
        fetch('/samples/sample-house.jpg').then((r) => r.blob()),
      ])
      setPdf(new File([p], 'sample-monitor-data.pdf', { type: 'application/pdf' }))
      setPhoto(new File([h], 'sample-house.jpg', { type: 'image/jpeg' }))
    } catch {
      setError('could not load the sample files')
    }
    setBusy(false)
  }

  async function submit() {
    if (!pdf || !photo) return
    setBusy(true)
    setError(null)

    const body = new FormData()
    body.append('raw_pdf', pdf)
    body.append('house_photo', photo)

    const res = await fetch('/api/reports', { method: 'POST', body })
    const json = await res.json()

    if (!res.ok) {
      setError(json.error ?? 'something went wrong')
      setBusy(false)
      return
    }
    router.push('/reports')
    router.refresh()
  }

  return (
    <main className="min-h-screen bg-stone-50">
      <div className="mx-auto max-w-lg px-6 py-10">
        <Link href="/reports" className="text-sm text-stone-500 hover:text-stone-900">
          ← Reports
        </Link>

        <h1 className="mt-4 text-xl font-semibold text-stone-900">New report</h1>
        <p className="mt-1 text-sm text-stone-500">
          Drop in the monitor&apos;s data file and a photo of the house. Everything
          else is read out of the file — you type nothing.
        </p>

        <div className="mt-6 space-y-3">
          <DropField
            label="Monitor data PDF"
            hint="The file the SunRADON unit prints"
            accept="application/pdf"
            file={pdf}
            onPick={setPdf}
          />
          <DropField
            label="House photo"
            hint="Goes on the cover"
            accept="image/*"
            file={photo}
            onPick={setPhoto}
          />
        </div>

        <button
          type="button"
          onClick={loadSamples}
          disabled={busy}
          className="mt-3 text-sm text-stone-500 underline underline-offset-4 hover:text-stone-900 disabled:opacity-40"
        >
          Don&apos;t have a monitor file? Use the sample pair
        </button>

        {error && (
          <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </p>
        )}

        <button
          onClick={submit}
          disabled={!ready}
          className="mt-6 w-full rounded-lg bg-stone-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-40"
        >
          {busy ? 'Building the report…' : 'Generate report'}
        </button>

        {busy && (
          <p className="mt-3 text-center text-xs text-stone-500">
            Reading the file, pulling outdoor weather, drawing seven pages.
            Usually about five seconds.
          </p>
        )}
      </div>
    </main>
  )
}
