import Link from 'next/link'
import { createClient } from '@/lib/supabase/server'
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
    ? await supabase.storage
        .from('raw-uploads')
        .createSignedUrl(firm.logo_path, 60 * 60)
    : { data: null }

  return (
    <main className="min-h-screen bg-stone-50">
      <div className="mx-auto max-w-3xl px-6 py-8">
        <Link href="/reports" className="text-sm text-stone-500 hover:text-stone-900">
          ← Reports
        </Link>

        <h1 className="mt-4 text-xl font-semibold text-stone-900">Settings</h1>
        <p className="mt-1 text-sm text-stone-500">
          Everything here prints on the reports this firm generates.
        </p>

        <div className="mt-6 space-y-5">
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
    </main>
  )
}
