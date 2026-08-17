// Status is fixed and always carries a word. Colour never decides alone —
// red and green are the one pair a colourblind reader cannot separate.
const MAP = {
  pass: { word: 'Pass', glyph: '●', color: 'var(--good)', tint: 'rgba(12,163,12,.10)', edge: 'rgba(12,163,12,.5)' },
  caution: { word: 'Caution', glyph: '▲', color: 'var(--caution)', tint: 'rgba(250,178,25,.08)', edge: 'rgba(250,178,25,.55)' },
  fail: { word: 'Fail', glyph: '■', color: 'var(--fail)', tint: 'rgba(208,59,59,.10)', edge: 'rgba(208,59,59,.55)' },
} as const

export type Outcome = keyof typeof MAP

export function outcomeOf(pci: number, caution: number, action: number): Outcome {
  if (pci >= action) return 'fail'
  if (pci >= caution) return 'caution'
  return 'pass'
}

export function OutcomePill({ outcome, size = 'md' }: { outcome: string | null; size?: 'sm' | 'md' }) {
  const s = MAP[(outcome ?? 'pass') as Outcome] ?? MAP.pass
  const sm = size === 'sm'
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full font-extrabold uppercase"
      style={{
        color: s.color,
        background: s.tint,
        border: `1.5px solid ${s.edge}`,
        padding: sm ? '5px 12px' : '9px 17px',
        fontSize: sm ? 11 : 12,
        letterSpacing: '0.12em',
      }}
    >
      <span aria-hidden>{s.glyph}</span> {s.word}
    </span>
  )
}

export function outcomeColor(outcome: string | null) {
  return (MAP[(outcome ?? 'pass') as Outcome] ?? MAP.pass).color
}
