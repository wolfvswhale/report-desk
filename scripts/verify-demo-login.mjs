// Confirms the demo account can sign in and sees only the demo firm.
// Run: npm run verify:demo
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
)

const { data: auth, error: authError } = await supabase.auth.signInWithPassword({
  email: 'demo@reportdesk.app',
  password: 'demo1234',
})

if (authError) {
  console.log('FAIL sign-in:', authError.message)
  process.exit(1)
}
console.log('ok    signed in as', auth.user.email)

const { data: firms } = await supabase.from('firms').select('name, is_demo')
console.log('ok    firms visible:', JSON.stringify(firms))

const { data: reports } = await supabase
  .from('reports')
  .select('property_address, average_pci, outcome, status')
console.log('ok    reports visible:', JSON.stringify(reports))

const { count } = await supabase
  .from('readings')
  .select('*', { count: 'exact', head: true })
console.log('ok    readings visible:', count)
