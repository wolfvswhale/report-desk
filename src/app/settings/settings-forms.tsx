'use client'

import { useState, useTransition } from 'react'
import {
  addPerson,
  clearLogo,
  removePerson,
  saveFirm,
  uploadLogo,
} from './actions'

type Firm = {
  name: string
  website: string | null
  phone: string | null
  caution_threshold: number
  action_threshold: number
}

type Person = {
  id: string
  full_name: string
  license_number: string | null
  role: string | null
}

function Note({ text, bad }: { text: string; bad?: boolean }) {
  if (!text) return null
  return (
    <p
      className="mt-4 rounded-lg px-3 py-2 text-sm"
      style={
        bad
          ? { background: 'rgba(208,59,59,.12)', color: '#ff9a9a' }
          : { background: 'rgba(12,163,12,.12)', color: '#7ee87e' }
      }
    >
      {bad ? '▲ ' : '● '}{text}
    </p>
  )
}

const input = 'rd-input mt-2'
const label = 'rd-label'
const card = 'rd-panel p-6'
const btn = 'rd-btn mt-5'
const btnGhost = 'rd-btn-ghost'

export function FirmForm({ firm }: { firm: Firm }) {
  const [pending, start] = useTransition()
  const [note, setNote] = useState('')
  const [bad, setBad] = useState(false)

  return (
    <form
      className={card}
      action={(fd) =>
        start(async () => {
          const res = await saveFirm(fd)
          setBad(!!res.error)
          setNote(res.error ?? 'Saved.')
        })
      }
    >
      <h2 className="rd-eyebrow" style={{color:"#fff"}}>The firm</h2>
      <p className="mt-2 text-[13px]" style={{color:"var(--dim)"}}>
        Name, contact details and the levels that decide pass, caution and fail.
      </p>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className={label}>
          Firm name
          <input name="name" defaultValue={firm.name} required className={input} />
        </label>
        <label className={label}>
          Phone
          <input
            name="phone"
            defaultValue={firm.phone ?? ''}
            placeholder="(804) 555-0142"
            className={input}
          />
        </label>
        <label className={label}>
          Website
          <input
            name="website"
            defaultValue={firm.website ?? ''}
            placeholder="yourfirm.com"
            className={input}
          />
        </label>
        <div />
        <label className={label}>
          Caution at (pCi/L)
          <input
            name="caution_threshold"
            type="number"
            step="0.1"
            min="0.1"
            defaultValue={firm.caution_threshold}
            className={input}
          />
        </label>
        <label className={label}>
          Action at (pCi/L)
          <input
            name="action_threshold"
            type="number"
            step="0.1"
            min="0.1"
            defaultValue={firm.action_threshold}
            className={input}
          />
        </label>
      </div>

      <button
        disabled={pending}
        className={btn}
      >
        {pending ? 'Saving…' : 'Save'}
      </button>
      <Note text={note} bad={bad} />
    </form>
  )
}

export function LogoForm({ logoUrl }: { logoUrl: string | null }) {
  const [pending, start] = useTransition()
  const [note, setNote] = useState('')
  const [bad, setBad] = useState(false)

  return (
    <div className={card}>
      <h2 className="rd-eyebrow" style={{color:"#fff"}}>Logo</h2>
      <p className="mt-2 text-[13px]" style={{color:"var(--dim)"}}>
        Prints on the report cover. With no logo set, that space is left blank —
        no stand-in, and nobody else&apos;s mark.
      </p>

      {logoUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={logoUrl}
          alt="Current logo"
          className="mt-5 h-24 w-auto rounded-xl object-contain p-2" style={{border:"1px solid var(--edge)",background:"rgba(255,255,255,.04)"}}
        />
      )}

      <form
        className="mt-4 flex flex-wrap items-center gap-3"
        action={(fd) =>
          start(async () => {
            const res = await uploadLogo(fd)
            setBad(!!res.error)
            setNote(res.error ?? 'Logo updated.')
          })
        }
      >
        <input
          type="file"
          name="logo"
          accept="image/*"
          className="text-[13px] file:mr-3 file:rounded-full file:border-0 file:px-4 file:py-2 file:text-[13px] file:font-extrabold" style={{color:"var(--dim)"}}
        />
        <button
          disabled={pending}
          className={btnGhost}
        >
          {pending ? 'Uploading…' : 'Upload'}
        </button>
        {logoUrl && (
          <button
            type="button"
            onClick={() =>
              start(async () => {
                const res = await clearLogo()
                setBad(!!res.error)
                setNote(res.error ?? 'Logo removed.')
              })
            }
            className="text-[13px] underline underline-offset-4" style={{color:"var(--dim)"}}
          >
            Remove
          </button>
        )}
      </form>
      <Note text={note} bad={bad} />
    </div>
  )
}

export function PeopleEditor({ people }: { people: Person[] }) {
  const [pending, start] = useTransition()
  const [note, setNote] = useState('')
  const [bad, setBad] = useState(false)

  return (
    <div className={card}>
      <h2 className="rd-eyebrow" style={{color:"#fff"}}>
        Certified people
      </h2>
      <p className="mt-2 text-[13px]" style={{color:"var(--dim)"}}>
        These names and licence numbers print in the signature block of every
        report. The cover has room for two.
      </p>

      <div className="mt-5">
        {people.length === 0 && (
          <p className="py-3 text-sm" style={{color:"var(--dim)"}}>
            Nobody added yet. Reports will print without a signature block.
          </p>
        )}
        {people.map((p) => (
          <div key={p.id} className="flex items-center justify-between py-3" style={{borderTop:"1px solid var(--hair)"}}>
            <div>
              <p className="text-[15px] font-bold text-white">{p.full_name}</p>
              <p className="mt-1 text-[11px] font-bold uppercase tracking-[0.12em]" style={{color:"var(--dim)"}}>
                {[p.license_number, p.role].filter(Boolean).join(' · ') ||
                  'No licence number'}
              </p>
            </div>
            <button
              disabled={pending}
              onClick={() =>
                start(async () => {
                  const res = await removePerson(p.id)
                  setBad(!!res.error)
                  setNote(res.error ?? 'Removed.')
                })
              }
              className="text-[12px] font-bold uppercase tracking-[0.12em] disabled:opacity-40" style={{color:"var(--dim)"}}
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      {people.length < 2 && (
        <form
          className="mt-5 grid gap-4 pt-5 sm:grid-cols-3" style={{borderTop:"1px solid var(--hair)"}}
          action={(fd) =>
            start(async () => {
              const res = await addPerson(fd)
              setBad(!!res.error)
              setNote(res.error ?? 'Added.')
            })
          }
        >
          <label className={label}>
            Name
            <input name="full_name" required className={input} />
          </label>
          <label className={label}>
            Licence number
            <input name="license_number" placeholder="RMS #..." className={input} />
          </label>
          <label className={label}>
            Role
            <input
              name="role"
              placeholder="Measurement Specialist"
              className={input}
            />
          </label>
          <div className="sm:col-span-3">
            <button
              disabled={pending}
              className={btnGhost}
            >
              {pending ? 'Adding…' : 'Add person'}
            </button>
          </div>
        </form>
      )}

      <Note text={note} bad={bad} />
    </div>
  )
}
