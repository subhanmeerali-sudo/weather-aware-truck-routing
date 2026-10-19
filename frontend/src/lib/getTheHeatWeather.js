import { howScaryIsRain, howScaryIsSnow, howScaryIsWind } from './scaryStuff.js'

/*
  gets the weather for the heatmap dots RIGHT from the browser.

  why? the server lives on Render and shares its internet address with tons of
  other apps, so Open-Meteo kept telling it "too many requests" (429). every
  person's browser has its own address, so asking from here works way better.
  (Open-Meteo allows this, it sends CORS headers.)

  same unit math as the backend get_weather.py:
    wind:  km/h -> mph     (x 0.621371)
    rain:  mm   -> inches  (/ 25.4)   rain + showers = "rain"
    snow:  cm   -> inches  (/ 2.54)   Open-Meteo snowfall is in cm!
*/

const OPEN_METEO_URL = 'https://api.open-meteo.com/v1/forecast'
const KMH_TO_MPH = 0.621371
const MM_TO_INCHES = 1 / 25.4
const CM_TO_INCHES = 1 / 2.54
const SPOTS_PER_ASK = 40 // same small groups as the backend
const NAP_BETWEEN_ASKS = 600 // ms, little break so Open-Meteo stays happy
const WAIT_TIMES_WHEN_TOO_FAST = [2000, 5000, 10000] // ms, gets bigger each time

function takeANap(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// "2026-10-19T14:00" style text that Open-Meteo wants (in GMT)
function makeHourText(date) {
  return date.toISOString().slice(0, 13) + ':00'
}

// chops the time down to the start of the hour
function chopToTheHour(date) {
  const d = new Date(date)
  d.setUTCMinutes(0, 0, 0)
  return d
}

// asks Open-Meteo about one group of spots. if it says "slow down" we wait and try again
async function askOpenMeteoFromBrowser(spots, startHour, endHour) {
  const params = new URLSearchParams({
    latitude: spots.map(([lat]) => lat.toFixed(2)).join(','),
    longitude: spots.map(([, lon]) => lon.toFixed(2)).join(','),
    hourly: 'wind_speed_10m,wind_gusts_10m,rain,showers,snowfall',
    timezone: 'GMT',
    timeformat: 'unixtime',
    start_hour: makeHourText(startHour),
    end_hour: makeHourText(endHour),
    wind_speed_unit: 'kmh',
    precipitation_unit: 'mm',
  })

  let tooFastCount = 0
  let otherFails = 0
  while (true) {
    let response
    try {
      response = await fetch(`${OPEN_METEO_URL}?${params}`)
    } catch (err) {
      otherFails += 1
      if (otherFails >= 2) throw new Error(`Couldn't reach Open-Meteo: ${err.message}`)
      await takeANap(1000)
      continue
    }

    if (response.status === 429) {
      if (tooFastCount >= WAIT_TIMES_WHEN_TOO_FAST.length) {
        throw new Error('Open-Meteo is busy (rate limit). Try again in a minute.')
      }
      let nap = WAIT_TIMES_WHEN_TOO_FAST[tooFastCount]
      const toldUs = Number(response.headers.get('Retry-After'))
      if (toldUs > 0) nap = Math.max(nap, Math.min(toldUs * 1000, 15000)) // dont wait forever tho
      tooFastCount += 1
      await takeANap(nap)
      continue
    }

    const data = await response.json().catch(() => null)
    if (!response.ok || !data || data.error) {
      otherFails += 1
      if (otherFails >= 2) throw new Error(`Open-Meteo said: ${data?.reason || response.status}`)
      await takeANap(1000)
      continue
    }
    return Array.isArray(data) ? data : [data]
  }
}

// turns one spot's hourly stuff into mph + inches per hour (like turn_into_truck_units)
function turnIntoTruckUnits(hourly = {}) {
  const safe = (name) => (hourly[name] || []).map((v) => (v == null ? 0 : Number(v)))
  const rain = safe('rain')
  const showers = safe('showers')
  return {
    times: (hourly.time || []).map(Number),
    wind_mph: safe('wind_speed_10m').map((w) => w * KMH_TO_MPH),
    rain_in_hr: rain.map((r, i) => (r + (showers[i] || 0)) * MM_TO_INCHES),
    snow_in_hr: safe('snowfall').map((s) => s * CM_TO_INCHES),
  }
}

// weather at an exact time by mixing the 2 closest hours (same as weather_at_time on the server)
function weatherAtThisTime(series, whenMs) {
  const { times } = series
  if (!times.length) return { wind_mph: 0, rain_in_hr: 0, snow_in_hr: 0 }
  let pos = (whenMs / 1000 - times[0]) / 3600
  pos = Math.max(0, Math.min(times.length - 1, pos))
  const lo = Math.floor(pos)
  const hi = Math.min(lo + 1, times.length - 1)
  const frac = pos - lo
  const mix = (key) => {
    const values = series[key]
    if (!values.length) return 0
    return values[lo] + (values[hi] - values[lo]) * frac
  }
  return { wind_mph: mix('wind_mph'), rain_in_hr: mix('rain_in_hr'), snow_in_hr: mix('snow_in_hr') }
}

/*
  the main one. give it the heatmap from the server + the load, and it gives back
  { wind_mph, rain_in_hr, snow_in_hr, risk } each shaped [hour][dot] for hours 0..48.
*/
export async function getTheHeatWeather(heatmap, loadLbs) {
  const dots = heatmap.points
  const hourTimes = heatmap.times.map((t) => new Date(t).getTime())
  const startHour = new Date(chopToTheHour(hourTimes[0]).getTime() - 3600 * 1000) // 1 hour early just in case
  const endHour = new Date(chopToTheHour(hourTimes[hourTimes.length - 1]).getTime() + 2 * 3600 * 1000)

  // ask in small groups, one after another (not all at once, thats what gets you blocked)
  const allSeries = []
  for (let i = 0; i < dots.length; i += SPOTS_PER_ASK) {
    if (i > 0) await takeANap(NAP_BETWEEN_ASKS)
    const group = dots.slice(i, i + SPOTS_PER_ASK)
    const answers = await askOpenMeteoFromBrowser(group, startHour, endHour)
    group.forEach((_, j) => allSeries.push(turnIntoTruckUnits(answers[j]?.hourly)))
  }

  // now build the [hour][dot] tables the slider flips thru
  const frames = { wind_mph: [], rain_in_hr: [], snow_in_hr: [], risk: [] }
  for (const whenMs of hourTimes) {
    const windRow = []
    const rainRow = []
    const snowRow = []
    const riskRow = []
    for (const series of allSeries) {
      const wx = weatherAtThisTime(series, whenMs)
      windRow.push(Math.round(wx.wind_mph * 10) / 10)
      rainRow.push(Math.round(wx.rain_in_hr * 1000) / 1000)
      snowRow.push(Math.round(wx.snow_in_hr * 100) / 100)
      // overall risk = the scariest of the 3 (just like quick_scary_score on the server)
      riskRow.push(
        Math.max(howScaryIsWind(wx.wind_mph, loadLbs), howScaryIsRain(wx.rain_in_hr), howScaryIsSnow(wx.snow_in_hr)),
      )
    }
    frames.wind_mph.push(windRow)
    frames.rain_in_hr.push(rainRow)
    frames.snow_in_hr.push(snowRow)
    frames.risk.push(riskRow)
  }
  return frames
}

// true if the server left the heat weather for us to fill in
export function heatNeedsWeather(heatmap) {
  return Boolean(heatmap?.needs_client_weather) && !(heatmap.risk && heatmap.risk.length)
}
