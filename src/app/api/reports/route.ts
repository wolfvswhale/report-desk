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
    .select('caution_threshold, action_threshold')
    .single()

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

  // 1. Hand both files to the Python generator.
  const upstream = new FormData()
  upstream.append('raw_pdf', rawPdf, rawPdf.name || 'raw.pdf')
  upstream.append('house_photo', housePhoto, housePhoto.name || 'photo.jpg')

  let parsed: Parsed
  try {
    const res = await fetch(`${process.env.REPORT_SERVICE_URL}/generate`, {
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

  return NextResponse.json({
    id: report.id,
    report_number: parsed.report_number,
    readings: parsed.readings.length,
  })
}
