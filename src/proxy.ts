import { type NextRequest } from 'next/server'
import { updateSession } from '@/lib/supabase/middleware'

export async function proxy(request: NextRequest) {
  return await updateSession(request)
}

export const config = {
  matcher: [
    // Everything except static files, images, and the Python generator.
    // api/generate is called server-to-server with no cookies — sending it to
    // the login page here would break every report.
    '/((?!_next/static|_next/image|favicon.ico|api/generate|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
