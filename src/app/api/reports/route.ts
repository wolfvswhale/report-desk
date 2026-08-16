import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

export const maxDuration = 120

type Parsed = {
  report_number: string
  client_name: string | null
  address_line1: string | null
  address_line2: string | null
  zip_code: string | null
  room: string | null
  monitor_serial: string | null
  monitor_model: string | null
  test_started_at: string
  test_ended_at: string
  duration_hr: number | null
  epa_average: number | null
  result: string | null
  weather_included: boolean
  readings: { recorded_at: string; pci: number }[]
  pdf_base64: string
}

// "Richmond, VA 23227" -> city, state, zip
function splitCityLine(line: string | null) {
  if (!line) return { city: null, state: null, zip: null }
  const m = line.match(/^(.*?),\s*([A-Z]{2})\s*(\d{5})?/)
  return {
    city: m?.[1]?.trim() ?? null,
    state: m?.[2] ?? null,
    zip: m?.[3] ?? null,
  }
}

function outcomeFor(avg: number | null, caution: number, action: number) {
  if (avg === null) return null
  if (avg >= action) return 'fail'
  if (avg >= caution) return 'caution'
  return 'pass'
}

export async function POST(request: Request) {
  const supabase = await createClient()

  const {
    data: { user },
  } = await supabase.auth.getUser()
  if (!user) {
    return NextResponse.json({ error: 'not signed in' }, { status: 401 })
  }

  const { data: profile } = await supabase
    .from('profiles')
    .select('firm_id')
    .eq('id', user.id)
    .single()
  if (!profile) {
    return NextResponse.json({ error: 'no firm on this account' }, { status: 403 })
  }

  const { data: firm } = await supabase
    .from('firms')
    .select('name, caution_threshold, action_threshold, website, phone, logo_path, is_demo')
    .single()

  // The demo account is public, so it is also a free compute and storage
  // faucet for anything that finds it. Cap the day and sweep the backlog.
  const DEMO_DAILY_LIMIT = 10
  const DEMO_KEEP = 5

  if (firm?.is_demo) {
    const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()
    const { count } = await supabase
      .from('reports')
      .select('*', { count: 'exact', head: true })
      .not('pdf_path', 'is', null)
      .gte('created_at', since)

    if ((count ?? 0) >= DEMO_DAILY_LIMIT) {
      return NextResponse.json(
        {
          error:
            'The demo has generated its limit for today. It resets in a few hours — or sign in with a real account to keep going.',
        },
        { status: 429 }
      )
    }
  }

  const { data: people } = await supabase
    .from('people')
    .select('full_name, license_number')
    .order('sort_order')

  const { data: template } = await supabase
    .from('templates')
    .select('id')
    .limit(1)
    .single()
  if (!template) {
    return NextResponse.json({ error: 'no report template set up' }, { status: 400 })
  }

  const form = await request.formData()
  const rawPdf = form.get('raw_pdf')
  const housePhoto = form.get('house_photo')
  if (!(rawPdf instanceof File) || !(housePhoto instanceof File)) {
    return NextResponse.json(
      { error: 'send both the monitor PDF and a house photo' },
      { status: 400 }
    )
  }

  // 1. Hand both files to the Python generator, with this firm's branding
  // so nobody else's name, licence number or logo lands on the report.
  const upstream = new FormData()
  upstream.append('raw_pdf', rawPdf, rawPdf.name || 'raw.pdf')
  upstream.append('house_photo', housePhoto, housePhoto.name || 'photo.jpg')
  upstream.append(
    'branding_json',
    JSON.stringify({
      rms_name: people?.[0]?.full_name ?? '',
      rms_license: people?.[0]?.license_number ?? '',
      rms_name_2: people?.[1]?.full_name ?? '',
      rms_license_2: people?.[1]?.license_number ?? '',
      website: firm?.website ?? '',
      company_phone: firm?.phone ?? '',
      // Empty means "draw no logo" rather than falling back to a built-in one.
      logo_path: '',
    })
  )

  if (firm?.logo_path) {
    const { data: logoBlob } = await supabase.storage
      .from('raw-uploads')
      .download(firm.logo_path)
    if (logoBlob) {
      upstream.append('logo', logoBlob, firm.logo_path.split('/').pop() || 'logo.png')
    }
  }

  let parsed: Parsed
  try {
    // Full endpoint URL. Locally that is the uvicorn process; in production it
    // is this same deployment's Python function.
    const endpoint =
      process.env.REPORT_SERVICE_URL ||
      new URL('/api/py/generate', request.url).toString()

    const res = await fetch(endpoint, {
      method: 'POST',
      body: upstream,
      headers: process.env.REPORT_SERVICE_SECRET
        ? { 'x-service-secret': process.env.REPORT_SERVICE_SECRET }
        : undefined,
    })
    if (!res.ok) {
      const detail = await res.text()
      return NextResponse.json(
        { error: `report generator said no: ${detail}` },
        { status: res.status === 422 ? 422 : 502 }
      )
    }
    parsed = (await res.json()) as Parsed
  } catch {
    return NextResponse.json(
      { error: 'could not reach the report generator' },
      { status: 502 }
    )
  }

  // 2. Store all three files under this firm's folder.
  const firmId = profile.firm_id
  const stamp = Date.now()
  const base = `${firmId}/${parsed.report_number}-${stamp}`
  const pdfBytes = Buffer.from(parsed.pdf_base64, 'base64')

  const sourcePath = `${base}-raw.pdf`
  const photoPath = `${base}-house.${(housePhoto.name.split('.').pop() || 'jpg').toLowerCase()}`
  const reportPath = `${base}-report.pdf`

  const uploads = await Promise.all([
    supabase.storage.from('raw-uploads').upload(sourcePath, rawPdf, {
      contentType: 'application/pdf',
    }),
    supabase.storage.from('raw-uploads').upload(photoPath, housePhoto, {
      contentType: housePhoto.type || 'image/jpeg',
    }),
    supabase.storage.from('generated-reports').upload(reportPath, pdfBytes, {
      contentType: 'application/pdf',
    }),
  ])

  const uploadError = uploads.find((u) => u.error)?.error
  if (uploadError) {
    return NextResponse.json(
      { error: `could not store the files: ${uploadError.message}` },
      { status: 500 }
    )
  }

  // 3. Save the report row, then its readings.
  const { city, state, zip } = splitCityLine(parsed.address_line2)
  const outcome = outcomeFor(
    parsed.epa_average,
    Number(firm?.caution_threshold ?? 2.6),
    Number(firm?.action_threshold ?? 4.0)
  )

  const { data: report, error: reportError } = await supabase
    .from('reports')
    .insert({
      firm_id: firmId,
      template_id: template.id,
      created_by: user.id,
      report_number: parsed.report_number,
      client_name: parsed.client_name,
      property_address: parsed.address_line1 || 'Address not found',
      property_city: city,
      property_state: state,
      property_zip: zip || parsed.zip_code,
      room: parsed.room,
      monitor_serial: parsed.monitor_serial,
      monitor_model: parsed.monitor_model,
      test_started_at: parsed.test_started_at,
      test_ended_at: parsed.test_ended_at,
      duration_hr: parsed.duration_hr,
      average_pci: parsed.epa_average,
      outcome,
      status: 'complete',
      source_file_path: sourcePath,
      photo_path: photoPath,
      pdf_path: reportPath,
      weather_included: parsed.weather_included,
    })
    .select('id')
    .single()

  if (reportError || !report) {
    return NextResponse.json(
      { error: `could not save the report: ${reportError?.message}` },
      { status: 500 }
    )
  }

  if (parsed.readings.length) {
    const { error: readingsError } = await supabase.from('readings').insert(
      parsed.readings.map((r) => ({
        report_id: report.id,
        firm_id: firmId,
        monitor_serial: parsed.monitor_serial,
        recorded_at: r.recorded_at,
        pci: r.pci,
      }))
    )
    if (readingsError) {
      return NextResponse.json(
        { error: `saved the report but not the readings: ${readingsError.message}` },
        { status: 500 }
      )
    }
  }

  // Sweep the demo's older runs so the account stays small and legible.
  if (firm?.is_demo) {
    const { data: old } = await supabase
      .from('reports')
      .select('id, source_file_path, photo_path, pdf_path')
      .not('pdf_path', 'is', null)
      .order('created_at', { ascending: false })
      .range(DEMO_KEEP, 100)

    for (const r of old ?? []) {
      await supabase.storage
        .from('raw-uploads')
        .remove([r.source_file_path, r.photo_path].filter(Boolean) as string[])
      await supabase.storage
        .from('generated-reports')
        .remove([r.pdf_path as string])
      await supabase.from('reports').delete().eq('id', r.id)
    }
  }

  return NextResponse.json({
    id: report.id,
    report_number: parsed.report_number,
    readings: parsed.readings.length,
  })
}
