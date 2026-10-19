import { useEffect, useMemo, useRef } from 'react'
import L from 'leaflet'
import { CircleMarker, MapContainer, Marker, Pane, Polyline, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { HeatPaintLayer } from '../lib/paintTheHeat.js'
import { findTruckAtHour } from '../lib/findTheTruck.js'
import {
  colorForRoad,
  colorForScaryLevel,
  howScaryIsRain,
  howScaryIsSnow,
  howScaryIsWind,
} from '../lib/scaryStuff.js'
import { prettyDateTime } from '../lib/timeStuff.js'
import RiskLegend from './RiskLegend.jsx'

const USA_CENTER = [39.5, -98.35]
const GRAY_TILES = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}'
const LABEL_TILES =
  'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}'
const TILE_CREDITS = 'Tiles &copy; Esri, HERE, Garmin &middot; &copy; OpenStreetMap contributors'

// zooms the map so the whole trip fits on screen (only when a new trip comes in)
function ZoomToTheTrip({ plan }) {
  const map = useMap()
  useEffect(() => {
    if (!plan) return
    const allDots = plan.routes.flatMap((r) => r.geometry)
    if (allDots.length) map.flyToBounds(L.latLngBounds(allDots), { padding: [40, 40], duration: 0.8 })
  }, [plan, map])
  return null
}

// turns the heatmap numbers for one hour into [lat, lon, score] dots
function makeHeatDots(heatmap, hour, kind, loadLbs) {
  if (!heatmap || !heatmap.risk || !heatmap.risk[hour]) return [] // weather not here yet (still loading)
  return heatmap.points.map(([lat, lon], i) => {
    let score
    if (kind === 'wind') score = howScaryIsWind(heatmap.wind_mph[hour][i], loadLbs)
    else if (kind === 'rain') score = howScaryIsRain(heatmap.rain_in_hr[hour][i])
    else if (kind === 'snow') score = howScaryIsSnow(heatmap.snow_in_hr[hour][i])
    else score = heatmap.risk[hour][i]
    return [lat, lon, score]
  })
}

// puts our custom heat canvas on the map and updates it when the slider moves
function HeatBlobs({ dots, isOn }) {
  const map = useMap()
  const layerRef = useRef(null)

  useEffect(() => {
    layerRef.current = new HeatPaintLayer({ pane: 'heat' })
    return () => {
      if (layerRef.current) map.removeLayer(layerRef.current)
    }
  }, [map])

  useEffect(() => {
    const layer = layerRef.current
    if (!layer) return
    if (isOn && !map.hasLayer(layer)) layer.addTo(map)
    if (!isOn && map.hasLayer(layer)) map.removeLayer(layer)
  }, [isOn, map])

  useEffect(() => {
    layerRef.current?.setDots(dots)
  }, [dots])

  return null
}

// flies to a checkpoint when you click it in the table and pops open its bubble
function FlyToCheckpoint({ route, focusedIndex, markerRefs }) {
  const map = useMap()
  useEffect(() => {
    if (focusedIndex == null || !route) return
    const cp = route.checkpoints[focusedIndex]
    if (!cp) return
    map.flyTo([cp.lat, cp.lon], Math.max(map.getZoom(), 9), { duration: 0.6 })
    const marker = markerRefs.current[focusedIndex]
    if (marker) setTimeout(() => marker.openPopup(), 650)
  }, [focusedIndex, route, map, markerRefs])
  return null
}

