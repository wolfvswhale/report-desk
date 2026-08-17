import Link from 'next/link'
import { createClient } from '@/lib/supabase/server'
import { Backdrop, Header } from '@/components/shell'
import { OutcomePill } from '@/components/outcome'

export default async function ReportsPage() {
  const supabase = await createClient()

  const { data: firm } = await supabase
    .from('firms')
    .select('name, caution_threshold, action_threshold')
    .single()

  const { data: reports } = await supabase
    .from('reports')
    .select('id, property_address, property_city, property_state, test_started_at, average_pci, outcome, status, client_name, report_number')
    .order('created_at', { ascending: false })

  const list = reports ?? []

  return (
    <main className="relative min-h-screen overflow-hidden" style={{ background: 'var(--base)' }}>
      <Backdrop />
      <div className="relative z-10">
        <Header firmName={firm?.name} />

        <div className="mx-auto max-w-5xl px-6 py-12 sm:px-10">
          <div className="rd-rise flex flex-wrap items-end justify-between gap-5">
            <div className="flex gap-5">
              <div className="rd-bar" />
              <div>
                <h1 className="rd-h1">Reports</h1>
                <p className="mt-2 text-[11px] font-bold uppercase tracking-[0.13em]" style={{ color: 'var(--dim)' }}>
                  Caution at {firm?.caution_threshold} pCi/L &nbsp;·&nbsp; Action at {firm?.action_threshold} pCi/L
                </p>
              </div>
            </div>
            <Link href="/reports/new" className="rd-btn">+ New report</Link>
          </div>

          {list.length === 0 && (
            <div className="rd-panel rd-rise mt-8 px-8 py-16 text-center" style={{ animationDelay: '.1s' }}>
              <p className="rd-h1" style={{ fontSize: 22 }}>Nothing here yet</p>
              <p className="mx-auto mt-3 max-w-sm text-sm leading-relaxed" style={{ color: 'var(--body)' }}>
                Drop in a monitor file and a photo of the house. The first report
                takes about fifteen seconds.
              </p>
              <Link href="/reports/new" className="rd-btn mt-6">+ New report</Link>
            </div>
          )}

          {list.length > 0 && (
            <div className="rd-panel rd-rise mt-8 overflow-hidden" style={{ animationDelay: '.1s' }}>
              {list.map((r, i) => (
                <Link
                  key={r.id}
                  href={`/reports/${r.id}`}
                  className="flex flex-wrap items-center gap-4 px-6 py-5 transition-colors hover:bg-white/[0.04]"
                  style={{ borderTop: i === 0 ? 'none' : '1px solid var(--hair)' }}
                >
                  <div className="min-w-[220px] flex-1">
                    <p className="text-[15px] font-bold text-white">{r.property_address}</p>
                    <p className="mt-1 text-[11px] font-bold uppercase tracking-[0.12em]" style={{ color: 'var(--dim)' }}>
                      {[r.property_city, r.property_state].filter(Boolean).join(', ')}
                      {r.report_number ? ` · ${r.report_number}` : ''}
                      {' · '}
                      {new Date(r.test_started_at).toLocaleDateString()}
                    </p>
                  </div>
                  <span className="rd-num text-lg font-extrabold text-white">
                    {r.average_pci}
                    <span className="ml-1 text-[11px] font-bold uppercase tracking-[0.12em]" style={{ color: 'var(--dim)' }}>
                      pCi/L
                    </span>
                  </span>
                  <OutcomePill outcome={r.outcome ?? r.status} size="sm" />
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  )
}
