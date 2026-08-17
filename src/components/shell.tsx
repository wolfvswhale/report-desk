import Link from 'next/link'

export function Backdrop() {
  return (
    <>
      <div className="rd-glow" />
      <div className="rd-grid" />
    </>
  )
}

export function Mark({ small }: { small?: boolean }) {
  return (
    <span className="flex items-center gap-[11px]">
      <span
        className="block rounded-[2px]"
        style={{
          width: small ? 8 : 9,
          height: small ? 8 : 9,
          background: 'var(--accent)',
          boxShadow: '0 0 14px var(--accent)',
        }}
      />
      <span
        className="font-extrabold uppercase text-white"
        style={{ fontSize: small ? 12 : 14, letterSpacing: '0.16em' }}
      >
        Report Desk
      </span>
    </span>
  )
}

export function Header({ firmName }: { firmName?: string | null }) {
  return (
    <header
      className="relative z-10 flex flex-wrap items-center justify-between gap-4 px-6 py-5 sm:px-10"
      style={{ borderBottom: '1px solid var(--hair)' }}
    >
      <div>
        <Mark />
        {firmName && (
          <p className="mt-1.5 pl-5 text-[11px] font-bold uppercase tracking-[0.13em]" style={{ color: 'var(--dim)' }}>
            {firmName}
          </p>
        )}
      </div>
      <nav className="flex items-center gap-6 text-[11px] font-bold uppercase tracking-[0.14em]" style={{ color: 'var(--dim)' }}>
        <Link href="/reports" className="text-white">Reports</Link>
        <Link href="/settings" className="hover:text-white">Settings</Link>
        <form action="/auth/signout" method="post">
          <button className="uppercase tracking-[0.14em] hover:text-white">Sign out</button>
        </form>
      </nav>
    </header>
  )
}
