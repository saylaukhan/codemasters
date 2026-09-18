// Style of the school map, DESIGN.md §2.5 and §3.13. Basemap: the public OpenStreetMap tiles of the
// demo (docs/tasks/README.md, «Решения по умолчанию»), muted in the light theme and inverted in the
// dark one by the raster paint; an own tileserver later replaces TILES and GLYPHS only. MapLibre paints
// on a canvas and cannot read CSS, so colours are taken from the tokens of tokens.css at runtime.
import type { AddLayerObject, GeoJSONSource, LngLatBoundsLike, Map as MapLibre, MapOptions } from 'maplibre-gl'

import type { RegionMapCollection, SchoolMapCollection, SchoolStatus } from '../../api/types'
import type { ThemeMode } from '../../app/themeMode'

const TILES = ['https://tile.openstreetmap.org/{z}/{x}/{y}.png']
const TILES_MAX_ZOOM = 19
const ATTRIBUTION = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
// Glyphs of the numbers inside the clusters.
const GLYPHS = 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf'
const CLUSTER_FONT = ['Open Sans Semibold']

const BASEMAP = 'basemap'
// Calm light map and its dark negative (DESIGN.md §3.13): less colour, so the statuses stand out.
const BASEMAP_PAINT: Record<ThemeMode, Record<string, number>> = {
  light: {
    'raster-saturation': -0.7,
    'raster-contrast': -0.1,
    'raster-brightness-min': 0.1,
    'raster-brightness-max': 1,
    'raster-hue-rotate': 0,
  },
  dark: {
    'raster-saturation': -0.7,
    'raster-contrast': 0,
    'raster-brightness-min': 0.75,
    'raster-brightness-max': 0.08,
    'raster-hue-rotate': 180,
  },
}
export const SCHOOLS = 'schools'
export const REGIONS = 'regions'
export const LAYERS = {
  regionFill: 'region-fill',
  regionLine: 'region-line',
  regionSelected: 'region-selected',
  clusters: 'clusters',
  clusterCount: 'cluster-count',
  schools: 'schools',
} as const

/** From the mildest to the worst, as the server folds them (ADR-004); a cluster wears the worst. */
export const SEVERITY: Record<SchoolStatus, number> = { no_data: 0, normal: 1, unstable: 2, critical: 3, offline: 4 }
const STATUSES = Object.keys(SEVERITY) as SchoolStatus[]

// Marker 12px, 16px on hover; cluster 32–48px by the number of schools (DESIGN.md §3.13).
const MARKER_RADIUS = 6
const MARKER_HOVER_RADIUS = 8
const CLUSTER_RADII = [16, 10, 20, 50, 24] as const
// Selected district: accent fill at 8% (DESIGN.md §2.5).
const SELECTED_FILL_OPACITY = 0.08
const CLUSTER_TEXT_SIZE = 13

type Style = Exclude<MapOptions['style'], string | undefined>
type PaintProperty = Parameters<MapLibre['setPaintProperty']>[1]
// Expressions are built as plain arrays; MapLibre validates them when they are set.
type PaintValue = Parameters<MapLibre['setPaintProperty']>[2]
type FeatureCollection = Extract<Parameters<GeoJSONSource['setData']>[0], { type: 'FeatureCollection' }>

export function baseStyle(mode: ThemeMode): Style {
  return {
    version: 8,
    glyphs: GLYPHS,
    sources: {
      [BASEMAP]: { type: 'raster', tiles: TILES, tileSize: 256, maxzoom: TILES_MAX_ZOOM, attribution: ATTRIBUTION },
    },
    layers: [{ id: BASEMAP, type: 'raster', source: BASEMAP, paint: BASEMAP_PAINT[mode] }],
  }
}

const token = (name: string): string => getComputedStyle(document.documentElement).getPropertyValue(name).trim()

const statusToken = (status: SchoolStatus) => token(`--status-${status.replace('_', '-')}-main`)

/** Colour of every status by its severity: the key of a cluster ring. */
function worstColor(): unknown[] {
  return [
    'match',
    ['get', 'worst'],
    ...STATUSES.flatMap((status) => [SEVERITY[status], statusToken(status)]),
    token('--status-no-data-main'),
  ]
}

function statusColor(): unknown[] {
  return [
    'match',
    ['get', 'status'],
    ...STATUSES.flatMap((status) => [status, statusToken(status)]),
    token('--status-no-data-main'),
  ]
}

const selectedRegion = (regionId: number | undefined) => ['==', ['id'], regionId ?? -1]

