import { useState, useEffect } from 'react';
import { Database, MapPin, X, Zap } from 'lucide-react';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { fetchSyntheticStats, seedSynthetic } from '../../api/client';
const CONSTRUCTION_TYPES = ['Wood Frame', 'Masonry', 'Reinforced Concrete', 'Steel Frame', 'Concrete Tilt-Up'];
const OCCUPANCIES = ['Residential', 'Commercial', 'Industrial', 'Hospitality', 'Healthcare'];

interface SeedConfigProps {
  bbox: [number, number, number, number] | null;
  onClearBbox: () => void;
  onSeeded: () => void;
}

export function SeedConfig({ bbox, onClearBbox, onSeeded }: SeedConfigProps) {
  const [count, setCount] = useState(100000);
  const [tivMin, setTivMin] = useState(50000);
  const [tivMax, setTivMax] = useState(20000000);
  const [ctypes, setCtypes] = useState<string[]>([]);
  const [occs, setOccs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const [loadingStats, setLoadingStats] = useState(true);

  useEffect(() => {
    fetchSyntheticStats()
      .then(res => setStats(res))
      .catch(() => {})
      .finally(() => setLoadingStats(false));
  }, []);

  const handleSeed = async () => {
    setLoading(true);
    try {
      const body: any = { count, tiv_min: tivMin, tiv_max: tivMax };
      if (bbox) body.bbox = bbox;
      if (ctypes.length > 0) body.construction_types = ctypes;
      if (occs.length > 0) body.occupancies = occs;
      const data = await seedSynthetic(body);
      setStats({ count: data.count });
      onSeeded();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="seed-config">
      <h2><Database size={18} /> Property Seeding</h2>
      <p className="text-muted" style={{ fontSize: 12, marginBottom: 12 }}>
        Generate synthetic properties with configurable parameters. Shift+drag on the map to set a geographic focus area.
      </p>

      {loadingStats ? <LoadingSpinner text="Loading stats..." /> : stats?.count > 0 && (
        <div className="seed-stats-banner">
          <span>{stats.count.toLocaleString()} properties seeded</span>
          <span>TIV: ${(stats.tiv_min / 1e6).toFixed(1)}M - ${(stats.tiv_max / 1e6).toFixed(1)}M (avg ${(stats.tiv_avg / 1e6).toFixed(1)}M)</span>
          <span>Bounds: [{stats.lat_min?.toFixed(1)}, {stats.lon_min?.toFixed(1)}] to [{stats.lat_max?.toFixed(1)}, {stats.lon_max?.toFixed(1)}]</span>
        </div>
      )}

      {bbox && (
        <div className="bbox-badge">
          <MapPin size={14} />
          <span>Focus: [{bbox.map(v => v.toFixed(2)).join(', ')}]</span>
          <button onClick={onClearBbox}><X size={12} /></button>
        </div>
      )}

      <div className="seed-form">
        <div className="filter-row">
          <label>Count</label>
          <input type="number" min={1000} max={2000000} step={10000} value={count} onChange={e => setCount(parseInt(e.target.value) || 100000)} />
        </div>
        <div className="filter-row">
          <label>TIV Min</label>
          <input type="number" value={tivMin} onChange={e => setTivMin(parseFloat(e.target.value) || 50000)} />
          <label>Max</label>
          <input type="number" value={tivMax} onChange={e => setTivMax(parseFloat(e.target.value) || 20000000)} />
        </div>
        <div className="filter-row">
          <label>Construction</label>
          <div className="chip-group">
            {CONSTRUCTION_TYPES.map(c => (
              <button key={c} className={`chip ${ctypes.includes(c) ? 'active' : ''}`}
                onClick={() => setCtypes(prev => prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c])}>{c}</button>
            ))}
          </div>
        </div>
        <div className="filter-row">
          <label>Occupancy</label>
          <div className="chip-group">
            {OCCUPANCIES.map(o => (
              <button key={o} className={`chip ${occs.includes(o) ? 'active' : ''}`}
                onClick={() => setOccs(prev => prev.includes(o) ? prev.filter(x => x !== o) : [...prev, o])}>{o}</button>
            ))}
          </div>
        </div>
      </div>

      <button className="btn btn-primary" onClick={handleSeed} disabled={loading} style={{ width: '100%', marginTop: 12 }}>
        {loading ? <LoadingSpinner size={14} text={`Generating ${count.toLocaleString()} properties...`} /> : <><Zap size={14} /> Generate {count.toLocaleString()} Properties</>}
      </button>
    </div>
  );
}
