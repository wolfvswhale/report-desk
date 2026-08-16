import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

// Supabase client for code that runs on the server.
// Reads and writes the login cookie so a signed-in user stays signed in.
export async function createClient() {
  const cookieStore = await cookies()

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            )
          } catch {
            // Called from a Server Component. Safe to ignore when
            // middleware is refreshing the session.
          }
        },
      },
    }
  )
}
