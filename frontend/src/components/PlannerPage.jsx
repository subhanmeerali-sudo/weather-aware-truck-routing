import { useCallback, useState } from 'react'
import TripForm from './TripForm.jsx'
import RouteCards from './RouteCards.jsx'
import CheckpointList from './CheckpointList.jsx'
import TripMap from './TripMap.jsx'
import HeatControls from './HeatControls.jsx'
import { askServerForTrip } from '../lib/askTheServer.js'

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

  // asks the server for the trip and saves the answer
  async function getTheTrip(form) {
    setIsLoading(true)
    setOops('')
    setIsPlaying(false)
    try {
      const answer = await askServerForTrip(form)
      setPlan(answer)
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
            Planned in {plan.meta.took_seconds}s · {plan.meta.weather_spots} weather points · Routing © OSRM/OpenStreetMap ·
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