function makeTruckIcon(color, isPicked) {
  return L.divIcon({
    className: 'truck-icon-wrap',
    html: `<div class="truck-icon ${isPicked ? 'is-picked' : ''}" style="border-color:${color}">🚚</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
  })
}

function makePinIcon(text, color) {
  return L.divIcon({
    className: 'pin-icon-wrap',
    html: `<div class="pin-icon" style="background:${color}">${text}</div>`,
    iconSize: [52, 24],
    iconAnchor: [26, 34],
  })
}

const START_PIN = makePinIcon('Start', '#001830')
const END_PIN = makePinIcon('End', '#F84858')

export default function TripMap({ plan, pickedRouteId, onPickRoute, heatHour, heatKind, heatIsOn, focusedIndex }) {
  const markerRefs = useRef({})
  const pickedRoute = plan?.routes.find((r) => r.id === pickedRouteId)

  // only remake heat dots when the hour / kind / trip actually changes
  const heatDots = useMemo(
    () => makeHeatDots(plan?.heatmap, heatHour, heatKind, plan?.load_lbs ?? 0),
    [plan, heatHour, heatKind],
  )

  // the picked road gets drawn last so its on top of the others
  const roadsInDrawOrder = useMemo(() => {
    if (!plan) return []
    return [...plan.routes].sort((a, b) => (a.id === pickedRouteId) - (b.id === pickedRouteId))
  }, [plan, pickedRouteId])

  return (
    <div className="map-wrap">
      <MapContainer center={USA_CENTER} zoom={4} preferCanvas zoomControl={false} className="map">
        {/* light gray map so the colors pop. labels go on their own layer ABOVE the heatmap so you can still read them */}
        <TileLayer url={GRAY_TILES} attribution={TILE_CREDITS} maxNativeZoom={16} maxZoom={18} />
        <Pane name="heat" style={{ zIndex: 350 }} />
        <Pane name="labels" style={{ zIndex: 380, pointerEvents: 'none' }}>
          <TileLayer url={LABEL_TILES} maxNativeZoom={16} maxZoom={18} />
        </Pane>
        <HeatBlobs dots={heatDots} isOn={heatIsOn && Boolean(plan)} />
        <ZoomToTheTrip plan={plan} />

        {roadsInDrawOrder.map((route) => {
          const isPicked = route.id === pickedRouteId
          return (
            <Polyline
              key={`${route.id}-${isPicked}`}
              positions={route.geometry}
              pathOptions={{
                color: colorForRoad(route.id),
                weight: isPicked ? 7 : 4,
                opacity: isPicked ? 0.95 : 0.5,
                dashArray: route.recommended || isPicked ? null : '8 8',
                lineCap: 'round',
              }}
              eventHandlers={{ click: () => onPickRoute(route.id) }}
            >
              <Tooltip sticky>
                {route.label} {route.recommended ? '★ Best pick' : ''} · {route.distance_miles.toFixed(0)} mi
              </Tooltip>
            </Polyline>
          )
        })}

        {pickedRoute?.checkpoints.map((cp) => (
          <CircleMarker
            key={`${pickedRoute.id}-${cp.index}`}
            ref={(m) => (markerRefs.current[cp.index] = m)}
            center={[cp.lat, cp.lon]}
            radius={cp.index === focusedIndex ? 9 : 6}
            pathOptions={{ color: '#fff', weight: 2, fillColor: colorForScaryLevel(cp.risk.level), fillOpacity: 1 }}
          >
            <Popup>
              <div className="cp-popup">
                <div className="cp-popup__head" style={{ background: colorForScaryLevel(cp.risk.level) }}>
                  {cp.risk.level}
                </div>
                <div>
                  <b>Mile {cp.mile.toFixed(0)}</b> on {pickedRoute.label}
                </div>
                <div>ETA {prettyDateTime(cp.eta)}</div>
                <div>
                  Wind {cp.weather.wind_mph.toFixed(0)} mph
                  {cp.weather.gust_mph != null ? ` (gusts ${cp.weather.gust_mph.toFixed(0)})` : ''}
                </div>
                <div>Rain {cp.weather.rain_in_hr.toFixed(2)} in/hr</div>
                <div>Snow {cp.weather.snow_in_hr.toFixed(2)} in/hr</div>
                {cp.weather.temp_f != null && <div>Temp {cp.weather.temp_f.toFixed(0)}°F</div>}
                {cp.risk.reasons.length > 0 && <div className="cp-popup__why">Why: {cp.risk.reasons.join('; ')}</div>}
              </div>
            </Popup>
          </CircleMarker>
        ))}

        {plan &&
          plan.routes.map((route) => {
            const truck = findTruckAtHour(route, heatHour)
            if (!truck) return null
            return (
              <Marker
                key={`truck-${route.id}`}
                position={[truck.lat, truck.lon]}
                icon={makeTruckIcon(colorForRoad(route.id), route.id === pickedRouteId)}
                zIndexOffset={route.id === pickedRouteId ? 1000 : 0}
                eventHandlers={{ click: () => onPickRoute(route.id) }}
              >
                <Tooltip direction="top" offset={[0, -14]}>
                  {route.label}: {truck.status === 'arrived' ? 'arrived' : `mile ${truck.mile.toFixed(0)}`}
                </Tooltip>
              </Marker>
            )
          })}

        {plan && (
          <>
            <Marker position={[plan.origin.lat, plan.origin.lon]} icon={START_PIN}>
              <Tooltip direction="top">Start: {plan.origin.name}</Tooltip>
            </Marker>
            <Marker position={[plan.destination.lat, plan.destination.lon]} icon={END_PIN}>
              <Tooltip direction="top">End: {plan.destination.name}</Tooltip>
            </Marker>
          </>
        )}

        <FlyToCheckpoint route={pickedRoute} focusedIndex={focusedIndex} markerRefs={markerRefs} />
      </MapContainer>
      <RiskLegend />
    </div>
  )
}
