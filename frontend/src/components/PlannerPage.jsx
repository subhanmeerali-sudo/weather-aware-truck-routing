import { useCallback, useRef, useState } from 'react'
import TripForm from './TripForm.jsx'
import RouteCards from './RouteCards.jsx'
import CheckpointList from './CheckpointList.jsx'
import TripMap from './TripMap.jsx'
import HeatControls from './HeatControls.jsx'
import { askServerForTrip } from '../lib/askTheServer.js'
import { getTheHeatWeather, heatNeedsWeather } from '../lib/getTheHeatWeather.js'

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
  const [heatStatus, setHeatStatus] = useState('idle') // idle | loading | ready | oops
  const tripNumber = useRef(0) // so an old slow heat answer cant overwrite a newer trip

  // after the trip comes back, the browser goes and gets the heatmap weather itself
  async function fillInTheHeat(answer, myTripNumber) {
    if (!heatNeedsWeather(answer.heatmap)) {
      setHeatStatus('ready')
      return
    }
    setHeatStatus('loading')
    try {
      const frames = await getTheHeatWeather(answer.heatmap, answer.load_lbs)
      if (myTripNumber !== tripNumber.current) return // a newer trip showed up, ignore this one
      setPlan((old) =>
        old === answer ? { ...old, heatmap: { ...old.heatmap, ...frames, needs_client_weather: false } } : old,
      )
      setHeatStatus('ready')
    } catch (err) {
      if (myTripNumber !== tripNumber.current) return
      console.warn('heatmap weather failed', err)
      setHeatStatus('oops')
    }
  }

  // asks the server for the trip and saves the answer
  async function getTheTrip(form) {
    setIsLoading(true)
    setOops('')
    setIsPlaying(false)
    tripNumber.current += 1
    const myTripNumber = tripNumber.current
    try {
      const answer = await askServerForTrip(form)
      setPlan(answer)
      fillInTheHeat(answer, myTripNumber) // no await on purpose, the routes show up right away
      setPickedRouteId(answer.recommendation.route_id) // start with the best one picked
      setFocusedIndex(null)
      setHeatHour(0)
    } catch (err) {
      setOops(err.message)
    } finally {
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

        {plan && <RouteCards plan={plan} pickedRouteId={pickedRouteId} onPickRoute={pickARoad} />}
        {pickedRoute && <CheckpointList route={pickedRoute} focusedIndex={focusedIndex} onFocus={setFocusedIndex} />}

        {plan && (
          <footer className="meta">
            Planned in {plan.meta.took_seconds}s · {plan.meta.weather_spots} checkpoint weather points · Routing © OSRM/OpenStreetMap ·
            Weather © Open-Meteo
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
            Finding roads and checking the sky…
          </div>
        )}
      </section>
    </div>
  )
}
