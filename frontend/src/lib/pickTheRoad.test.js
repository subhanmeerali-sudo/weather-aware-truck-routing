import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  seeHowWindy,
  seeHowRainy,
  seeHowSnowy,
  checkIfScary,
  quickScaryScore,
} from './scaryStuff.js'
import { countScaryMiles, pickBestRoad, fillInRiskAndPickWinner } from './pickTheRoad.js'

describe('wind rules (PDF + load)', () => {
  it('buckets light trucks', () => {
    const cases = [
      [0, 'Low'],
      [24.9, 'Low'],
      [25, 'Moderate'],
      [34.9, 'Moderate'],
      [35, 'High'],
      [44.9, 'High'],
      [45, 'Severe'],
      [54.9, 'Severe'],
      [55, 'No Travel'],
      [80, 'No Travel'],
    ]
    for (const [mph, expected] of cases) {
      assert.equal(seeHowWindy(mph, 10000)[0], expected, `wind ${mph}`)
    }
  })

  it('applies load rules', () => {
    assert.equal(seeHowWindy(55, 0)[0], 'No Travel')
    assert.equal(seeHowWindy(47, 30001)[0], 'No Travel')
    assert.equal(seeHowWindy(47, 30000)[0], 'Severe')
    assert.equal(seeHowWindy(38, 40001)[0], 'Severe')
    assert.equal(seeHowWindy(38, 40000)[0], 'High')
  })
})

describe('rain and snow buckets', () => {
  it('rain', () => {
    const cases = [
      [0.0, 'Low'],
      [0.09, 'Low'],
      [0.1, 'Moderate'],
      [0.25, 'High'],
      [0.49, 'High'],
      [0.5, 'Severe'],
      [1.0, 'Severe'],
      [1.01, 'No Travel'],
    ]
    for (const [rate, expected] of cases) {
      assert.equal(seeHowRainy(rate)[0], expected, `rain ${rate}`)
    }
  })

  it('snow', () => {
    const cases = [
      [0.0, 'Low'],
      [0.49, 'Low'],
      [0.5, 'Moderate'],
      [1.0, 'High'],
      [2.0, 'Severe'],
      [3.0, 'Severe'],
      [3.1, 'No Travel'],
    ]
    for (const [rate, expected] of cases) {
      assert.equal(seeHowSnowy(rate)[0], expected, `snow ${rate}`)
    }
  })
})

describe('overall scary', () => {
  it('worst condition wins', () => {
    const risk = checkIfScary({ wind_mph: 10, rain_in_hr: 0.3, snow_in_hr: 0.6 }, 20000)
    assert.equal(risk.level, 'High')
    assert.equal(risk.score, 3)
    assert.equal(risk.snow_level, 'Moderate')
    assert.equal(risk.reasons.length, 2)
  })

  it('quick score matches full check', () => {
    for (const [wind, rain, snow, load] of [
      [5, 0, 0, 0],
      [40, 0, 0, 45000],
      [50, 0.6, 0, 35000],
      [20, 0, 2.5, 0],
    ]) {
      const full = checkIfScary({ wind_mph: wind, rain_in_hr: rain, snow_in_hr: snow }, load)
      assert.equal(quickScaryScore(wind, rain, snow, load), full.score)
    }
  })
})

describe('pick best road', () => {
  function fakeRoad(label, duration, severe = 0, high = 0, avg = 1) {
    return {
      label,
      duration_seconds: duration,
      summary: { severe_miles: severe, high_miles: high, avg_risk: avg, has_no_travel: false },
    }
  }

  it('fewest severe miles beats faster', () => {
    const { ranked, reason } = pickBestRoad([fakeRoad('A', 3600, 20), fakeRoad('B', 7200, 0, 50)])
    assert.equal(ranked[0].label, 'B')
    assert.match(reason, /Severe/)
  })

  it('high miles break severe tie', () => {
    const { ranked } = pickBestRoad([fakeRoad('A', 3600, 0, 30), fakeRoad('B', 5000, 0, 10)])
    assert.equal(ranked[0].label, 'B')
  })

  it('avg risk then time', () => {
    const a = pickBestRoad([fakeRoad('A', 3600, 0, 0, 1.5), fakeRoad('B', 5000, 0, 0, 1.2)])
    assert.equal(a.ranked[0].label, 'B')
    const b = pickBestRoad([fakeRoad('A', 5000), fakeRoad('B', 3600)])
    assert.equal(b.ranked[0].label, 'B')
    assert.match(b.reason, /fastest/)
    assert.equal(b.ranked[0].recommended, true)
    assert.equal(b.ranked[1].recommended, false)
  })
})

describe('count scary miles', () => {
  it('counts severe+no travel together', () => {
    const cps = [
      { miles_covered: 10, risk: { level: 'Low' } },
      { miles_covered: 10, risk: { level: 'Severe' } },
      { miles_covered: 5, risk: { level: 'No Travel' } },
      { miles_covered: 5, risk: { level: 'High' } },
    ]
    const s = countScaryMiles(cps)
    assert.equal(s.severe_miles, 15)
    assert.equal(s.high_miles, 5)
    assert.equal(s.has_no_travel, true)
    assert.ok(Math.abs(s.avg_risk - (10 * 1 + 10 * 4 + 5 * 5 + 5 * 3) / 30) < 0.002)
  })
})

describe('fillInRiskAndPickWinner', () => {
  it('applies weather and picks less scary road', () => {
    const plan = {
      load_lbs: 35000,
      needs_client_weather: true,
      meta: { needs_client_weather: true },
      routes: [
        {
          id: 'a',
          label: 'Route A',
          duration_seconds: 3600,
          checkpoints: [
            { lat: 1, lon: 1, miles_covered: 50, weather: null, risk: null },
            { lat: 1.1, lon: 1.1, miles_covered: 50, weather: null, risk: null },
          ],
          summary: { severe_miles: 0, high_miles: 0, avg_risk: 1, has_no_travel: false, miles_by_level: {} },
        },
        {
          id: 'b',
          label: 'Route B',
          duration_seconds: 7200,
          checkpoints: [
            { lat: 2, lon: 2, miles_covered: 50, weather: null, risk: null },
            { lat: 2.1, lon: 2.1, miles_covered: 50, weather: null, risk: null },
          ],
          summary: { severe_miles: 0, high_miles: 0, avg_risk: 1, has_no_travel: false, miles_by_level: {} },
        },
      ],
      recommendation: { route_id: 'a', label: 'Route A', reason: 'provisional' },
    }
    const weather = new Map([
      ['1,1', { wind_mph: 50, gust_mph: 55, rain_in_hr: 0, snow_in_hr: 0, temp_f: 40 }], // Severe for 35k
      ['1.1,1.1', { wind_mph: 50, gust_mph: 55, rain_in_hr: 0, snow_in_hr: 0, temp_f: 40 }],
      ['2,2', { wind_mph: 10, gust_mph: 12, rain_in_hr: 0, snow_in_hr: 0, temp_f: 40 }],
      ['2.1,2.1', { wind_mph: 10, gust_mph: 12, rain_in_hr: 0, snow_in_hr: 0, temp_f: 40 }],
    ])
    const filled = fillInRiskAndPickWinner(plan, weather)
    assert.equal(filled.recommendation.route_id, 'b')
    assert.equal(filled.needs_client_weather, false)
    assert.ok(filled.routes.find((r) => r.id === 'a').summary.severe_miles > 0)
    assert.equal(filled.routes.find((r) => r.id === 'b').summary.severe_miles, 0)
    assert.equal(filled.routes.find((r) => r.id === 'b').recommended, true)
  })
})
