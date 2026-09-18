import 'maplibre-gl/dist/maplibre-gl.css'

import { Map as MapLibre, setWorkerUrl, type GeoJSONSource, type LngLatBoundsLike } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { Minus, Plus, Scan } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import type { RegionMapCollection, SchoolMapCollection, SchoolStatus } from '../../api/types'
import { useThemeMode } from '../../app/themeMode'
import { SIZES } from '../../styles/theme'
import { Button } from '../ui/Button'
import { MapLegend } from './MapLegend'
import {
  LAYERS,
  REGIONS,
  SCHOOLS,
  baseStyle,
  boundsOf,
  dataLayers,
  paintLayers,
  regionShapes,
  schoolPoints,
  selectRegion,
} from './mapStyle'
import styles from './SchoolMap.module.css'

// MapLibre 6 runs its worker as a module: Vite bundles it with its shared chunk into one file.
setWorkerUrl(workerUrl)

// Clusters break up into markers from this zoom on (a district, not the oblast).
const CLUSTER_MAX_ZOOM = 10
const CLUSTER_RADIUS = 48
const FIT_PADDING = 48
const FIT_MAX_ZOOM = 12

interface SchoolMapProps {
  schools: SchoolMapCollection
  regions: RegionMapCollection | undefined
  /** District of the filter: its boundary is highlighted. */
  regionId: number | undefined
  className?: string
}

/** Schools of VKO on the map (DESIGN.md §2.5, §3.13): markers in the colours of the statuses, clusters. */
export function SchoolMap({ schools, regions, regionId, className }: SchoolMapProps) {
  const container = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<MapLibre | null>(null)
  const [hidden, setHidden] = useState<SchoolStatus[]>([])
  const { mode } = useThemeMode()
  // Values the map starts with; later changes reach it through the effects below.
  const initial = useRef({ schools, regions, regionId, mode })

  useEffect(() => {
    const start = initial.current
    const points = schoolPoints(start.schools, [])
    const shapes = regionShapes(start.regions)
    const instance = new MapLibre({
      container: container.current!,
      style: baseStyle(start.mode),
      bounds: boundsOf(points, shapes),
      fitBoundsOptions: { padding: FIT_PADDING, maxZoom: FIT_MAX_ZOOM },
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
    })
    instance.touchZoomRotate.disableRotation()

    instance.on('load', () => {
      instance.addSource(REGIONS, { type: 'geojson', data: shapes })
      instance.addSource(SCHOOLS, {
        type: 'geojson',
        data: points,
        cluster: true,
        clusterMaxZoom: CLUSTER_MAX_ZOOM,
        clusterRadius: CLUSTER_RADIUS,
        clusterProperties: { worst: ['max', ['get', 'severity']] },
      })
      for (const layer of dataLayers(start.regionId)) instance.addLayer(layer)
      paintLayers(instance, start.mode)
      setMap(instance)
    })

    // A click on a cluster zooms in until it breaks up.
    instance.on('click', LAYERS.clusters, async (event) => {
      const cluster = event.features?.[0]
      if (!cluster || cluster.geometry.type !== 'Point') return
      const source = instance.getSource<GeoJSONSource>(SCHOOLS)
      const zoom = await source?.getClusterExpansionZoom(cluster.properties.cluster_id as number)
      instance.easeTo({ center: cluster.geometry.coordinates as [number, number], zoom })
    })
    let hovered: string | number | undefined
    const unhover = () => {
      if (hovered !== undefined) instance.setFeatureState({ source: SCHOOLS, id: hovered }, { hover: false })
      hovered = undefined
    }
    instance.on('mousemove', LAYERS.schools, (event) => {
      const id = event.features?.[0]?.id
      if (id === hovered) return
      unhover()
      hovered = id
      if (id !== undefined) instance.setFeatureState({ source: SCHOOLS, id }, { hover: true })
    })
    instance.on('mouseleave', LAYERS.schools, unhover)
    for (const layer of [LAYERS.clusters, LAYERS.schools]) {
      instance.on('mouseenter', layer, () => (instance.getCanvas().style.cursor = 'pointer'))
      instance.on('mouseleave', layer, () => (instance.getCanvas().style.cursor = ''))
    }

    return () => instance.remove()
  }, [])

  useEffect(() => {
    map?.getSource<GeoJSONSource>(SCHOOLS)?.setData(schoolPoints(schools, hidden))
  }, [map, schools, hidden])

  useEffect(() => {
    map?.getSource<GeoJSONSource>(REGIONS)?.setData(regionShapes(regions))
  }, [map, regions])

  useEffect(() => {
    if (map) selectRegion(map, regionId)
  }, [map, regionId])

  useEffect(() => {
    if (map) paintLayers(map, mode)
  }, [map, mode])

  const fit = () => {
    const bounds: LngLatBoundsLike | undefined = boundsOf(schoolPoints(schools, hidden), regionShapes(regions))
    if (bounds) map?.fitBounds(bounds, { padding: FIT_PADDING, maxZoom: FIT_MAX_ZOOM })
  }
  const toggle = (status: SchoolStatus) =>
    setHidden((current) => (current.includes(status) ? current.filter((s) => s !== status) : [...current, status]))
  const icon = { size: SIZES.iconMd, strokeWidth: SIZES.iconStroke }

  return (
    <div className={className ? `${styles.frame} ${className}` : styles.frame}>
      <div ref={container} className={styles.map} />
      <div className={styles.controls}>
        <Button kind="outlined" tooltip="Приблизить" icon={<Plus {...icon} />} onClick={() => map?.zoomIn()} />
        <Button kind="outlined" tooltip="Отдалить" icon={<Minus {...icon} />} onClick={() => map?.zoomOut()} />
        <Button kind="outlined" tooltip="Вписать область" icon={<Scan {...icon} />} onClick={fit} />
      </div>
      <MapLegend schools={schools} hidden={hidden} onToggle={toggle} />
    </div>
  )
}
