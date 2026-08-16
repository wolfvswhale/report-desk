import Link from 'next/link'
import { notFound } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import ReadingsTable from './readings-table'

const OUTCOME_STYLES: Record<string, string> = {
  pass: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  caution: 'bg-amber-50 text-amber-700 ring-amber-200',
  fail: 'bg-red-50 text-red-700 ring-red-200',
}

function Field({ label, value }: { label: string; value: string | null }) {
  if (!value) return null
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-stone-400">{label}</dt>
      <dd className="mt-0.5 text-sm text-stone-800">{value}</dd>
    </div>
  )
}

export default async function ReportPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const supabase = await createClient()

  const { data: report } = await supabase
    .from('reports')
    .select('*')
    .eq('id', id)
    .maybeSingle()

  if (!report) notFound()

  const { data: firm } = await supabase
    .from('firms')
    .select('caution_threshold, action_threshold')
    .single()

  const { data: readings } = await supabase
    .from('readings')
    .select('recorded_at, pci')
    .eq('report_id', id)
    .order('recorded_at')

  const { data: signed } = report.pdf_path
    ? await supabase.storage
        .from('generated-reports')
        .createSignedUrl(report.pdf_path, 60 * 60)
    : { data: null }

  const window_ = `${new Date(report.test_started_at).toLocaleString()} → ${new Date(
    report.test_ended_at
  ).toLocaleString()}`

  return (
    <main className="min-h-screen bg-stone-50">
      <div className="mx-auto max-w-5xl px-6 py-8">
        <Link href="/reports" className="text-sm text-stone-500 hover:text-stone-900">
          ← Reports
        </Link>

        <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-stone-900">
              {report.property_address}
            </h1>
            <p className="mt-0.5 text-sm text-stone-500">
              {[report.property_city, report.property_state, report.property_zip]
                .filter(Boolean)
                .join(', ')}
              {report.report_number ? ` · ${report.report_number}` : ''}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span
              className={`rounded-full px-3 py-1 text-sm font-medium capitalize ring-1 ${
                OUTCOME_STYLES[report.outcome ?? ''] ??
                'bg-stone-100 text-stone-600 ring-stone-200'
              }`}
            >
              {report.average_pci} pCi/L · {report.outcome ?? report.status}
            </span>
            {signed?.signedUrl && (
              <a
                href={signed.signedUrl}
                download
                className="rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800"
              >
                Download PDF
              </a>
            )}
          </div>
        </div>

        <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 rounded-xl border border-stone-200 bg-white p-5 sm:grid-cols-4">
          <Field label="Client" value={report.client_name} />
          <Field label="Monitor location" value={report.room} />
          <Field
            label="Monitor"
            value={
              [report.monitor_model, report.monitor_serial]
                .filter(Boolean)
                .join(' · ') || null
            }
          />
          <Field
            label="Duration"
            value={report.duration_hr ? `${report.duration_hr} hours` : null}
          />
          <div className="col-span-2 sm:col-span-4">
            <dt className="text-xs uppercase tracking-wide text-stone-400">
              Test window
            </dt>
            <dd className="mt-0.5 text-sm text-stone-800">{window_}</dd>
          </div>
        </dl>

        {!report.weather_included && (
          <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Outdoor weather was unavailable when this report was built, so that
            page is empty. Everything else is complete.
          </p>
        )}

        <section className="mt-8">
          <h2 className="text-sm font-semibold text-stone-900">The report</h2>
          {signed?.signedUrl ? (
            <object
              data={signed.signedUrl}
              type="application/pdf"
              className="mt-3 h-[820px] w-full rounded-xl border border-stone-200 bg-white"
            >
              <p className="p-5 text-sm text-stone-500">
                Your browser will not show the PDF here.{' '}
                <a className="underline" href={signed.signedUrl}>
                  Open it in a new tab
                </a>
                .
              </p>
            </object>
          ) : (
            <p className="mt-3 rounded-xl border border-stone-200 bg-white px-5 py-8 text-sm text-stone-500">
              No PDF stored for this report.
            </p>
          )}
        </section>

        <ReadingsTable
          readings={readings ?? []}
          caution={Number(firm?.caution_threshold ?? 2.6)}
          action={Number(firm?.action_threshold ?? 4.0)}
        />
      </div>
    </main>
  )
}
