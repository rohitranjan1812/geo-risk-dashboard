import { useState, useEffect, useCallback } from 'react';
import { fetchLayerGeoJSON, fetchPropertiesGeoJSON } from '../api/client';

interface LayerState {
  earthquakes: GeoJSON.FeatureCollection | null;
  seismic_zones: GeoJSON.FeatureCollection | null;
  flood_zones: GeoJSON.FeatureCollection | null;
  hurricane_tracks: GeoJSON.FeatureCollection | null;
  properties: GeoJSON.FeatureCollection | null;
}

interface LayerVisibility {
  earthquakes: boolean;
  seismic_zones: boolean;
  flood_zones: boolean;
  hurricane_tracks: boolean;
  properties: boolean;
}

export function useMapLayers() {
  const [layers, setLayers] = useState<LayerState>({
    earthquakes: null,
    seismic_zones: null,
    flood_zones: null,
    hurricane_tracks: null,
    properties: null,
  });

  const [visibility, setVisibility] = useState<LayerVisibility>({
    earthquakes: true,
    seismic_zones: true,
    flood_zones: true,
    hurricane_tracks: true,
    properties: true,
    cat_properties: true,
    aal_heatmap: true,
    portfolio_heat: true,
  });

  const [loading, setLoading] = useState(true);

  const loadLayers = useCallback(async () => {
    setLoading(true);
    try {
      const [earthquakes, seismicZones, floodZones, hurricaneTracks, properties] =
        await Promise.allSettled([
          fetchLayerGeoJSON('earthquakes'),
          fetchLayerGeoJSON('seismic_zones'),
          fetchLayerGeoJSON('flood_zones'),
          fetchLayerGeoJSON('hurricane_tracks'),
          fetchPropertiesGeoJSON(),
        ]);

      setLayers({
        earthquakes: earthquakes.status === 'fulfilled' ? earthquakes.value : null,
        seismic_zones: seismicZones.status === 'fulfilled' ? seismicZones.value : null,
        flood_zones: floodZones.status === 'fulfilled' ? floodZones.value : null,
        hurricane_tracks: hurricaneTracks.status === 'fulfilled' ? hurricaneTracks.value : null,
        properties: properties.status === 'fulfilled' ? properties.value : null,
      });
    } catch (err) {
      console.error('Failed to load map layers:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLayers();
  }, [loadLayers]);

  const toggleLayer = useCallback((layerId: keyof LayerVisibility) => {
    setVisibility(prev => ({ ...prev, [layerId]: !prev[layerId] }));
  }, []);

  return { layers, visibility, toggleLayer, loading, reload: loadLayers };
}
