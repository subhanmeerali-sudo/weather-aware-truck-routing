// colors + helpers for the scary levels. green = chill, black = do NOT go
//
// these rules are the SAME as the backend scary_rules.py / the PDF. the browser
// is the boss for risk now (Render's IP got blocked by Open-Meteo).

export const SCARY_LEVELS = ['Low', 'Moderate', 'High', 'Severe', 'No Travel']

export const SCARY_POINTS = { Low: 1, Moderate: 2, High: 3, Severe: 4, 'No Travel': 5 }

export const SCARY_COLORS = {
  Low: '#22a55a',
  Moderate: '#f2c418',
  High: '#f5841f',
  Severe: '#e0262f',
  'No Travel': '#111111',
}

// each road gets its own color so you can tell them apart (not the same as risk colors!)
export const ROAD_COLORS = { a: '#008080', b: '#5b5bd6', c: '#2b8fd6' }

const HEAVY_FOR_NO_TRAVEL_LBS = 30000
const HEAVY_FOR_SEVERE_LBS = 40000

export function colorForScaryLevel(level) {
  return SCARY_COLORS[level] || '#888'
}

export function colorForRoad(id) {
  return ROAD_COLORS[id] || '#555'
}

// this checks if the wind is too strong for the big truck.
// heavy trucks get extra rules cuz the PDF says so (big tall trailers + wind = bad).
// returns [level, reason_or_null]
export function seeHowWindy(windMph, loadLbs) {
  if (windMph >= 55) return ['No Travel', `wind ${Math.round(windMph)} mph is 55+ (no travel for any load)`]
  if (windMph >= 45) {
    if (loadLbs > HEAVY_FOR_NO_TRAVEL_LBS) {
      return ['No Travel', `wind ${Math.round(windMph)} mph with ${Math.round(loadLbs).toLocaleString()} lb load (>30,000 lb)`]
    }
    return ['Severe', `wind ${Math.round(windMph)} mph`]
  }
  if (windMph >= 35) {
    if (loadLbs > HEAVY_FOR_SEVERE_LBS) {
      return ['Severe', `wind ${Math.round(windMph)} mph with ${Math.round(loadLbs).toLocaleString()} lb load (>40,000 lb)`]
    }
    return ['High', `wind ${Math.round(windMph)} mph`]
  }
  if (windMph >= 25) return ['Moderate', `wind ${Math.round(windMph)} mph`]
  return ['Low', null]
}

// this checks how hard its raining (inches per hour)
export function seeHowRainy(rainInHr) {
  if (rainInHr > 1.0) return ['No Travel', `rain ${rainInHr.toFixed(2)} in/hr`]
  if (rainInHr >= 0.5) return ['Severe', `rain ${rainInHr.toFixed(2)} in/hr`]
  if (rainInHr >= 0.25) return ['High', `rain ${rainInHr.toFixed(2)} in/hr`]
  if (rainInHr >= 0.1) return ['Moderate', `rain ${rainInHr.toFixed(2)} in/hr`]
  return ['Low', null]
}

// this checks how much snow is falling (inches per hour). snow is the worst for trucks
export function seeHowSnowy(snowInHr) {
  if (snowInHr > 3.0) return ['No Travel', `snow ${snowInHr.toFixed(1)} in/hr`]
  if (snowInHr >= 2.0) return ['Severe', `snow ${snowInHr.toFixed(1)} in/hr`]
  if (snowInHr >= 1.0) return ['High', `snow ${snowInHr.toFixed(1)} in/hr`]
  if (snowInHr >= 0.5) return ['Moderate', `snow ${snowInHr.toFixed(1)} in/hr`]
  return ['Low', null]
}

// score versions used by the heatmap coloring (1..5)
export function howScaryIsWind(mph, loadLbs) {
  return SCARY_POINTS[seeHowWindy(mph, loadLbs)[0]]
}

export function howScaryIsRain(inPerHr) {
  return SCARY_POINTS[seeHowRainy(inPerHr)[0]]
}

export function howScaryIsSnow(inPerHr) {
  return SCARY_POINTS[seeHowSnowy(inPerHr)[0]]
}

function scariestOne(...levels) {
  return levels.reduce((best, lvl) => (SCARY_POINTS[lvl] > SCARY_POINTS[best] ? lvl : best))
}

// looks at wind + rain + snow at one spot and says how scary it is overall.
// the overall level is just whichever one is the worst (one bad thing is enough to be bad).
export function checkIfScary(weather, loadLbs) {
  const [windLevel, windWhy] = seeHowWindy(weather.wind_mph, loadLbs)
  const [rainLevel, rainWhy] = seeHowRainy(weather.rain_in_hr)
  const [snowLevel, snowWhy] = seeHowSnowy(weather.snow_in_hr)
  const level = scariestOne(windLevel, rainLevel, snowLevel)
  const reasons = [windWhy, rainWhy, snowWhy].filter(Boolean)
  return {
    level,
    score: SCARY_POINTS[level],
    wind_level: windLevel,
    rain_level: rainLevel,
    snow_level: snowLevel,
    reasons,
  }
}

export function quickScaryScore(windMph, rainInHr, snowInHr, loadLbs) {
  return Math.max(howScaryIsWind(windMph, loadLbs), howScaryIsRain(rainInHr), howScaryIsSnow(snowInHr))
}

// turns hex like #ff8800 into [255, 136, 0] cuz canvas gradients want rgba
export function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}
