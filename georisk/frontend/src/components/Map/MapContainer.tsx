import { useRef, useCallback, useEffect, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import type { Property } from '../../types';

const STYLE_URL = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';
const LIGHT_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

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
}

export function MapContainer({
  layers,
  visibility,
  onPropertyClick,
  highlightCoords,
  portfolioGeoJSON,
  isDark,
}: MapContainerProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

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
    if (!map.current || !mapLoaded) return;
    map.current.setStyle(isDark ? STYLE_URL : LIGHT_STYLE);
    map.current.once('style.load', () => setMapLoaded(true));
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
          if (e.features && e.features[0] && onPropertyClick) {
            const props = e.features[0].properties;
            onPropertyClick({
              id: props?.id,
              name: props?.name,
              address: props?.address,
              latitude: (e.features[0].geometry as GeoJSON.Point).coordinates[1],
              longitude: (e.features[0].geometry as GeoJSON.Point).coordinates[0],
              tiv: props?.tiv || 0,
              construction_type: props?.construction_type || '',
              occupancy: props?.occupancy || '',
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
  }, [layers, mapLoaded, portfolioGeoJSON, addOrUpdateSource, onPropertyClick]);

  useEffect(() => {
    const m = map.current;
    if (!m || !mapLoaded) return;

    const layerMap: Record<string, string[]> = {
      earthquakes: ['earthquakes-circle'],
      seismic_zones: ['seismic-zones-fill', 'seismic-zones-outline'],
      flood_zones: ['flood-zones-fill', 'flood-zones-outline'],
      hurricane_tracks: ['hurricane-tracks-line'],
      properties: ['properties-circle', 'properties-label'],
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

  return <div ref={mapContainer} className="map-container" />;
}
