import 'maplibre-gl/dist/maplibre-gl.css'

import { Drawer } from 'antd'
import { Map as MapLibre, Popup, setWorkerUrl, type GeoJSONSource, type LngLatBoundsLike } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { Minus, Plus, Scan } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

import type { RegionMapCollection, SchoolMapCollection, SchoolStatus } from '../../api/types'
import { useThemeMode } from '../../app/themeMode'
import { useMediaQuery } from '../../app/useMediaQuery'
import { PHONE_SCREEN, SIZES } from '../../styles/theme'
import { Button } from '../ui/Button'
import { SHEET_HEIGHT } from './FilterSheet'
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
import { SchoolPopover } from './SchoolPopover'

// MapLibre 6 runs its worker as a module: Vite bundles it with its shared chunk into one file.
setWorkerUrl(workerUrl)

// Clusters break up into markers from this zoom on (a district, not the oblast).
const CLUSTER_MAX_ZOOM = 10
const CLUSTER_RADIUS = 48
const FIT_PADDING = 48
const FIT_MAX_ZOOM = 12
// The popover stands clear of the selected marker and its ring, and of the edges of the map.
const POPOVER_OFFSET = 16
const POPOVER_MARGIN = 12

/** Pixels to pan so that [start, end] fits into [min, max]; the start wins when it cannot fit. */
function overflow(start: number, end: number, min: number, max: number): number {
  if (start < min + POPOVER_MARGIN) return start - min - POPOVER_MARGIN
  if (end > max - POPOVER_MARGIN) return Math.min(end - max + POPOVER_MARGIN, start - min - POPOVER_MARGIN)
  return 0
}

interface SchoolMapProps {
  schools: SchoolMapCollection
  regions: RegionMapCollection | undefined
  /** District of the filter: its boundary is highlighted. */
  regionId: number | undefined
  className?: string
}

/**
 * Schools of VKO on the map (DESIGN.md §2.5, §3.13): markers in the colours of the statuses, clusters;
 * a click on a marker opens the popover of the school (§3.14).
 */
export function SchoolMap({ schools, regions, regionId, className }: SchoolMapProps) {
  const frame = useRef<HTMLDivElement>(null)
  const container = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<MapLibre | null>(null)
  const [hidden, setHidden] = useState<SchoolStatus[]>([])
  const [selectedId, setSelectedId] = useState<number>()
  // MapLibre positions the popup; React renders the popover into it through a portal.
  const [popoverNode] = useState(() => document.createElement('div'))
  const [popup] = useState(() =>
    new Popup({ closeButton: false, closeOnClick: false, maxWidth: 'none', offset: POPOVER_OFFSET }).setDOMContent(
      popoverNode,
    ),
  )
  const { mode } = useThemeMode()
  const phone = useMediaQuery(PHONE_SCREEN)
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

    // A click on a marker opens its popover, a click anywhere else on the map closes it; clicks inside
    // the popover are not the map's.
    instance.on('click', (event) => {
      if (event.originalEvent.target !== instance.getCanvas()) return
      const school = instance.queryRenderedFeatures(event.point, { layers: [LAYERS.schools] })[0]
      setSelectedId(typeof school?.id === 'number' ? school.id : undefined)
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

    return () => {
      popup.remove()
      instance.remove()
    }
  }, [popup])

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

  // The popover follows the fresh data of the school and closes when its marker is hidden or filtered out.
  const selected = schools.features.find(
    (school) => school.id === selectedId && school.geometry && !hidden.includes(school.properties.status),
  )
  const coordinates = selected?.geometry?.coordinates
  const [lng, lat] = coordinates ?? []

  // DESIGN.md §9.3, row «Поповер карты»: a phone shows the popover in a bottom sheet, so the
  // MapLibre popup is not attached at all there.
  useEffect(() => {
    if (!map) return
    if (phone || lng === undefined || lat === undefined) {
      popup.remove()
      return
    }
    popup.setLngLat([lng, lat])
    if (!popup.isOpen()) popup.addTo(map)
  }, [map, phone, popup, lng, lat])

  // Ring of the selected marker; the previous one is cleared on the next change, not on unmount.
  const marked = useRef<number | undefined>(undefined)
  const selectedMarker = selected?.id
  useEffect(() => {
    if (!map) return
    if (marked.current !== undefined) map.setFeatureState({ source: SCHOOLS, id: marked.current }, { selected: false })
    if (selectedMarker !== undefined) map.setFeatureState({ source: SCHOOLS, id: selectedMarker }, { selected: true })
    marked.current = selectedMarker
  }, [map, selectedMarker])

  // A popover that does not fit into the map on opening pans the map until it does.
  useEffect(() => {
    if (!map || phone || selectedMarker === undefined) return
    const frame = requestAnimationFrame(() => {
      const box = popup.getElement()?.getBoundingClientRect()
      if (!box) return
      const view = map.getContainer().getBoundingClientRect()
      const dx = overflow(box.left, box.right, view.left, view.right)
      const dy = overflow(box.top, box.bottom, view.top, view.bottom)
      if (dx || dy) map.panBy([dx, dy])
    })
    return () => cancelAnimationFrame(frame)
  }, [map, phone, popup, selectedMarker])

  // Esc or a click outside the map closes the popover (DESIGN.md §3.14).
  useEffect(() => {
    if (phone || selectedMarker === undefined) return
    const close = () => setSelectedId(undefined)
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close()
    }
    const onPointer = (event: PointerEvent) => {
      if (!frame.current?.contains(event.target as Node)) close()
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointer)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointer)
    }
  }, [phone, selectedMarker])

  const fit = () => {
    const bounds: LngLatBoundsLike | undefined = boundsOf(schoolPoints(schools, hidden), regionShapes(regions))
    if (bounds) map?.fitBounds(bounds, { padding: FIT_PADDING, maxZoom: FIT_MAX_ZOOM })
  }
  const toggle = (status: SchoolStatus) =>
    setHidden((current) => (current.includes(status) ? current.filter((s) => s !== status) : [...current, status]))
  const icon = { size: SIZES.iconMd, strokeWidth: SIZES.iconStroke }

  return (
    <div ref={frame} className={className ? `${styles.frame} ${className}` : styles.frame}>
      <div ref={container} className={styles.map} />
      <div className={styles.controls}>
        <Button kind="outlined" tooltip="Приблизить" icon={<Plus {...icon} />} onClick={() => map?.zoomIn()} />
        <Button kind="outlined" tooltip="Отдалить" icon={<Minus {...icon} />} onClick={() => map?.zoomOut()} />
        <Button kind="outlined" tooltip="Вписать область" icon={<Scan {...icon} />} onClick={fit} />
      </div>
      <MapLegend schools={schools} hidden={hidden} onToggle={toggle} />
      {selected && !phone && createPortal(<SchoolPopover school={selected} />, popoverNode)}
      <Drawer
        placement="bottom"
        height={SHEET_HEIGHT}
        open={phone && selected !== undefined}
        onClose={() => setSelectedId(undefined)}
      >
        {selected && <SchoolPopover school={selected} />}
      </Drawer>
    </div>
  )
}
