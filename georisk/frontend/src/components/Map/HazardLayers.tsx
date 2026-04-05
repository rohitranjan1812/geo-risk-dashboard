import { Eye, EyeOff, Mountain, Droplets, Wind, MapPin, Activity } from 'lucide-react';

interface LayerControlProps {
  visibility: Record<string, boolean>;
  onToggle: (layerId: string) => void;
}

const LAYER_CONFIG = [
  { id: 'properties', label: 'Properties', icon: MapPin, color: '#00e5ff' },
  { id: 'seismic_zones', label: 'Seismic Zones', icon: Mountain, color: '#f44336' },
  { id: 'flood_zones', label: 'Flood Zones', icon: Droplets, color: '#2196f3' },
  { id: 'hurricane_tracks', label: 'Hurricane Tracks', icon: Wind, color: '#ff9800' },
  { id: 'earthquakes', label: 'Recent Earthquakes', icon: Activity, color: '#ffd54f' },
];

export function HazardLayerControls({ visibility, onToggle }: LayerControlProps) {
  return (
    <div className="layer-controls">
      <h3>Map Layers</h3>
      {LAYER_CONFIG.map(({ id, label, icon: Icon, color }) => (
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
