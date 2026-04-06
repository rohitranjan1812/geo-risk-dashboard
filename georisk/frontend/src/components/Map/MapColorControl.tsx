import { Palette } from 'lucide-react';
import type { ColorByField } from './MapContainer';

const OPTIONS: { value: ColorByField; label: string }[] = [
  { value: 'composite_score', label: 'Composite Risk' },
  { value: 'seismic_score', label: 'Seismic Score' },
  { value: 'flood_score', label: 'Flood Score' },
  { value: 'wind_score', label: 'Wind Score' },
  { value: 'aal', label: 'AAL' },
  { value: 'tiv', label: 'TIV (Exposure)' },
  { value: 'dominant_peril', label: 'Dominant Peril' },
];

interface MapColorControlProps {
  value: ColorByField;
  onChange: (v: ColorByField) => void;
  visible: boolean;
}

export function MapColorControl({ value, onChange, visible }: MapColorControlProps) {
  if (!visible) return null;

  return (
    <div className="map-color-control">
      <div className="color-control-header">
        <Palette size={14} />
        <span>Color by</span>
      </div>
      <select value={value} onChange={e => onChange(e.target.value as ColorByField)} className="color-select">
        {OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}
