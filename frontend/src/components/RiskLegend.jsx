import { colorForScaryLevel, SCARY_LEVELS } from '../lib/scaryStuff.js'

// the little color key so people know green = good and black = nope
export default function RiskLegend() {
  return (
    <div className="legend">
      <strong>Risk</strong>
      {SCARY_LEVELS.map((level) => (
        <div key={level} className="legend__row">
          <span className="legend__dot" style={{ background: colorForScaryLevel(level) }} />
          {level}
        </div>
      ))}
    </div>
  )
}
