import { type NextRequest } from 'next/server'
import { updateSession } from '@/lib/supabase/middleware'

export async function proxy(request: NextRequest) {
  return await updateSession(request)
}

export const config = {
  matcher: [
    // Everything except static files, images, and the Python generator.
    // pygen is called server-to-server with no cookies — sending it to
    // the login page here would break every report.
    // api/warm is called by signed-out visitors on the sign-in page. Leaving it
    // in here sent it to the login page instead, so the generator never woke.
    '/((?!_next/static|_next/image|favicon.ico|pygen|api/warm|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
