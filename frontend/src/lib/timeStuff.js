// makes times look nice for humans (in whatever timezone the browser is in)

const shortTime = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
})

const longTime = new Intl.DateTimeFormat(undefined, {
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
})

const clockOnly = new Intl.DateTimeFormat(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })

// short version without the timezone, for tight spots like the table
export function prettyClock(iso) {
  return iso ? clockOnly.format(new Date(iso)) : '—'
}

// like "EST" or "GMT+5" so we can say it once in a header
export function myTimezoneName() {
  const part = new Intl.DateTimeFormat(undefined, { timeZoneName: 'short' })
    .formatToParts(new Date())
    .find((p) => p.type === 'timeZoneName')
  return part ? part.value : 'local'
}

export function prettyTime(iso) {
  return iso ? shortTime.format(new Date(iso)) : '—'
}

export function prettyDateTime(iso) {
  return iso ? longTime.format(new Date(iso)) : '—'
}

// 3.5 hours -> "3h 30m"
export function prettyHowLong(hours) {
  const totalMin = Math.round(hours * 60)
  const h = Math.floor(totalMin / 60)
  const m = totalMin % 60
  return h ? `${h}h ${String(m).padStart(2, '0')}m` : `${m}m`
}

// the datetime-local input wants "2026-10-19T14:00" in LOCAL time, not UTC (annoying)
export function nextHourForInput() {
  const d = new Date()
  d.setMinutes(0, 0, 0)
  d.setHours(d.getHours() + 1)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
