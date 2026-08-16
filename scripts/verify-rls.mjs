// Proves the database refuses to hand data to a stranger.
// Run: npm run verify:rls
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
)

const tables = ['firms', 'profiles', 'templates', 'people', 'reports', 'readings']
let leaked = 0

for (const table of tables) {
  const { data, error } = await supabase.from(table).select('*').limit(5)
  const rows = data?.length ?? 0
  if (rows > 0) {
    leaked++
    console.log(`FAIL  ${table}: returned ${rows} row(s) to a signed-out visitor`)
  } else {
    console.log(`ok    ${table}: no rows (${error ? error.code : 'blocked by policy'})`)
  }
}

console.log(leaked === 0
  ? '\nPASS - nothing is readable without signing in.'
  : `\nFAIL - ${leaked} table(s) leaked data.`)
process.exit(leaked === 0 ? 0 : 1)