export function dataLayers(regionId: number | undefined): AddLayerObject[] {
  return [
    { id: LAYERS.regionFill, type: 'fill', source: REGIONS, filter: selectedRegion(regionId) as never },
    { id: LAYERS.regionLine, type: 'line', source: REGIONS },
    { id: LAYERS.regionSelected, type: 'line', source: REGIONS, filter: selectedRegion(regionId) as never },
    { id: LAYERS.clusters, type: 'circle', source: SCHOOLS, filter: ['has', 'point_count'] },
    {
      id: LAYERS.clusterCount,
      type: 'symbol',
      source: SCHOOLS,
      filter: ['has', 'point_count'],
      layout: {
        'text-field': ['get', 'point_count_abbreviated'],
        'text-font': CLUSTER_FONT,
        'text-size': CLUSTER_TEXT_SIZE,
        'text-allow-overlap': true,
      },
    },
    { id: LAYERS.schools, type: 'circle', source: SCHOOLS, filter: ['!', ['has', 'point_count']] },
  ]
}

/** Colours of the data layers from the current theme; called again when the theme switches. */
export function paintLayers(map: MapLibre, mode: ThemeMode): void {
  for (const [property, value] of Object.entries(BASEMAP_PAINT[mode])) {
    map.setPaintProperty(BASEMAP, property as PaintProperty, value)
  }
  const surface = token('--bg-surface')
  const paint: [string, PaintProperty, unknown][] = [
    [LAYERS.regionFill, 'fill-color', token('--accent')],
    [LAYERS.regionFill, 'fill-opacity', SELECTED_FILL_OPACITY],
    [LAYERS.regionLine, 'line-color', token('--border-strong')],
    [LAYERS.regionLine, 'line-width', 1],
    [LAYERS.regionSelected, 'line-color', token('--accent')],
    [LAYERS.regionSelected, 'line-width', 2],
    [LAYERS.clusters, 'circle-color', surface],
    [LAYERS.clusters, 'circle-stroke-width', 2],
    [LAYERS.clusters, 'circle-stroke-color', worstColor()],
    [LAYERS.clusters, 'circle-radius', ['step', ['get', 'point_count'], ...CLUSTER_RADII]],
    [LAYERS.clusterCount, 'text-color', token('--text-primary')],
    [LAYERS.schools, 'circle-color', statusColor()],
    [LAYERS.schools, 'circle-stroke-width', 2],
    [LAYERS.schools, 'circle-stroke-color', surface],
    [
      LAYERS.schools,
      'circle-radius',
      ['case', ['boolean', ['feature-state', 'hover'], false], MARKER_HOVER_RADIUS, MARKER_RADIUS],
    ],
  ]
  for (const [layer, property, value] of paint) map.setPaintProperty(layer, property, value as PaintValue)
}

export function selectRegion(map: MapLibre, regionId: number | undefined): void {
  map.setFilter(LAYERS.regionFill, selectedRegion(regionId) as never)
  map.setFilter(LAYERS.regionSelected, selectedRegion(regionId) as never)
}

/** Schools with coordinates and a visible status, with the severity their clusters fold. */
export function schoolPoints(schools: SchoolMapCollection, hidden: readonly SchoolStatus[]): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: schools.features.flatMap((school) =>
      school.geometry && !hidden.includes(school.properties.status)
        ? [
            {
              type: 'Feature' as const,
              id: school.id,
              geometry: { type: 'Point' as const, coordinates: [...school.geometry.coordinates] },
              properties: { ...school.properties, severity: SEVERITY[school.properties.status] },
            },
          ]
        : [],
    ),
  }
}

export function regionShapes(regions: RegionMapCollection | undefined): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: (regions?.features ?? []).flatMap((region) =>
      region.geometry
        ? [
            {
              type: 'Feature' as const,
              id: region.id,
              geometry: { type: 'MultiPolygon' as const, coordinates: region.geometry.coordinates },
              properties: region.properties,
            },
          ]
        : [],
    ),
  }
}

/** Box around the schools, or around the districts while no school has coordinates. */
export function boundsOf(...collections: FeatureCollection[]): LngLatBoundsLike | undefined {
  let west = Infinity
  let south = Infinity
  let east = -Infinity
  let north = -Infinity
  const visit = (value: unknown): void => {
    if (!Array.isArray(value)) return
    if (typeof value[0] === 'number' && typeof value[1] === 'number') {
      west = Math.min(west, value[0])
      east = Math.max(east, value[0])
      south = Math.min(south, value[1])
      north = Math.max(north, value[1])
      return
    }
    value.forEach(visit)
  }
  for (const collection of collections) {
    if (collection.features.length === 0) continue
    for (const feature of collection.features) {
      if (feature.geometry.type !== 'GeometryCollection') visit(feature.geometry.coordinates)
    }
    return [west, south, east, north]
  }
  return undefined
}
