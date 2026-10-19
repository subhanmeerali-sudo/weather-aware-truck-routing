import { useCallback, useRef, useState } from 'react'
import TripForm from './TripForm.jsx'
import RouteCards from './RouteCards.jsx'
import CheckpointList from './CheckpointList.jsx'
import TripMap from './TripMap.jsx'
import HeatControls from './HeatControls.jsx'
import { askServerForTrip } from '../lib/askTheServer.js'
import {
  getTheCheckpointWeather,
  getTheHeatWeather,
  heatNeedsWeather,
  planNeedsWeather,
} from '../lib/getTheHeatWeather.js'
import { fillInRiskAndPickWinner } from '../lib/pickTheRoad.js'

// the main screen. form + results on the left, big map on the right
export default function PlannerPage() {
  const [plan, setPlan] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [oops, setOops] = useState('')
  const [pickedRouteId, setPickedRouteId] = useState(null)
  const [focusedIndex, setFocusedIndex] = useState(null)
  const [heatHour, setHeatHour] = useState(0)
  const [heatKind, setHeatKind] = useState('risk')
  const [heatIsOn, setHeatIsOn] = useState(true)
  const [isPlaying, setIsPlaying] = useState(false)
  const [weatherStatus, setWeatherStatus] = useState('idle') // idle | loading | ready | oops
  const [heatStatus, setHeatStatus] = useState('idle') // idle | loading | ready | oops
  const tripNumber = useRef(0) // so an old slow weather answer cant overwrite a newer trip

  // after the trip comes back, the browser gets checkpoint weather + picks the best road
  async function fillInCheckpointWeather(answer, myTripNumber) {
    if (!planNeedsWeather(answer)) {
      setWeatherStatus('ready')
      return answer
    }
    setWeatherStatus('loading')
    try {
      const weatherBySpot = await getTheCheckpointWeather(answer.routes)
      if (myTripNumber !== tripNumber.current) return null
      const filled = fillInRiskAndPickWinner(answer, weatherBySpot)
      setPlan(filled)
      setPickedRouteId(filled.recommendation.route_id)
      setWeatherStatus('ready')
      return filled
    } catch (err) {
      if (myTripNumber !== tripNumber.current) return null
      console.warn('checkpoint weather failed', err)
      setWeatherStatus('oops')
      setOops(err.message || 'Could not load weather for checkpoints.')
      return answer
    }
  }

  // heatmap weather can take longer; run it after (or alongside) checkpoints
  async function fillInTheHeat(answer, myTripNumber) {
    if (!heatNeedsWeather(answer.heatmap)) {
      setHeatStatus('ready')
      return
    }
    setHeatStatus('loading')
    try {
      const frames = await getTheHeatWeather(answer.heatmap, answer.load_lbs)
      if (myTripNumber !== tripNumber.current) return
      setPlan((old) => {
        if (!old) return old
        // merge onto whatever plan is current (might already have risk filled in)
        return { ...old, heatmap: { ...old.heatmap, ...frames, needs_client_weather: false } }
      })
      setHeatStatus('ready')
    } catch (err) {
      if (myTripNumber !== tripNumber.current) return
      console.warn('heatmap weather failed', err)
      setHeatStatus('oops')
    }
  }

  // asks the server for the trip (roads only) then fills weather in the browser
  async function getTheTrip(form) {
    setIsLoading(true)
    setOops('')
    setIsPlaying(false)
    setWeatherStatus('idle')
    setHeatStatus('idle')
    tripNumber.current += 1
    const myTripNumber = tripNumber.current
    try {
      const answer = await askServerForTrip(form)
      // show roads on the map RIGHT AWAY (before weather)
      setPlan(answer)
      setPickedRouteId(answer.recommendation.route_id)
      setFocusedIndex(null)
      setHeatHour(0)
      setIsLoading(false)

      // weather in the browser (checkpoints first so cards/risk update fast)
      const filled = await fillInCheckpointWeather(answer, myTripNumber)
      if (myTripNumber !== tripNumber.current) return
      // heat can keep going; use the original heatmap geometry either way
      fillInTheHeat(filled || answer, myTripNumber)
    } catch (err) {
      setOops(err.message)
      setIsLoading(false)
    }
  }

  const pickARoad = useCallback((id) => {
    setPickedRouteId(id)
    setFocusedIndex(null)
  }, [])

  const pickedRoute = plan?.routes.find((r) => r.id === pickedRouteId)

  return (
    <div className="planner">
      <aside className="sidebar">
        <header className="brand">
          <img src="/favicon.png" alt="" className="brand__mark" />
          <div>
            <div className="brand__title">Weather-Aware Truck Routing</div>
            <div className="brand__sub">3 routes · weather at your ETA · load-aware risk</div>
          </div>
        </header>

        <TripForm isLoading={isLoading} onPlan={getTheTrip} />

        {oops && <div className="error">{oops}</div>}

        {!plan && !isLoading && !oops && (
          <div className="empty">
            Enter a trip and we&apos;ll compare 3 routes using the forecast for when your truck actually gets to each
            checkpoint.
          </div>
        )}

        {plan && (
          <RouteCards
            plan={plan}
            pickedRouteId={pickedRouteId}
            onPickRoute={pickARoad}
            weatherStatus={weatherStatus}
          />
        )}
        {pickedRoute && (
          <CheckpointList
            route={pickedRoute}
            focusedIndex={focusedIndex}
            onFocus={setFocusedIndex}
            weatherStatus={weatherStatus}
          />
        )}

        {plan && (
          <footer className="meta">
            Planned in {plan.meta.took_seconds}s · {plan.meta.weather_spots} checkpoint weather points · Routing ©
            OSRM/OpenStreetMap · Weather © Open-Meteo
          </footer>
        )}
      </aside>

      <section className="map-area">
        <TripMap
          plan={plan}
          pickedRouteId={pickedRouteId}
          onPickRoute={pickARoad}
          heatHour={heatHour}
          heatKind={heatKind}
          heatIsOn={heatIsOn}
          focusedIndex={focusedIndex}
          weatherStatus={weatherStatus}
        />
        {plan && (
          <HeatControls
            heatmap={plan.heatmap}
            heatStatus={heatStatus}
            hour={heatHour}
            setHour={setHeatHour}
            kind={heatKind}
            setKind={setHeatKind}
            isOn={heatIsOn}
            setIsOn={setHeatIsOn}
            isPlaying={isPlaying}
            setIsPlaying={setIsPlaying}
          />
        )}
        {isLoading && (
          <div className="map-loading">
            <span className="spinner spinner--big" />
            Finding roads…
          </div>
        )}
        {!isLoading && weatherStatus === 'loading' && (
          <div className="map-loading map-loading--soft">
            <span className="spinner" />
            Checking weather…
          </div>
        )}
      </section>
    </div>
  )
}
