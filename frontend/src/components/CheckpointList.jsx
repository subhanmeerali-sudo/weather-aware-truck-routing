import { ScaryChip } from './RouteCards.jsx'
import { myTimezoneName, prettyClock } from '../lib/timeStuff.js'

// a table of every checkpoint on the picked road. click one to zoom the map to it
export default function CheckpointList({ route, focusedIndex, onFocus }) {
  return (
    <section className="checkpoints">
      <h3>
        {route.label} checkpoints <small>({route.checkpoints.length})</small>
      </h3>
      <div className="checkpoints__scroll">
        <table>
          <thead>
            <tr>
              <th>Mile</th>
              <th>ETA ({myTimezoneName()})</th>
              <th>Wind</th>
              <th>Rain</th>
              <th>Snow</th>
              <th>Risk</th>
            </tr>
          </thead>
          <tbody>
            {route.checkpoints.map((cp) => (
              <tr
                key={cp.index}
                className={cp.index === focusedIndex ? 'is-focused' : ''}
                onClick={() => onFocus(cp.index)}
                title={cp.risk.reasons.join(', ') || 'All clear'}
              >
                <td>{cp.mile.toFixed(0)}</td>
                <td>{prettyClock(cp.eta)}</td>
                <td>{cp.weather.wind_mph.toFixed(0)} mph</td>
                <td>{cp.weather.rain_in_hr.toFixed(2)}″</td>
                <td>{cp.weather.snow_in_hr.toFixed(1)}″</td>
                <td>
                  <ScaryChip level={cp.risk.level} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
