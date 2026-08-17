import { NextResponse } from 'next/server'

// The generator sleeps when nobody has used it for two days. Opening the
// upload page pokes it awake, so it is up by the time anyone presses the
// button. Deliberately fire-and-forget: nothing here should block the page.
export async function POST() {
  const endpoint = process.env.REPORT_SERVICE_URL
  if (!endpoint) return NextResponse.json({ warmed: false, reason: 'same host' })

  const health = endpoint.replace(/\/(api\/)?generate\/?$/, '/health')

  try {
    const res = await fetch(health, {
      method: 'GET',
      signal: AbortSignal.timeout(4000),
      cache: 'no-store',
    })
    return NextResponse.json({ warmed: res.ok, status: res.status })
  } catch {
    // A timeout here usually means it is booting, which is the point.
    return NextResponse.json({ warmed: false, waking: true })
  }
}
