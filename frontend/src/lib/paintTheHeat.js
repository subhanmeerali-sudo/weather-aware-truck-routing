import L from 'leaflet'
import { colorForScaryLevel, hexToRgb, SCARY_LEVELS } from './scaryStuff.js'

/*
  our own little heatmap layer for leaflet.

  why not leaflet.heat? that one ADDS colors together when blobs overlap, so
  a bunch of "Low" dots right next to each other turn red and look scary when
  theyre not. our risk is in buckets (Low..No Travel) so we just paint soft
  blobs in the bucket color, and paint the scary ones LAST so they sit on top.

  its one canvas, redrawn when you pan/zoom or move the slider. 300 blobs
  takes like 2ms so the slider feels instant.
*/

// pre-make the colors once so we dont do math every frame
const BLOB_RGB = Object.fromEntries(SCARY_LEVELS.map((lvl, i) => [i + 1, hexToRgb(colorForScaryLevel(lvl))]))
const BLOB_ALPHA = { 1: 0.24, 2: 0.5, 3: 0.6, 4: 0.68, 5: 0.75 }

export const HeatPaintLayer = L.Layer.extend({
  options: { radiusMiles: 16, pane: 'overlayPane' },

  initialize(options) {
    L.setOptions(this, options)
    this._dots = [] // each dot = [lat, lon, score 1-5]
  },

  onAdd(map) {
    this._map = map
    this._canvas = L.DomUtil.create('canvas', 'heat-canvas leaflet-zoom-animated')
    this._canvas.style.pointerEvents = 'none'
    map.getPane(this.options.pane).appendChild(this._canvas)
    map.on('moveend resize', this._resetCanvas, this)
    map.on('zoomanim', this._slideDuringZoom, this)
    this._resetCanvas()
  },

  onRemove(map) {
    this._canvas.remove()
    map.off('moveend resize', this._resetCanvas, this)
    map.off('zoomanim', this._slideDuringZoom, this)
  },

  // give it new dots (like when the slider moves) and it redraws
  setDots(dots) {
    this._dots = [...dots].sort((a, b) => a[2] - b[2])
    if (this._map) this.paintTheMap()
    return this
  },

  // when the map moves, put the canvas back in the corner and redraw
  _resetCanvas() {
    const map = this._map
    const size = map.getSize()
    const topLeft = map.containerPointToLayerPoint([0, 0])
    L.DomUtil.setPosition(this._canvas, topLeft)
    const ratio = window.devicePixelRatio || 1
    this._canvas.width = size.x * ratio
    this._canvas.height = size.y * ratio
    this._canvas.style.width = `${size.x}px`
    this._canvas.style.height = `${size.y}px`
    this.paintTheMap()
  },

  // makes the blobs grow/shrink smoothly while zooming (copied the idea from leaflet's own layers)
  _slideDuringZoom(e) {
    const map = this._map
    const scale = map.getZoomScale(e.zoom)
    const offset = map._latLngBoundsToNewLayerBounds(map.getBounds(), e.zoom, e.center).min
    L.DomUtil.setTransform(this._canvas, offset, scale)
  },

  // how many pixels is X miles at the current zoom
  _milesToPixels(miles) {
    const map = this._map
    const center = map.getCenter()
    const a = map.latLngToContainerPoint(center)
    const b = map.latLngToContainerPoint([center.lat + miles / 69, center.lng])
    return Math.max(10, Math.min(260, Math.abs(b.y - a.y)))
  },

  // draws every blob. the scary ones were sorted to the end so they go on top
  paintTheMap() {
    const ctx = this._canvas.getContext('2d')
    const ratio = window.devicePixelRatio || 1
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
    ctx.clearRect(0, 0, this._canvas.width, this._canvas.height)
    if (!this._dots.length) return

    const r = this._milesToPixels(this.options.radiusMiles)
    const size = this._map.getSize()
    for (const [lat, lon, score] of this._dots) {
      const p = this._map.latLngToContainerPoint([lat, lon])
      if (p.x < -r || p.y < -r || p.x > size.x + r || p.y > size.y + r) continue // offscreen, skip it
      const [cr, cg, cb] = BLOB_RGB[score] || BLOB_RGB[1]
      const alpha = BLOB_ALPHA[score] || 0.3
      const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, r)
      grad.addColorStop(0, `rgba(${cr},${cg},${cb},${alpha})`)
      grad.addColorStop(0.55, `rgba(${cr},${cg},${cb},${alpha * 0.55})`)
      grad.addColorStop(1, `rgba(${cr},${cg},${cb},0)`)
      ctx.fillStyle = grad
      ctx.fillRect(p.x - r, p.y - r, r * 2, r * 2)
    }
  },
})
