// talks to the django backend. thats it, thats the whole file

const API_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

// sends the trip stuff to the server and waits for the 3 roads to come back
export async function askServerForTrip({ origin, destination, departureIso, loadLbs, sampleMiles }) {
  let response
  try {
    response = await fetch(`${API_BASE}/api/plan-trip/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        origin,
        destination,
        departure_iso: departureIso,
        load_lbs: Number(loadLbs),
        sample_miles: Number(sampleMiles),
      }),
    })
  } catch {
    throw new Error("Can't reach the server. Is the backend running?")
  }

  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(makeErrorReadable(data) || `Server error (${response.status})`)
  }
  return data
}

// django REST errors come in a few shapes, this squishes them into one sentence
function makeErrorReadable(data) {
  if (!data || typeof data !== 'object') return null
  if (data.detail) return data.detail
  return Object.entries(data)
    .map(([field, problems]) => `${field}: ${[].concat(problems).join(' ')}`)
    .join(' · ')
}
