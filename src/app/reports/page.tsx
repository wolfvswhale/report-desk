import Link from 'next/link'
import { createClient } from '@/lib/supabase/server'

const OUTCOME_STYLES: Record<string, string> = {
  pass: 'bg-emerald-50 text-emerald-700',
  caution: 'bg-amber-50 text-amber-700',
  fail: 'bg-red-50 text-red-700',
}

export default async function ReportsPage() {
  const supabase = await createClient()

  const { data: firm } = await supabase
    .from('firms')
    .select('name, caution_threshold, action_threshold')
    .single()

  const { data: reports } = await supabase
    .from('reports')
    .select('id, property_address, property_city, property_state, test_started_at, average_pci, outcome, status')
    .order('created_at', { ascending: false })

  return (
    <main className="min-h-screen bg-stone-50">
      <header className="border-b border-stone-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <div>
            <p className="text-sm font-semibold text-stone-900">
              {firm?.name ?? 'Report Desk'}
            </p>
            <p className="text-xs text-stone-500">
              Caution at {firm?.caution_threshold} pCi/L · Action at{' '}
              {firm?.action_threshold} pCi/L
            </p>
          </div>
          <form action="/auth/signout" method="post">
            <button className="text-sm text-stone-500 hover:text-stone-900">
              Sign out
            </button>
          </form>
        </div>
      </header>

      <div className="mx-auto max-w-4xl px-6 py-10">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-stone-900">Reports</h1>
          <Link
            href="/reports/new"
            className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800"
          >
            New report
          </Link>
        </div>

        <div className="mt-5 overflow-hidden rounded-xl border border-stone-200 bg-white">
          {(reports ?? []).length === 0 && (
            <p className="px-5 py-8 text-sm text-stone-500">
              No reports yet.
            </p>
          )}

          {(reports ?? []).map((r) => (
            <div
              key={r.id}
              className="flex items-center justify-between border-b border-stone-100 px-5 py-4 last:border-0"
            >
              <div>
                <p className="text-sm font-medium text-stone-900">
                  {r.property_address}
                </p>
                <p className="text-xs text-stone-500">
                  {r.property_city}, {r.property_state} ·{' '}
                  {new Date(r.test_started_at).toLocaleDateString()}
                </p>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-sm tabular-nums text-stone-700">
                  {r.average_pci} pCi/L
                </span>
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${
                    OUTCOME_STYLES[r.outcome ?? ''] ?? 'bg-stone-100 text-stone-600'
                  }`}
                >
                  {r.outcome ?? r.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </main>
  )
}
