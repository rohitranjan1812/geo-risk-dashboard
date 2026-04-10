import { useRef, useCallback, useEffect, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { Property } from '../../types';

const STYLE_URL = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';
const LIGHT_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

export type ColorByField = 'composite_score' | 'seismic_score' | 'flood_score' | 'wind_score' | 'aal' | 'tiv' | 'dominant_peril';

const COLOR_EXPRESSIONS: Record<string, any> = {
  composite_score: ['interpolate', ['linear'], ['get', 'composite_score'], 0, '#4caf50', 30, '#fdd835', 60, '#ff9800', 80, '#f44336', 100, '#880e4f'],
  seismic_score: ['interpolate', ['linear'], ['get', 'seismic_score'], 0, '#e8eaf6', 50, '#f44336', 100, '#880e4f'],
  flood_score: ['interpolate', ['linear'], ['get', 'flood_score'], 0, '#e3f2fd', 50, '#1976d2', 100, '#0d47a1'],
  wind_score: ['interpolate', ['linear'], ['get', 'wind_score'], 0, '#fff3e0', 50, '#ff9800', 100, '#e65100'],
  aal: ['interpolate', ['linear'], ['get', 'aal'], 0, '#e3f2fd', 5000, '#ff9800', 50000, '#f44336', 200000, '#880e4f'],
  tiv: ['interpolate', ['linear'], ['get', 'tiv'], 100000, '#e8f5e9', 1000000, '#fdd835', 5000000, '#ff9800', 15000000, '#f44336'],
  dominant_peril: ['match', ['get', 'dominant_peril'], 'seismic', '#f44336', 'flood', '#2196f3', 'wind', '#ff9800', '#999999'],
};

interface MapContainerProps {
  layers: {
    earthquakes: GeoJSON.FeatureCollection | null;
    seismic_zones: GeoJSON.FeatureCollection | null;
    flood_zones: GeoJSON.FeatureCollection | null;
    hurricane_tracks: GeoJSON.FeatureCollection | null;
    properties: GeoJSON.FeatureCollection | null;
  };
  visibility: Record<string, boolean>;
  onPropertyClick?: (property: Property) => void;
  highlightCoords?: [number, number] | null;
  portfolioGeoJSON?: GeoJSON.FeatureCollection | null;
  isDark: boolean;
  enableBboxSelect?: boolean;
  onBboxSelect?: (bbox: [number, number, number, number]) => void;
  catPropertiesGeoJSON?: GeoJSON.FeatureCollection | null;
  colorByField?: ColorByField;
  onCatPropertyClick?: (propertyId: number, coords?: [number, number]) => void;
  aalHeatmapGeoJSON?: GeoJSON.FeatureCollection | null;
  selectedCatPropertyId?: number | null;
  selectedCatCoords?: [number, number] | null;
  selectedCatIds?: number[];
  onCatBoxSelectIds?: (ids: number[], bbox: [number, number, number, number]) => void;
}

export function MapContainer({
  layers,
  visibility,
  onPropertyClick,
  highlightCoords,
  portfolioGeoJSON,
  isDark,
  enableBboxSelect,
  onBboxSelect,
  catPropertiesGeoJSON,
  colorByField = 'composite_score',
  onCatPropertyClick,
  aalHeatmapGeoJSON,
  selectedCatPropertyId = null,
  selectedCatCoords = null,
  selectedCatIds = [],
  onCatBoxSelectIds,
}: MapContainerProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  // Stable refs for callbacks to avoid stale closures in map event handlers.
  const onPropertyClickRef = useRef(onPropertyClick);
  onPropertyClickRef.current = onPropertyClick;
  const onCatPropertyClickRef = useRef(onCatPropertyClick);
  onCatPropertyClickRef.current = onCatPropertyClick;
  const onBboxSelectRef = useRef(onBboxSelect);
  onBboxSelectRef.current = onBboxSelect;
  const onCatBoxSelectIdsRef = useRef(onCatBoxSelectIds);
  onCatBoxSelectIdsRef.current = onCatBoxSelectIds;

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    const m = new maplibregl.Map({
      container: mapContainer.current,
      style: isDark ? STYLE_URL : LIGHT_STYLE,
      center: [-98, 38],
      zoom: 3.5,
      attributionControl: false,
    });

    m.addControl(new maplibregl.NavigationControl(), 'top-right');
    m.addControl(new maplibregl.ScaleControl(), 'bottom-left');

    m.on('load', () => {
      setMapLoaded(true);
    });

    map.current = m;

    return () => {
      m.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m || !mapLoaded) return;
    // Changing style clears sources/layers; force effects to re-run.
    setMapLoaded(false);
    m.setStyle(isDark ? STYLE_URL : LIGHT_STYLE);
    m.once('style.load', () => setMapLoaded(true));
  }, [isDark]);

  const addOrUpdateSource = useCallback(
    (sourceId: string, data: GeoJSON.FeatureCollection) => {
      const m = map.current;
      if (!m) return;
      const source = m.getSource(sourceId) as maplibregl.GeoJSONSource | undefined;
      if (source) {
        source.setData(data);
      } else {
        m.addSource(sourceId, { type: 'geojson', data });
      }
    },
    []
  );

  useEffect(() => {
    const m = map.current;
    if (!m || !mapLoaded) return;

    if (layers.seismic_zones) {
      addOrUpdateSource('seismic-zones', layers.seismic_zones);
      if (!m.getLayer('seismic-zones-fill')) {
        m.addLayer({
          id: 'seismic-zones-fill',
          type: 'fill',
          source: 'seismic-zones',
          paint: {
            'fill-color': ['get', 'color'],
            'fill-opacity': 0.25,
          },
        });
        m.addLayer({
          id: 'seismic-zones-outline',
          type: 'line',
          source: 'seismic-zones',
          paint: { 'line-color': ['get', 'color'], 'line-width': 1.5 },
        });
      }
    }

    if (layers.flood_zones) {
      addOrUpdateSource('flood-zones', layers.flood_zones);
      if (!m.getLayer('flood-zones-fill')) {
        m.addLayer({
          id: 'flood-zones-fill',
          type: 'fill',
          source: 'flood-zones',
          paint: {
            'fill-color': ['coalesce', ['get', 'color'], '#1976d2'],
            'fill-opacity': 0.25,
          },
        });
        m.addLayer({
          id: 'flood-zones-outline',
          type: 'line',
          source: 'flood-zones',
          paint: { 'line-color': ['coalesce', ['get', 'color'], '#1976d2'], 'line-width': 1.5 },
        });
      }
    }

    if (layers.hurricane_tracks) {
      addOrUpdateSource('hurricane-tracks', layers.hurricane_tracks);
      if (!m.getLayer('hurricane-tracks-line')) {
        m.addLayer({
          id: 'hurricane-tracks-line',
          type: 'line',
          source: 'hurricane-tracks',
          paint: {
            'line-color': ['coalesce', ['get', 'color'], '#ff9800'],
            'line-width': 2,
            'line-opacity': 0.8,
          },
        });
      }
    }

    if (layers.earthquakes) {
      addOrUpdateSource('earthquakes', layers.earthquakes);
      if (!m.getLayer('earthquakes-circle')) {
        m.addLayer({
          id: 'earthquakes-circle',
          type: 'circle',
          source: 'earthquakes',
          paint: {
            'circle-radius': [
              'interpolate', ['linear'], ['get', 'mag'],
              2, 3, 5, 8, 7, 16, 9, 30,
            ],
            'circle-color': [
              'interpolate', ['linear'], ['get', 'mag'],
              2, '#ffd54f', 4, '#ff9800', 6, '#f44336', 8, '#880e4f',
            ],
            'circle-opacity': 0.7,
            'circle-stroke-width': 1,
            'circle-stroke-color': '#fff',
          },
        });
      }
    }

    if (layers.properties) {
      addOrUpdateSource('properties', layers.properties);
      if (!m.getLayer('properties-circle')) {
        m.addLayer({
          id: 'properties-circle',
          type: 'circle',
          source: 'properties',
          paint: {
            'circle-radius': 8,
            'circle-color': '#00e5ff',
            'circle-stroke-width': 2,
            'circle-stroke-color': '#fff',
          },
        });
        m.addLayer({
          id: 'properties-label',
          type: 'symbol',
          source: 'properties',
          layout: {
            'text-field': ['get', 'name'],
            'text-size': 11,
            'text-offset': [0, 1.5],
            'text-anchor': 'top',
          },
          paint: {
            'text-color': '#fff',
            'text-halo-color': '#000',
            'text-halo-width': 1,
          },
        });

        m.on('click', 'properties-circle', (e) => {
          if (e.features && e.features[0] && onPropertyClickRef.current) {
            const props = e.features[0].properties;
            if (!props) return;
            const geom = e.features[0].geometry;
            if (geom.type !== 'Point') return;
            onPropertyClickRef.current({
              id: props.id,
              name: props.name,
              address: props.address,
              latitude: geom.coordinates[1],
              longitude: geom.coordinates[0],
              tiv: props.tiv || 0,
              construction_type: props.construction_type || '',
              occupancy: props.occupancy || '',
              year_built: null,
              stories: 1,
            });
          }
        });

        m.on('mouseenter', 'properties-circle', () => {
          m.getCanvas().style.cursor = 'pointer';
        });
        m.on('mouseleave', 'properties-circle', () => {
          m.getCanvas().style.cursor = '';
        });
      }
    }

    if (portfolioGeoJSON) {
      addOrUpdateSource('portfolio', portfolioGeoJSON);
      if (!m.getLayer('portfolio-heat')) {
        m.addLayer({
          id: 'portfolio-heat',
          type: 'heatmap',
          source: 'portfolio',
          paint: {
            'heatmap-weight': ['interpolate', ['linear'], ['get', 'tiv'], 0, 0, 10000000, 1],
            'heatmap-intensity': 1,
            'heatmap-radius': 30,
            'heatmap-opacity': 0.7,
            'heatmap-color': [
              'interpolate', ['linear'], ['heatmap-density'],
              0, 'rgba(0,0,0,0)', 0.2, '#2196f3', 0.4, '#4caf50',
              0.6, '#ff9800', 0.8, '#f44336', 1, '#880e4f',
            ],
          },
        });
      }
    }
  }, [layers, mapLoaded, portfolioGeoJSON, addOrUpdateSource]);

  useEffect(() => {
    const m = map.current;
    if (!m || !mapLoaded) return;

    const layerMap: Record<string, string[]> = {
      earthquakes: ['earthquakes-circle'],
      seismic_zones: ['seismic-zones-fill', 'seismic-zones-outline'],
      flood_zones: ['flood-zones-fill', 'flood-zones-outline'],
      hurricane_tracks: ['hurricane-tracks-line'],
      properties: ['properties-circle', 'properties-label'],
      cat_properties: ['cat-properties-circle'],
      aal_heatmap: ['aal-heatmap-layer'],
      portfolio_heat: ['portfolio-heat'],
    };

    for (const [key, layerIds] of Object.entries(layerMap)) {
      const vis = visibility[key] ? 'visible' : 'none';
      for (const lid of layerIds) {
        if (m.getLayer(lid)) {
          m.setLayoutProperty(lid, 'visibility', vis);
        }
      }
    }
  }, [visibility, mapLoaded]);

  useEffect(() => {
    const m = map.current;
    if (!m || !highlightCoords) return;

    const el = document.createElement('div');
    el.className = 'highlight-marker';

    const marker = new maplibregl.Marker({ element: el })
      .setLngLat(highlightCoords)
      .addTo(m);

    m.flyTo({ center: highlightCoords, zoom: 10, duration: 1500 });

    return () => { marker.remove(); };
  }, [highlightCoords]);

  useEffect(() => {
    const m = map.current;
    if (!m || !mapLoaded) return;

    if (catPropertiesGeoJSON) {
      addOrUpdateSource('cat-properties', catPropertiesGeoJSON);
      if (!m.getLayer('cat-properties-circle')) {
        m.addLayer({
          id: 'cat-properties-circle',
          type: 'circle',
          source: 'cat-properties',
          paint: {
            'circle-radius': ['interpolate', ['linear'], ['get', 'tiv'], 100000, 4, 1000000, 7, 10000000, 14],
            'circle-color': COLOR_EXPRESSIONS[colorByField] || COLOR_EXPRESSIONS.composite_score,
            'circle-opacity': 0.85,
            'circle-stroke-width': 1,
            'circle-stroke-color': '#fff',
          },
        });

        m.on('click', 'cat-properties-circle', (e) => {
          if (e.features?.[0] && onCatPropertyClickRef.current) {
            const f = e.features[0];
            const id = f.properties?.id;
            const coords = (f.geometry as GeoJSON.Point).coordinates;
            if (typeof id === 'number' && Array.isArray(coords) && coords.length >= 2) {
              onCatPropertyClickRef.current(id, [coords[0], coords[1]]);
            } else if (typeof id === 'number') {
              onCatPropertyClickRef.current(id);
            }
          }
        });
        m.on('mouseenter', 'cat-properties-circle', () => { m.getCanvas().style.cursor = 'pointer'; });
        m.on('mouseleave', 'cat-properties-circle', () => { m.getCanvas().style.cursor = ''; });
      } else {
        m.setPaintProperty('cat-properties-circle', 'circle-color',
          COLOR_EXPRESSIONS[colorByField] || COLOR_EXPRESSIONS.composite_score);
      }
    } else {
      if (m.getLayer('cat-properties-circle')) {
        m.removeLayer('cat-properties-circle');
      }
      if (m.getLayer('cat-properties-selected')) {
        m.removeLayer('cat-properties-selected');
      }
      if (m.getSource('cat-properties')) {
        m.removeSource('cat-properties');
      }
    }
  }, [catPropertiesGeoJSON, colorByField, mapLoaded, addOrUpdateSource]);

  useEffect(() => {
    const m = map.current;
    if (!m || !mapLoaded) return;
    if (!catPropertiesGeoJSON) return;
    if (!m.getLayer('cat-properties-circle')) return;

    const hasSelected = typeof selectedCatPropertyId === 'number';

    if (hasSelected) {
      if (!m.getLayer('cat-properties-selected')) {
        // Put selected ring above base layer.
        m.addLayer({
          id: 'cat-properties-selected',
          type: 'circle',
          source: 'cat-properties',
          filter: ['==', ['get', 'id'], selectedCatPropertyId],
          paint: {
            'circle-radius': ['+', ['interpolate', ['linear'], ['get', 'tiv'], 100000, 4, 1000000, 7, 10000000, 14], 4],
            'circle-color': 'rgba(0,0,0,0)',
            'circle-stroke-width': 3,
            'circle-stroke-color': '#00e5ff',
            'circle-opacity': 1,
          },
        });
      } else {
        m.setFilter('cat-properties-selected', ['==', ['get', 'id'], selectedCatPropertyId]);
      }
    } else if (m.getLayer('cat-properties-selected')) {
      m.removeLayer('cat-properties-selected');
    }
  }, [catPropertiesGeoJSON, mapLoaded, selectedCatPropertyId]);

  useEffect(() => {
    const m = map.current;
    if (!m || !mapLoaded) return;
    if (!m.getLayer('cat-properties-circle')) return;

    const ids = (selectedCatIds || []).filter((x) => typeof x === 'number');
    if (ids.length === 0) {
      m.setPaintProperty('cat-properties-circle', 'circle-opacity', 0.85);
      return;
    }
    // Dim non-selected points when we have a multi-selection.
    m.setPaintProperty('cat-properties-circle', 'circle-opacity', [
      'case',
      ['in', ['get', 'id'], ['literal', ids]],
      0.95,
      0.18,
    ]);
  }, [mapLoaded, selectedCatIds]);

  useEffect(() => {
    const m = map.current;
    if (!m || !selectedCatCoords) return;
    m.flyTo({ center: selectedCatCoords, zoom: 10, duration: 900 });
  }, [selectedCatCoords]);

  useEffect(() => {
    const m = map.current;
    if (!m || !mapLoaded) return;

    if (aalHeatmapGeoJSON) {
      addOrUpdateSource('aal-heatmap', aalHeatmapGeoJSON);
      if (!m.getLayer('aal-heatmap-layer')) {
        m.addLayer({
          id: 'aal-heatmap-layer',
          type: 'heatmap',
          source: 'aal-heatmap',
          paint: {
            'heatmap-weight': ['interpolate', ['linear'], ['get', 'aal'], 0, 0, 100000, 1],
            'heatmap-intensity': 0.8,
            'heatmap-radius': 25,
            'heatmap-opacity': 0.6,
            'heatmap-color': [
              'interpolate', ['linear'], ['heatmap-density'],
              0, 'rgba(0,0,0,0)', 0.2, '#2196f3', 0.4, '#4caf50',
              0.6, '#fdd835', 0.8, '#f44336', 1, '#880e4f',
            ],
          },
        });
      }
    } else {
      if (m.getLayer('aal-heatmap-layer')) m.removeLayer('aal-heatmap-layer');
      if (m.getSource('aal-heatmap')) m.removeSource('aal-heatmap');
    }
  }, [aalHeatmapGeoJSON, mapLoaded, addOrUpdateSource]);

  useEffect(() => {
    const m = map.current;
    if (!m || !enableBboxSelect) return;

    let start: maplibregl.LngLat | null = null;
    let box: HTMLDivElement | null = null;

    const onMouseDown = (e: maplibregl.MapMouseEvent & { originalEvent: MouseEvent }) => {
      if (!e.originalEvent.shiftKey) return;
      e.originalEvent.preventDefault();
      m.dragPan.disable();
      start = e.lngLat;
      box = document.createElement('div');
      box.className = 'bbox-selection-box';
      box.style.position = 'absolute';
      m.getContainer().appendChild(box);

      const onMouseMove = (ev: maplibregl.MapMouseEvent & { originalEvent: MouseEvent }) => {
        if (!start || !box) return;
        const startPt = m.project(start);
        const curPt = m.project(ev.lngLat);
        const left = Math.min(startPt.x, curPt.x);
        const top = Math.min(startPt.y, curPt.y);
        box.style.left = left + 'px';
        box.style.top = top + 'px';
        box.style.width = Math.abs(curPt.x - startPt.x) + 'px';
        box.style.height = Math.abs(curPt.y - startPt.y) + 'px';
      };

      const onMouseUp = (ev: maplibregl.MapMouseEvent) => {
        m.dragPan.enable();
        const startPt = start ? m.project(start) : null;
        const curPt = m.project(ev.lngLat);
        if (start && onBboxSelectRef.current) {
          const west = Math.min(start.lng, ev.lngLat.lng);
          const south = Math.min(start.lat, ev.lngLat.lat);
          const east = Math.max(start.lng, ev.lngLat.lng);
          const north = Math.max(start.lat, ev.lngLat.lat);
          if (Math.abs(east - west) > 0.01 && Math.abs(north - south) > 0.01) {
            const bboxLngLat: [number, number, number, number] = [west, south, east, north];
            onBboxSelectRef.current(bboxLngLat);

            if (startPt && onCatBoxSelectIdsRef.current && m.getLayer('cat-properties-circle')) {
              const minX = Math.min(startPt.x, curPt.x);
              const maxX = Math.max(startPt.x, curPt.x);
              const minY = Math.min(startPt.y, curPt.y);
              const maxY = Math.max(startPt.y, curPt.y);
              const feats = m.queryRenderedFeatures(
                [
                  [minX, minY],
                  [maxX, maxY],
                ],
                { layers: ['cat-properties-circle'] }
              ) as any[];
              const ids: number[] = [];
              const seen = new Set<number>();
              for (const f of feats || []) {
                const id = f?.properties?.id;
                if (typeof id === 'number' && !seen.has(id)) {
                  seen.add(id);
                  ids.push(id);
                }
              }
              onCatBoxSelectIdsRef.current(ids, bboxLngLat);
            }
          }
        }
        if (box) { box.remove(); box = null; }
        start = null;
        m.off('mousemove', onMouseMove as any);
        m.off('mouseup', onMouseUp as any);
      };

      m.on('mousemove', onMouseMove as any);
      m.on('mouseup', onMouseUp as any);
    };

    m.on('mousedown', onMouseDown as any);
    return () => { m.off('mousedown', onMouseDown as any); };
  }, [enableBboxSelect, mapLoaded]);

  return <div ref={mapContainer} className="map-container" />;
}
