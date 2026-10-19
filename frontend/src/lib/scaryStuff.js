// colors + helpers for the scary levels. green = chill, black = do NOT go

export const SCARY_LEVELS = ['Low', 'Moderate', 'High', 'Severe', 'No Travel']

export const SCARY_COLORS = {
  Low: '#22a55a',
  Moderate: '#f2c418',
  High: '#f5841f',
  Severe: '#e0262f',
  'No Travel': '#111111',
}

// each road gets its own color so you can tell them apart (not the same as risk colors!)
export const ROAD_COLORS = { a: '#008080', b: '#5b5bd6', c: '#2b8fd6' }

export function colorForScaryLevel(level) {
  return SCARY_COLORS[level] || '#888'
}

export function colorForRoad(id) {
  return ROAD_COLORS[id] || '#555'
}

// the same rules as the backend, but only for coloring the heatmap layers for wind/rain/snow.
// (the backend is still the boss for the real risk numbers)
export function howScaryIsWind(mph, loadLbs) {
  if (mph >= 55) return 5
  if (mph >= 45) return loadLbs > 30000 ? 5 : 4
  if (mph >= 35) return loadLbs > 40000 ? 4 : 3
  if (mph >= 25) return 2
  return 1
}

export function howScaryIsRain(inPerHr) {
  if (inPerHr > 1) return 5
  if (inPerHr >= 0.5) return 4
  if (inPerHr >= 0.25) return 3
  if (inPerHr >= 0.1) return 2
  return 1
}

export function howScaryIsSnow(inPerHr) {
  if (inPerHr > 3) return 5
  if (inPerHr >= 2) return 4
  if (inPerHr >= 1) return 3
  if (inPerHr >= 0.5) return 2
  return 1
}

// turns hex like #ff8800 into [255, 136, 0] cuz canvas gradients want rgba
export function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255]
}
