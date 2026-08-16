'use server'

import { revalidatePath } from 'next/cache'
import { createClient } from '@/lib/supabase/server'

async function firmId() {
  const supabase = await createClient()
  const {
    data: { user },
  } = await supabase.auth.getUser()
  if (!user) return { supabase, id: null as string | null }
  const { data } = await supabase
    .from('profiles')
    .select('firm_id')
    .eq('id', user.id)
    .single()
  return { supabase, id: data?.firm_id ?? null }
}

export async function saveFirm(form: FormData) {
  const { supabase, id } = await firmId()
  if (!id) return { error: 'not signed in' }

  const caution = Number(form.get('caution_threshold'))
  const action = Number(form.get('action_threshold'))
  if (!(caution > 0) || !(action > 0) || caution >= action) {
    return { error: 'Caution has to be a positive number below the action level.' }
  }

  const { error } = await supabase
    .from('firms')
    .update({
      name: String(form.get('name') || '').trim(),
      website: String(form.get('website') || '').trim() || null,
      phone: String(form.get('phone') || '').trim() || null,
      caution_threshold: caution,
      action_threshold: action,
    })
    .eq('id', id)

  if (error) return { error: error.message }
  revalidatePath('/settings')
  revalidatePath('/reports')
  return { ok: true }
}

export async function uploadLogo(form: FormData) {
  const { supabase, id } = await firmId()
  if (!id) return { error: 'not signed in' }

  const file = form.get('logo')
  if (!(file instanceof File) || file.size === 0) {
    return { error: 'pick an image first' }
  }
  if (file.size > 4 * 1024 * 1024) {
    return { error: 'that image is over 4 MB — shrink it first' }
  }

  const ext = (file.name.split('.').pop() || 'png').toLowerCase()
  const path = `${id}/logo-${Date.now()}.${ext}`

  const { error: uploadError } = await supabase.storage
    .from('raw-uploads')
    .upload(path, file, { contentType: file.type || 'image/png' })
  if (uploadError) return { error: uploadError.message }

  const { data: firm } = await supabase
    .from('firms')
    .select('logo_path')
    .eq('id', id)
    .single()

  const { error } = await supabase
    .from('firms')
    .update({ logo_path: path })
    .eq('id', id)
  if (error) return { error: error.message }

  // Drop the previous one so old logos do not pile up in storage.
  if (firm?.logo_path) {
    await supabase.storage.from('raw-uploads').remove([firm.logo_path])
  }

  revalidatePath('/settings')
  return { ok: true }
}

export async function clearLogo() {
  const { supabase, id } = await firmId()
  if (!id) return { error: 'not signed in' }

  const { data: firm } = await supabase
    .from('firms')
    .select('logo_path')
    .eq('id', id)
    .single()

  await supabase.from('firms').update({ logo_path: null }).eq('id', id)
  if (firm?.logo_path) {
    await supabase.storage.from('raw-uploads').remove([firm.logo_path])
  }
  revalidatePath('/settings')
  return { ok: true }
}

export async function addPerson(form: FormData) {
  const { supabase, id } = await firmId()
  if (!id) return { error: 'not signed in' }

  const full_name = String(form.get('full_name') || '').trim()
  if (!full_name) return { error: 'a name is required' }

  const { count } = await supabase
    .from('people')
    .select('*', { count: 'exact', head: true })

  if ((count ?? 0) >= 2) {
    return { error: 'The report has room for two names. Remove one first.' }
  }

  const { error } = await supabase.from('people').insert({
    firm_id: id,
    full_name,
    license_number: String(form.get('license_number') || '').trim() || null,
    role: String(form.get('role') || '').trim() || null,
    sort_order: (count ?? 0) + 1,
  })
  if (error) return { error: error.message }
  revalidatePath('/settings')
  return { ok: true }
}

export async function removePerson(personId: string) {
  const { supabase, id } = await firmId()
  if (!id) return { error: 'not signed in' }

  const { error } = await supabase.from('people').delete().eq('id', personId)
  if (error) return { error: error.message }
  revalidatePath('/settings')
  return { ok: true }
}
