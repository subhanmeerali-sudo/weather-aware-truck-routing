// picks the best road + counts scary miles.
// same rules as the backend pick_road.py / check_points.py so the answer matches.

import { SCARY_LEVELS, SCARY_POINTS, checkIfScary } from './scaryStuff.js'

const TIE_MILES = 0.5 // half a mile difference is basically a tie
const TIE_RISK = 0.001

// adds up how many miles of the trip are at each scary level.
// "severe miles" counts Severe AND No Travel, cuz No Travel is even worse.
export function countScaryMiles(checkpoints) {
  const byLevel = Object.fromEntries(SCARY_LEVELS.map((l) => [l, 0]))
  let weighted = 0
  let total = 0
  let worst = SCARY_LEVELS[0]
  for (const cp of checkpoints) {
    const level = cp.risk.level
    byLevel[level] += cp.miles_covered
    weighted += SCARY_POINTS[level] * cp.miles_covered
    total += cp.miles_covered
    if (SCARY_POINTS[level] > SCARY_POINTS[worst]) worst = level
  }
  const avg = total ? weighted / total : 1
  return {
    miles_by_level: Object.fromEntries(Object.entries(byLevel).map(([k, v]) => [k, Math.round(v * 10) / 10])),
    severe_miles: Math.round((byLevel.Severe + byLevel['No Travel']) * 10) / 10,
    high_miles: Math.round(byLevel.High * 10) / 10,
    no_travel_miles: Math.round(byLevel['No Travel'] * 10) / 10,
    avg_risk: Math.round(avg * 1000) / 1000,
    worst_level: worst,
    has_no_travel: byLevel['No Travel'] > 0,
    checkpoint_count: checkpoints.length,
  }
}

function whyItWon(winner, runnerUp) {
  const w = winner.summary
  const r = runnerUp.summary
  if (Math.abs(w.severe_miles - r.severe_miles) > TIE_MILES) {
    return `Fewest Severe miles (${w.severe_miles.toFixed(0)} vs ${r.severe_miles.toFixed(0)} on ${runnerUp.label}).`
  }
  if (Math.abs(w.high_miles - r.high_miles) > TIE_MILES) {
    return `Same Severe exposure, but fewer High-risk miles (${w.high_miles.toFixed(0)} vs ${r.high_miles.toFixed(0)}).`
  }
  if (Math.abs(w.avg_risk - r.avg_risk) > TIE_RISK) {
    return `Similar Severe/High exposure, but lower average risk (${w.avg_risk.toFixed(3)} vs ${r.avg_risk.toFixed(3)}).`
  }
  const diffMin = (runnerUp.duration_seconds - winner.duration_seconds) / 60
  return `Weather risk is about the same, so the fastest route wins (saves ${diffMin.toFixed(0)} min).`
}

// we pick the road that is less scary. if theyre all the same scary, pick the fast one.
export function pickBestRoad(roads) {
  const fuzzyKey = (road) => {
    const s = road.summary
    return [
      Math.round(s.severe_miles / TIE_MILES),
      Math.round(s.high_miles / TIE_MILES),
      Math.round(s.avg_risk / TIE_RISK),
      road.duration_seconds,
    ]
  }
  const ranked = [...roads].sort((a, b) => {
    const ka = fuzzyKey(a)
    const kb = fuzzyKey(b)
    for (let i = 0; i < ka.length; i++) {
      if (ka[i] !== kb[i]) return ka[i] - kb[i]
    }
    return 0
  })
  ranked.forEach((road, i) => {
    road.rank = i + 1
    road.recommended = i === 0
  })
  let reason
  if (ranked.length === 1) reason = 'Only one route was available.'
  else reason = whyItWon(ranked[0], ranked[1])
  if (ranked[0].summary.has_no_travel) {
    reason += ' Heads up: even this route has No Travel conditions, consider changing the departure time.'
  }
  return { ranked, reason }
}

// takes a plan from the server (null weather) + a map of "lat,lon" -> weather at ETA,
// fills risk on every checkpoint, recomputes summaries, and picks the real best road.
export function fillInRiskAndPickWinner(plan, weatherBySpot) {
  const loadLbs = plan.load_lbs
  const routes = plan.routes.map((route) => {
    const checkpoints = route.checkpoints.map((cp) => {
      const key = `${cp.lat},${cp.lon}`
      const weather = weatherBySpot.get(key) || {
        wind_mph: 0,
        gust_mph: null,
        rain_in_hr: 0,
        snow_in_hr: 0,
        temp_f: null,
      }
      const risk = checkIfScary(weather, loadLbs)
      return { ...cp, weather, risk }
    })
    const summary = countScaryMiles(checkpoints)
    return { ...route, checkpoints, summary }
  })

  const { ranked, reason } = pickBestRoad(routes)
  // keep routes in a/b/c order for the UI, but with updated rank/recommended from ranked
  const byId = Object.fromEntries(ranked.map((r) => [r.id, r]))
  const ordered = plan.routes.map((r) => byId[r.id])
  const best = ranked[0]

  return {
    ...plan,
    needs_client_weather: false,
    routes: ordered,
    recommendation: { route_id: best.id, label: best.label, reason },
    meta: { ...plan.meta, needs_client_weather: false },
  }
}
