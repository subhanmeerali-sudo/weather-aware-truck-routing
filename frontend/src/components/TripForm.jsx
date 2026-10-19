import { useState } from 'react'
import { nextHourForInput } from '../lib/timeStuff.js'

const EXAMPLE_TRIPS = [
  { origin: 'Denver, CO', destination: 'Salt Lake City, UT' },
  { origin: 'Chicago, IL', destination: 'Minneapolis, MN' },
  { origin: 'Dallas, TX', destination: 'Atlanta, GA' },
]

// the box where the driver types where theyre going
export default function TripForm({ isLoading, onPlan }) {
  const [origin, setOrigin] = useState('Denver, CO')
  const [destination, setDestination] = useState('Salt Lake City, UT')
  const [departure, setDeparture] = useState(nextHourForInput)
  const [loadLbs, setLoadLbs] = useState(35000)
  const [sampleMiles, setSampleMiles] = useState(25)

  // when you hit the button we send everything up to the parent
  function sendTheTrip(e) {
    e.preventDefault()
    onPlan({
      origin: origin.trim(),
      destination: destination.trim(),
      departureIso: new Date(departure).toISOString(), // local time -> UTC so the server knows exactly when
      loadLbs,
      sampleMiles,
    })
  }

  // flips origin and destination, for the trip home
  function swapThePlaces() {
    setOrigin(destination)
    setDestination(origin)
  }

  return (
    <form className="trip-form" onSubmit={sendTheTrip}>
      <div className="field-pair">
        <label className="field">
          <span>Origin</span>
          <input value={origin} onChange={(e) => setOrigin(e.target.value)} placeholder="City, state or lat, lon" required />
        </label>
        <button type="button" className="swap-btn" onClick={swapThePlaces} title="Swap origin and destination">
          ⇅
        </button>
        <label className="field">
          <span>Destination</span>
          <input value={destination} onChange={(e) => setDestination(e.target.value)} placeholder="City, state or lat, lon" required />
        </label>
      </div>

      <div className="field-row">
        <label className="field">
          <span>Departure</span>
          <input type="datetime-local" value={departure} onChange={(e) => setDeparture(e.target.value)} required />
        </label>
        <label className="field field--small">
          <span>Load (lb)</span>
          <input
            type="number"
            min="0"
            max="200000"
            step="500"
            value={loadLbs}
            onChange={(e) => setLoadLbs(e.target.value)}
            required
          />
        </label>
      </div>

      <div className="field">
        <span>Check the weather every</span>
        <div className="segmented" role="radiogroup">
          {[10, 25, 50].map((miles) => (
            <button
              type="button"
              key={miles}
              role="radio"
              aria-checked={sampleMiles === miles}
              className={sampleMiles === miles ? 'is-on' : ''}
              onClick={() => setSampleMiles(miles)}
            >
              {miles} mi
            </button>
          ))}
        </div>
      </div>

      <button className="plan-btn" type="submit" disabled={isLoading}>
        {isLoading ? <span className="spinner" /> : null}
        {isLoading ? 'Finding roads…' : 'Plan my trip'}
      </button>

      <div className="examples">
        <span>Try:</span>
        {EXAMPLE_TRIPS.map((trip) => (
          <button
            type="button"
            key={trip.origin}
            onClick={() => {
              setOrigin(trip.origin)
              setDestination(trip.destination)
            }}
          >
            {trip.origin.split(',')[0]} → {trip.destination.split(',')[0]}
          </button>
        ))}
      </div>
    </form>
  )
}
