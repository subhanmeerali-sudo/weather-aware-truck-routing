import { useEffect } from 'react'
import { prettyDateTime } from '../lib/timeStuff.js'

const KINDS = [
  { id: 'risk', label: 'Overall risk' },
  { id: 'wind', label: 'Wind' },
  { id: 'rain', label: 'Rain' },
  { id: 'snow', label: 'Snow' },
]

// the 0-48 hour slider that moves the heatmap thru time. it can also play like a movie
export default function HeatControls({ heatmap, heatStatus, hour, setHour, kind, setKind, isOn, setIsOn, isPlaying, setIsPlaying }) {
  const maxHour = heatmap.hours[heatmap.hours.length - 1]

  // when playing, bump the hour forward every little bit. goes back to 0 at the end
  useEffect(() => {
    if (!isPlaying) return undefined
    const timer = setInterval(() => setHour((h) => (h >= maxHour ? 0 : h + 1)), 450)
    return () => clearInterval(timer)
  }, [isPlaying, maxHour, setHour])

  return (
    <div className="heat-controls">
      <div className="heat-controls__row">
        <button
          className="play-btn"
          onClick={() => setIsPlaying(!isPlaying)}
          aria-label={isPlaying ? 'Pause forecast' : 'Play forecast'}
        >
          {isPlaying ? '❚❚' : '▶'}
        </button>
        <div className="heat-controls__time">
          <b>+{hour}h</b> <span>{prettyDateTime(heatmap.times[hour])}</span>
        </div>
        <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Heatmap layer">
          {KINDS.map((k) => (
            <option key={k.id} value={k.id}>
              {k.label}
            </option>
          ))}
        </select>
        <label className="toggle">
          <input type="checkbox" checked={isOn} onChange={(e) => setIsOn(e.target.checked)} />
          Heatmap
        </label>
      </div>
      <input
        className="heat-slider"
        type="range"
        min={0}
        max={maxHour}
        step={1}
        value={hour}
        onChange={(e) => {
          setIsPlaying(false)
          setHour(Number(e.target.value))
        }}
        aria-label="Forecast hour after departure"
      />
      <div className="heat-controls__ticks">
        <span>Departure</span>
        <span>+12h</span>
        <span>+24h</span>
        <span>+36h</span>
        <span>+48h</span>
      </div>
      {heatStatus === 'loading' && (
        <p className="heat-controls__hint heat-controls__loading">
          <span className="spinner" /> Loading corridor forecast…
        </p>
      )}
      {heatStatus === 'oops' && (
        <p className="heat-controls__hint">Couldn&apos;t load the corridor forecast right now (routes + checkpoints still work).</p>
      )}
      {heatStatus !== 'loading' && heatStatus !== 'oops' && (
        <p className="heat-controls__hint">Corridor forecast at departure + {hour}h. 🚚 = where each truck would be.</p>
      )}
    </div>
  )
}
