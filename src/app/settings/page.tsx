import { createClient } from '@/lib/supabase/server'
import { Backdrop, Header } from '@/components/shell'
import { FirmForm, LogoForm, PeopleEditor } from './settings-forms'

export default async function SettingsPage() {
  const supabase = await createClient()

  const { data: firm } = await supabase
    .from('firms')
    .select('name, website, phone, caution_threshold, action_threshold, logo_path')
    .single()

  const { data: people } = await supabase
    .from('people')
    .select('id, full_name, license_number, role')
    .order('sort_order')

  const { data: signedLogo } = firm?.logo_path
    ? await supabase.storage.from('raw-uploads').createSignedUrl(firm.logo_path, 3600)
    : { data: null }

  return (
    <main className="relative min-h-screen overflow-hidden" style={{ background: 'var(--base)' }}>
      <Backdrop />
      <div className="relative z-10">
        <Header firmName={firm?.name} />

        <div className="mx-auto max-w-3xl px-6 py-12 sm:px-10">
          <div className="rd-rise flex gap-5">
            <div className="rd-bar" />
            <div>
              <h1 className="rd-h1">Settings</h1>
              <p className="mt-3 text-sm leading-relaxed" style={{ color: 'var(--body)' }}>
                Everything here prints on the reports this firm generates.
              </p>
            </div>
          </div>

          <div className="rd-rise mt-8 space-y-5" style={{ animationDelay: '.1s' }}>
            {firm && (
              <FirmForm
                firm={{
                  name: firm.name,
                  website: firm.website,
                  phone: firm.phone,
                  caution_threshold: Number(firm.caution_threshold),
                  action_threshold: Number(firm.action_threshold),
                }}
              />
            )}
            <LogoForm logoUrl={signedLogo?.signedUrl ?? null} />
            <PeopleEditor people={people ?? []} />
          </div>
        </div>
      </div>
    </main>
  )
}
