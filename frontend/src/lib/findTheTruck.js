// figures out where the truck is X hours after it leaves. used for the little truck icons on the slider

export function findTruckAtHour(route, hour) {
  const cps = route.checkpoints
  if (!cps.length) return null
  if (hour <= 0) return { lat: cps[0].lat, lon: cps[0].lon, mile: 0, status: 'departing' }
  const last = cps[cps.length - 1]
  if (hour >= last.hours_from_departure) {
    return { lat: last.lat, lon: last.lon, mile: last.mile, status: 'arrived' }
  }
  // find the 2 checkpoints the truck is between and slide between them
  for (let i = 0; i < cps.length - 1; i++) {
    const a = cps[i]
    const b = cps[i + 1]
    if (hour >= a.hours_from_departure && hour <= b.hours_from_departure) {
      const span = b.hours_from_departure - a.hours_from_departure || 1
      const t = (hour - a.hours_from_departure) / span
      return {
        lat: a.lat + (b.lat - a.lat) * t,
        lon: a.lon + (b.lon - a.lon) * t,
        mile: a.mile + (b.mile - a.mile) * t,
        status: 'driving',
      }
    }
  }
  return null
}
