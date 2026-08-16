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
      className={`mt-3 rounded-lg px-3 py-2 text-sm ${
        bad ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700'
      }`}
    >
      {text}
    </p>
  )
}

const input =
  'mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-stone-900 outline-none focus:border-stone-900'
const label = 'block text-sm font-medium text-stone-700'
const card = 'rounded-xl border border-stone-200 bg-white p-6'

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
      <h2 className="text-sm font-semibold text-stone-900">The firm</h2>
      <p className="mt-1 text-xs text-stone-500">
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
        className="mt-5 rounded-lg bg-stone-900 px-4 py-2 text-sm font-medium text-white hover:bg-stone-800 disabled:opacity-50"
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
      <h2 className="text-sm font-semibold text-stone-900">Logo</h2>
      <p className="mt-1 text-xs text-stone-500">
        Prints on the report cover. With no logo set, that space is left blank —
        no stand-in, and nobody else&apos;s mark.
      </p>

      {logoUrl && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={logoUrl}
          alt="Current logo"
          className="mt-4 h-24 w-auto rounded-lg border border-stone-200 bg-white object-contain p-2"
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
          className="text-sm text-stone-600 file:mr-3 file:rounded-lg file:border-0 file:bg-stone-900 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white"
        />
        <button
          disabled={pending}
          className="rounded-lg border border-stone-300 px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-50 disabled:opacity-50"
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
            className="text-sm text-stone-500 underline underline-offset-4 hover:text-stone-900"
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
      <h2 className="text-sm font-semibold text-stone-900">
        Certified people
      </h2>
      <p className="mt-1 text-xs text-stone-500">
        These names and licence numbers print in the signature block of every
        report. The cover has room for two.
      </p>

      <div className="mt-4 divide-y divide-stone-100">
        {people.length === 0 && (
          <p className="py-3 text-sm text-stone-500">
            Nobody added yet. Reports will print without a signature block.
          </p>
        )}
        {people.map((p) => (
          <div key={p.id} className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm text-stone-900">{p.full_name}</p>
              <p className="text-xs text-stone-500">
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
              className="text-sm text-stone-500 hover:text-red-700 disabled:opacity-50"
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      {people.length < 2 && (
        <form
          className="mt-4 grid gap-3 border-t border-stone-100 pt-4 sm:grid-cols-3"
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
              className="rounded-lg border border-stone-300 px-4 py-2 text-sm font-medium text-stone-800 hover:bg-stone-50 disabled:opacity-50"
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
