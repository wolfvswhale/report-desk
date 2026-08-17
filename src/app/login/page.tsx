'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { Backdrop, Mark } from '@/components/shell'

export default function LoginPage() {
  const router = useRouter()
  const supabase = createClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<null | 'form' | 'demo'>(null)

  // Start waking the generator now, not when they reach the upload page.
  useEffect(() => {
    fetch('/api/warm', { method: 'POST' }).catch(() => {})
  }, [])

  async function signIn(nextEmail: string, nextPassword: string) {
    setError(null)
    const { error } = await supabase.auth.signInWithPassword({
      email: nextEmail,
      password: nextPassword,
    })
    if (error) {
      setError(error.message)
      setBusy(null)
      return
    }
    router.push('/reports')
    router.refresh()
  }

  return (
    <main className="relative min-h-screen overflow-hidden" style={{ background: 'var(--base)' }}>
      <Backdrop />
      <div className="relative z-10 mx-auto flex min-h-screen max-w-md flex-col justify-center px-6 py-16">
        <div className="rd-rise">
          <Mark />
          <div className="mt-8 flex gap-5">
            <div className="rd-bar" />
            <div>
              <h1 className="rd-h1">
                Radon reports,<br />start to finished PDF
              </h1>
              <p className="mt-3 text-sm leading-relaxed" style={{ color: 'var(--body)' }}>
                Drop in the monitor&apos;s data file and a photo of the house.
                Seven pages come back. You type nothing.
              </p>
            </div>
          </div>
        </div>

        <form
          className="rd-panel rd-rise mt-9 p-6"
          style={{ animationDelay: '.1s' }}
          onSubmit={(e) => {
            e.preventDefault()
            setBusy('form')
            signIn(email, password)
          }}
        >
          <label className="rd-label">Email</label>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rd-input mt-2"
          />

          <label className="rd-label mt-5 block">Password</label>
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rd-input mt-2"
          />

          {error && (
            <p
              className="mt-4 rounded-lg px-3 py-2 text-sm"
              style={{ background: 'rgba(208,59,59,.12)', color: '#ff9a9a' }}
            >
              {error}
            </p>
          )}

          <button type="submit" disabled={busy !== null} className="rd-btn mt-6 w-full justify-center">
            {busy === 'form' ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <div
          className="rd-rise mt-5 rounded-2xl p-5"
          style={{ border: '1px dashed rgba(18,200,224,.4)', background: 'rgba(18,200,224,.05)', animationDelay: '.2s' }}
        >
          <p className="rd-badge">◆ No signup</p>
          <p className="mt-3 text-sm leading-relaxed" style={{ color: 'var(--body)' }}>
            Open a working account with sample data and generate a real report.
            Nothing inside belongs to anyone.
          </p>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => {
              setBusy('demo')
              signIn('demo@reportdesk.app', 'demo1234')
            }}
            className="rd-btn-ghost mt-4 w-full justify-center"
          >
            {busy === 'demo' ? 'Opening demo…' : 'Try the demo →'}
          </button>
        </div>

        <p className="mt-8 text-center text-[11px] font-bold uppercase tracking-[0.16em]" style={{ color: 'var(--dim)' }}>
          Built by J. Alderman Lyell
        </p>
      </div>
    </main>
  )
}
