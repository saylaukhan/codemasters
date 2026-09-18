import 'maplibre-gl/dist/maplibre-gl.css'

import { Map as MapLibre, Marker, setWorkerUrl, type MapMouseEvent } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { useEffect, useRef, useState } from 'react'

import type { GeoPoint } from '../../api/types'
import { useThemeMode } from '../../app/themeMode'
import { baseStyle, boundsOf, regionShapes } from '../map/mapStyle'
import { useRegionBoundaries } from '../map/queries'
import styles from './Admin.module.css'

// MapLibre 6 runs its worker as a module, as on the map of schools.
setWorkerUrl(workerUrl)

// A school is found street by street; the districts are shown while there is no point.
const POINT_ZOOM = 14
const FIT_PADDING = 24
// Six decimals are about 10 cm: finer than a click can aim.
const round = (value: number): number => Math.round(value * 1e6) / 1e6

interface LocationPickerProps {
  /** Point the map opens at; none — the districts of VKO. */
  start: GeoPoint | null
  /** Point of the form now: the marker follows it. */
  lat: number | null
  lon: number | null
  onPick: (point: GeoPoint) => void
}

/** Point of a school on the map (ТЗ п. 3): a click sets it, the fields of the form show the coordinates. */
export function LocationPicker({ start, lat, lon, onPick }: LocationPickerProps) {
  const container = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<MapLibre | null>(null)
  const [marker] = useState(() => {
    const element = document.createElement('div')
    element.className = styles.marker
    return new Marker({ element })
  })
  const { mode } = useThemeMode()
  const regions = useRegionBoundaries()
  // Values the map starts with; later changes reach it through the effects below.
  const initial = useRef({ start, mode })

  useEffect(() => {
    const { start: point, mode: startMode } = initial.current
    const instance = new MapLibre({
      container: container.current!,
      style: baseStyle(startMode),
      ...(point && { center: [point.lon, point.lat] as [number, number], zoom: POINT_ZOOM }),
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
    })
    instance.touchZoomRotate.disableRotation()
    instance.on('load', () => setMap(instance))
    return () => {
      marker.remove()
      instance.remove()
    }
  }, [marker])

  // Without a point the map shows the districts of VKO.
  useEffect(() => {
    if (!map || initial.current.start) return
    const bounds = boundsOf(regionShapes(regions.data))
    if (bounds) map.fitBounds(bounds, { padding: FIT_PADDING, animate: false })
  }, [map, regions.data])

  useEffect(() => {
    if (!map) return
    const pick = (event: MapMouseEvent) => {
      const point = event.lngLat.wrap()
      onPick({ lat: round(point.lat), lon: round(point.lng) })
    }
    map.on('click', pick)
    return () => {
      map.off('click', pick)
    }
  }, [map, onPick])

  // The marker follows the fields; a point typed outside the view brings the map to it.
  useEffect(() => {
    if (!map) return
    if (lat == null || lon == null) {
      marker.remove()
      return
    }
    marker.setLngLat([lon, lat]).addTo(map)
    if (!map.getBounds().contains([lon, lat])) map.easeTo({ center: [lon, lat] })
  }, [map, marker, lat, lon])

  useEffect(() => {
    map?.setStyle(baseStyle(mode))
  }, [map, mode])

  return (
    <div className={styles.picker}>
      <div ref={container} className={styles.canvas} />
    </div>
  )
}
