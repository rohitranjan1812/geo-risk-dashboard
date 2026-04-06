import { Eye, EyeOff, Mountain, Droplets, Wind, MapPin, Activity, Layers, Flame } from 'lucide-react';

interface LayerControlProps {
  visibility: Record<string, boolean>;
  onToggle: (layerId: string) => void;
  showCatLayers?: boolean;
}

const LAYER_CONFIG = [
  { id: 'properties', label: 'Properties', icon: MapPin, color: '#00e5ff' },
  { id: 'seismic_zones', label: 'Seismic Zones', icon: Mountain, color: '#f44336' },
  { id: 'flood_zones', label: 'Flood Zones', icon: Droplets, color: '#2196f3' },
  { id: 'hurricane_tracks', label: 'Hurricane Tracks', icon: Wind, color: '#ff9800' },
  { id: 'earthquakes', label: 'Recent Earthquakes', icon: Activity, color: '#ffd54f' },
];

const CAT_LAYER_CONFIG = [
  { id: 'cat_properties', label: 'CAT Properties', icon: Layers, color: '#7c4dff' },
  { id: 'aal_heatmap', label: 'AAL Heatmap', icon: Flame, color: '#ff5722' },
  { id: 'portfolio_heat', label: 'Portfolio Heat', icon: Flame, color: '#e91e63' },
];

export function HazardLayerControls({ visibility, onToggle, showCatLayers }: LayerControlProps) {
  const allLayers = showCatLayers ? [...LAYER_CONFIG, ...CAT_LAYER_CONFIG] : LAYER_CONFIG;

  return (
    <div className="layer-controls">
      <h3>Map Layers</h3>
      {allLayers.map(({ id, label, icon: Icon, color }) => (
        <button
          key={id}
          className={`layer-toggle ${visibility[id] ? 'active' : ''}`}
          onClick={() => onToggle(id)}
        >
          <span className="layer-indicator" style={{ backgroundColor: visibility[id] ? color : '#555' }} />
          <Icon size={16} />
          <span>{label}</span>
          {visibility[id] ? <Eye size={14} /> : <EyeOff size={14} />}
        </button>
      ))}
    </div>
  );
}
