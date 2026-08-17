import Link from 'next/link'
import { notFound } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { Backdrop, Header } from '@/components/shell'
import { OutcomePill, outcomeColor } from '@/components/outcome'
import { Trace } from './trace'
import { HeroNumber } from './hero'

function Chip({ k, v }: { k: string; v: string | null }) {
  if (!v) return null
  return (
    <span className="rd-chip">
      <span className="mr-2 text-[11px] font-bold uppercase tracking-[0.1em]" style={{ color: 'var(--dim)' }}>{k}</span>
      {v}
    </span>
  )
}

export default async function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const supabase = await createClient()

  const { data: report } = await supabase.from('reports').select('*').eq('id', id).maybeSingle()
  if (!report) notFound()

  const { data: firm } = await supabase
    .from('firms').select('name, caution_threshold, action_threshold').single()

  const { data: readings } = await supabase
    .from('readings').select('recorded_at, pci').eq('report_id', id).order('recorded_at')

  const { data: signed } = report.pdf_path
    ? await supabase.storage.from('generated-reports').createSignedUrl(report.pdf_path, 3600)
    : { data: null }

  const caution = Number(firm?.caution_threshold ?? 2.6)
  const action = Number(firm?.action_threshold ?? 4.0)
  const rows = (readings ?? []).map((r) => ({ recorded_at: r.recorded_at, pci: Number(r.pci) }))
  const hi = rows.length ? Math.max(...rows.map((r) => r.pci)) : 0
  const lo = rows.length ? Math.min(...rows.map((r) => r.pci)) : 0

  return (
    <main className="relative min-h-screen overflow-hidden" style={{ background: 'var(--base)' }}>
      <Backdrop />
      <div className="relative z-10">
        <Header firmName={firm?.name} />

        <div className="mx-auto max-w-5xl px-6 py-10 sm:px-10 sm:py-12">
          <Link href="/reports" className="text-[11px] font-bold uppercase tracking-[0.14em]" style={{ color: 'var(--dim)' }}>
            ← Reports
          </Link>

          <div className="rd-rise mt-6">
            <span className="rd-badge">
              ◆ {report.status === 'complete' ? 'Complete' : report.status} · {report.duration_hr ?? '—'}-hour test
            </span>
            <div className="mt-5 flex gap-5">
              <div className="rd-bar" />
              <div>
                <h1 className="rd-h1">{report.property_address}</h1>
                <p className="mt-2 text-[11px] font-bold uppercase tracking-[0.13em]" style={{ color: 'var(--dim)' }}>
                  {[report.property_city, report.property_state, report.property_zip].filter(Boolean).join(', ')}
                  {report.report_number ? ` · Report ${report.report_number}` : ''}
                </p>
              </div>
            </div>
          </div>

          <div className="rd-rise mt-9 flex flex-wrap items-end gap-x-8 gap-y-5" style={{ animationDelay: '.08s' }}>
            <div className="flex items-start gap-3">
              <HeroNumber value={Number(report.average_pci ?? 0)} />
              <span className="mt-3 text-[11px] font-bold uppercase leading-[1.7] tracking-[0.16em]" style={{ color: 'var(--dim)' }}>
                pCi/L<br />average
              </span>
            </div>
            <div className="ml-auto text-right">
              <OutcomePill outcome={report.outcome} />
              <p className="rd-num mt-3 text-[12px] tracking-[0.06em]" style={{ color: 'var(--dim)' }}>
                PEAK {hi.toFixed(1)} · LOW {lo.toFixed(1)} · ACTION {action}
              </p>
            </div>
          </div>

          <div className="rd-rise mt-7 flex flex-wrap gap-2.5" style={{ animationDelay: '.14s' }}>
            <Chip k="Client" v={report.client_name} />
            <Chip k="Location" v={report.room} />
            <Chip k="Monitor" v={[report.monitor_model, report.monitor_serial].filter(Boolean).join(' · ') || null} />
            <Chip k="Duration" v={report.duration_hr ? `${report.duration_hr} hours` : null} />
          </div>

          {report.weather_included === false && (
            <p className="mt-5 rounded-xl px-4 py-3 text-sm"
              style={{ background: 'rgba(250,178,25,.09)', border: '1px solid rgba(250,178,25,.3)', color: '#f7d491' }}>
              ▲ Outdoor weather was unavailable when this ran, so that page is blank. Everything else is complete.
            </p>
          )}

          {rows.length > 0 && (
            <section className="rd-panel rd-rise mt-7 p-6 pb-3" style={{ animationDelay: '.2s' }}>
              <h2 className="rd-eyebrow" style={{ color: '#fff' }}>Concentration · {rows.length} hours</h2>
              <div className="mt-3">
                <Trace readings={rows} caution={caution} action={action} />
              </div>
            </section>
          )}

          <section className="rd-panel rd-rise mt-5 p-6" style={{ animationDelay: '.26s' }}>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <h2 className="rd-eyebrow" style={{ color: '#fff' }}>The report</h2>
              {signed?.signedUrl && (
                <a href={signed.signedUrl} download className="rd-btn">↓ Download PDF</a>
              )}
            </div>
            {signed?.signedUrl ? (
              <object data={signed.signedUrl} type="application/pdf"
                className="mt-5 h-[760px] w-full rounded-xl"
                style={{ border: '1px solid var(--edge)', background: '#0a0d14' }}>
                <p className="p-6 text-sm" style={{ color: 'var(--body)' }}>
                  Your browser will not show the PDF here.{' '}
                  <a className="underline" style={{ color: 'var(--accent)' }} href={signed.signedUrl}>
                    Open it in a new tab
                  </a>.
                </p>
              </object>
            ) : (
              <p className="mt-5 text-sm" style={{ color: 'var(--dim)' }}>No PDF stored for this report.</p>
            )}
          </section>

          {rows.length > 0 && (
            <section className="rd-panel rd-rise mt-5 p-6" style={{ animationDelay: '.32s' }}>
              <div className="flex items-baseline justify-between">
                <h2 className="rd-eyebrow" style={{ color: '#fff' }}>Hourly readings</h2>
                <span className="rd-eyebrow">The numbers the PDF was built from</span>
              </div>
              <div className="mt-4 max-h-[420px] overflow-y-auto">
                <table className="w-full text-[13px]">
                  <tbody>
                    {rows.map((r, i) => {
                      const over = r.pci >= action, warn = !over && r.pci >= caution
                      return (
                        <tr key={i} style={{ borderBottom: '1px solid var(--hair)' }}>
                          <td className="py-2.5" style={{ color: 'var(--body)' }}>
                            {new Date(r.recorded_at).toLocaleString([], {
                              month: 'numeric', day: 'numeric', hour: 'numeric', minute: '2-digit',
                            })}
                          </td>
                          <td className="rd-num py-2.5 text-right font-bold"
                            style={{ color: over ? outcomeColor('fail') : warn ? outcomeColor('caution') : '#fff' }}>
                            {r.pci.toFixed(1)}
                            {(over || warn) && (
                              <span className="ml-2 text-[10px] font-extrabold uppercase tracking-[0.12em]">
                                {over ? 'Fail' : 'Caution'}
                              </span>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </div>
      </div>
    </main>
  )
}
