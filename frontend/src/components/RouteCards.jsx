import { colorForRoad, colorForScaryLevel, SCARY_LEVELS } from '../lib/scaryStuff.js'
import { prettyClock, prettyHowLong } from '../lib/timeStuff.js'

// a skinny bar that shows how many miles are green/yellow/orange/red/black
function ScaryMilesBar({ milesByLevel, totalMiles }) {
  return (
    <div className="risk-bar" title="Miles by risk level">
      {SCARY_LEVELS.map((level) => {
        const miles = milesByLevel[level] || 0
        if (!miles) return null
        return (
          <span
            key={level}
            style={{ width: `${(miles / totalMiles) * 100}%`, background: colorForScaryLevel(level) }}
            title={`${level}: ${miles.toFixed(0)} mi`}
          />
        )
      })}
    </div>
  )
}

function ScaryChip({ level }) {
  return (
    <span className="chip" style={{ background: colorForScaryLevel(level), color: level === 'Moderate' ? '#111' : '#fff' }}>
      {level}
    </span>
  )
}

// one card per road with all the important numbers
function RouteCard({ route, isPicked, onPick }) {
  const s = route.summary
  const totalMiles = Object.values(s.miles_by_level).reduce((a, b) => a + b, 0) || 1
  return (
    <button
      className={`route-card ${isPicked ? 'is-picked' : ''} ${route.recommended ? 'is-best' : ''}`}
      style={{ '--road-color': colorForRoad(route.id) }}
      onClick={() => onPick(route.id)}
    >
      <div className="route-card__top">
        <span className="route-card__swatch" />
        <strong>{route.label}</strong>
        {route.recommended && <span className="best-badge">★ Best pick</span>}
        <span className="route-card__rank">#{route.rank}</span>
      </div>
      <div className="route-card__stats">
        <div>
          <small>Distance</small>
          <b>{route.distance_miles.toFixed(0)} mi</b>
        </div>
        <div>
          <small>Drive time</small>
          <b>{prettyHowLong(route.duration_hours)}</b>
        </div>
        <div>
          <small>Arrives</small>
          <b title={route.arrival}>{prettyClock(route.arrival)}</b>
        </div>
      </div>
      <ScaryMilesBar milesByLevel={s.miles_by_level} totalMiles={totalMiles} />
      <div className="route-card__risk">
        <span>
          Severe+ <b>{s.severe_miles.toFixed(0)} mi</b>
        </span>
        <span>
          High <b>{s.high_miles.toFixed(0)} mi</b>
        </span>
        <span>
          Avg <b>{s.avg_risk.toFixed(2)}</b>
        </span>
        <ScaryChip level={s.worst_level} />
      </div>
    </button>
  )
}

export default function RouteCards({ plan, pickedRouteId, onPickRoute }) {
  const best = plan.routes.find((r) => r.id === plan.recommendation.route_id)
  return (
    <section className="results">
      <div className="recommendation" style={{ '--road-color': colorForRoad(best.id) }}>
        <div className="recommendation__label">Our Recomendation</div>
        <div className="recommendation__route">{best.label}</div>
        <p>{plan.recommendation.reason}</p>
      </div>
      {plan.warnings.map((w) => (
        <div className="warning" key={w}>
          ⚠ {w}
        </div>
      ))}
      <div className="route-list">
        {plan.routes.map((route) => (
          <RouteCard key={route.id} route={route} isPicked={route.id === pickedRouteId} onPick={onPickRoute} />
        ))}
      </div>
    </section>
  )
}

export { ScaryChip }
