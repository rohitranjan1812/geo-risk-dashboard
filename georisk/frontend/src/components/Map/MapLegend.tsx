import type { ColorByField } from './MapContainer';

const LEGENDS: Record<string, { label: string; gradient: string; min: string; max: string }> = {
  composite_score: { label: 'Composite Risk', gradient: 'linear-gradient(to right, #4caf50, #fdd835, #ff9800, #f44336, #880e4f)', min: '0', max: '100' },
  seismic_score: { label: 'Seismic Score', gradient: 'linear-gradient(to right, #e8eaf6, #f44336, #880e4f)', min: '0', max: '100' },
  flood_score: { label: 'Flood Score', gradient: 'linear-gradient(to right, #e3f2fd, #1976d2, #0d47a1)', min: '0', max: '100' },
  wind_score: { label: 'Wind Score', gradient: 'linear-gradient(to right, #fff3e0, #ff9800, #e65100)', min: '0', max: '100' },
  aal: { label: 'AAL ($)', gradient: 'linear-gradient(to right, #e3f2fd, #ff9800, #f44336, #880e4f)', min: '$0', max: '$200K+' },
  tiv: { label: 'TIV ($)', gradient: 'linear-gradient(to right, #e8f5e9, #fdd835, #ff9800, #f44336)', min: '$100K', max: '$15M+' },
  dominant_peril: { label: 'Dominant Peril', gradient: '', min: '', max: '' },
};

const PERIL_SWATCHES = [
  { color: '#f44336', label: 'Seismic' },
  { color: '#2196f3', label: 'Flood' },
  { color: '#ff9800', label: 'Wind' },
];

interface MapLegendProps {
  colorBy: ColorByField;
  count: number;
  visible: boolean;
}

export function MapLegend({ colorBy, count, visible }: MapLegendProps) {
  if (!visible || count === 0) return null;
  const cfg = LEGENDS[colorBy];
  if (!cfg) return null;

  return (
    <div className="map-legend">
      <div className="legend-title">{cfg.label} <span className="legend-count">({count.toLocaleString()} pts)</span></div>
      {colorBy === 'dominant_peril' ? (
        <div className="legend-swatches">
          {PERIL_SWATCHES.map(s => (
            <div key={s.label} className="legend-swatch">
              <span className="swatch-dot" style={{ backgroundColor: s.color }} />
              <span>{s.label}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="legend-gradient-row">
          <span className="legend-min">{cfg.min}</span>
          <div className="legend-gradient-bar" style={{ background: cfg.gradient }} />
          <span className="legend-max">{cfg.max}</span>
        </div>
      )}
    </div>
  );
}
