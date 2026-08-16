'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'

export default function LoginPage() {
  const router = useRouter()
  const supabase = createClient()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<null | 'form' | 'demo'>(null)

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
    <main className="flex min-h-screen items-center justify-center bg-stone-50 px-6">
      <div className="w-full max-w-sm">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold tracking-tight text-stone-900">
            Report Desk
          </h1>
          <p className="mt-1 text-sm text-stone-500">
            Radon measurement reports, start to finished PDF.
          </p>
        </div>

        <form
          className="rounded-xl border border-stone-200 bg-white p-6 shadow-sm"
          onSubmit={(e) => {
            e.preventDefault()
            setBusy('form')
            signIn(email, password)
          }}
        >
          <label className="block text-sm font-medium text-stone-700">
            Email
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-stone-900 outline-none focus:border-stone-900"
            />
          </label>

          <label className="mt-4 block text-sm font-medium text-stone-700">
            Password
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-stone-900 outline-none focus:border-stone-900"
            />
          </label>

          {error && (
            <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy !== null}
            className="mt-5 w-full rounded-lg bg-stone-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
          >
            {busy === 'form' ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <div className="mt-6 rounded-xl border border-dashed border-stone-300 bg-white/60 p-5">
          <p className="text-sm font-medium text-stone-800">
            Just looking?
          </p>
          <p className="mt-1 text-sm text-stone-500">
            Open a working account with sample data. No signup, nothing real
            inside.
          </p>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => {
              setBusy('demo')
              signIn('demo@reportdesk.app', 'demo1234')
            }}
            className="mt-3 w-full rounded-lg border border-stone-900 px-4 py-2.5 text-sm font-medium text-stone-900 hover:bg-stone-900 hover:text-white disabled:opacity-50"
          >
            {busy === 'demo' ? 'Opening demo…' : 'Try the demo'}
          </button>
        </div>

        <p className="mt-6 text-center text-xs text-stone-400">
          Built by J. Alderman Lyell
        </p>
      </div>
    </main>
  )
}
