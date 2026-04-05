import { useState } from 'react';
import { Sliders, ArrowRight, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import axios from 'axios';

interface WhatIfScenarioProps {
  latitude: number;
  longitude: number;
  constructionType: string;
}

interface ScenarioResult {
  base_case: { seismic: number; flood: number; wind: number; composite: number; tier: string };
  scenario: { seismic: number; flood: number; wind: number; composite: number; tier: string; weights: Record<string, number> };
  delta: { seismic: number; flood: number; wind: number; composite: number };
}

const TIER_COLORS: Record<string, string> = {
  Low: '#4caf50',
  Moderate: '#ff9800',
  High: '#f44336',
  'Very High': '#d32f2f',
  Extreme: '#880e4f',
};

export function WhatIfScenario({ latitude, longitude, constructionType }: WhatIfScenarioProps) {
  const [seismicWeight, setSeismicWeight] = useState(35);
  const [floodWeight, setFloodWeight] = useState(35);
  const [windWeight, setWindWeight] = useState(30);
  const [pgaOverride, setPgaOverride] = useState<string>('');
  const [floodZoneOverride, setFloodZoneOverride] = useState<string>('');
  const [windProbOverride, setWindProbOverride] = useState<string>('');
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const runScenario = async () => {
    setLoading(true);
    try {
      const payload: any = {
        latitude,
        longitude,
        construction_type: constructionType,
        seismic_weight: seismicWeight / 100,
        flood_weight: floodWeight / 100,
        wind_weight: windWeight / 100,
      };
      if (pgaOverride) payload.pga_override = parseFloat(pgaOverride);
      if (floodZoneOverride) payload.flood_zone_override = floodZoneOverride;
      if (windProbOverride) payload.wind_prob_override = parseFloat(windProbOverride);

      const { data } = await axios.post('http://localhost:8000/api/scenarios/what-if', payload);
      setResult(data);
    } catch (err) {
      console.error('Scenario failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const DeltaIcon = ({ value }: { value: number }) => {
    if (value > 1) return <TrendingUp size={14} className="text-red" />;
    if (value < -1) return <TrendingDown size={14} className="text-green" />;
    return <Minus size={14} />;
  };

  return (
    <div className="whatif-section">
      <button className="whatif-toggle" onClick={() => setExpanded(!expanded)}>
        <Sliders size={16} />
        <span>What-If Scenarios</span>
      </button>

      {expanded && (
        <div className="whatif-controls">
          <div className="weight-sliders">
            <h4>Risk Weights</h4>
            <div className="slider-row">
              <label>Seismic: {seismicWeight}%</label>
              <input type="range" min={0} max={100} value={seismicWeight} onChange={e => setSeismicWeight(+e.target.value)} />
            </div>
            <div className="slider-row">
              <label>Flood: {floodWeight}%</label>
              <input type="range" min={0} max={100} value={floodWeight} onChange={e => setFloodWeight(+e.target.value)} />
            </div>
            <div className="slider-row">
              <label>Wind: {windWeight}%</label>
              <input type="range" min={0} max={100} value={windWeight} onChange={e => setWindWeight(+e.target.value)} />
            </div>
          </div>

          <div className="override-inputs">
            <h4>Override Hazard Values</h4>
            <div className="override-row">
              <label>PGA (g):</label>
              <input type="number" step="0.1" min="0" max="2" placeholder="auto" value={pgaOverride} onChange={e => setPgaOverride(e.target.value)} />
            </div>
            <div className="override-row">
              <label>Flood Zone:</label>
              <select value={floodZoneOverride} onChange={e => setFloodZoneOverride(e.target.value)}>
                <option value="">Auto</option>
                <option value="VE">VE (Coastal High)</option>
                <option value="AE">AE (High w/ BFE)</option>
                <option value="A">A (100-year)</option>
                <option value="X">X (Minimal)</option>
                <option value="D">D (Undetermined)</option>
              </select>
            </div>
            <div className="override-row">
              <label>Wind Prob (%):</label>
              <input type="number" step="5" min="0" max="100" placeholder="auto" value={windProbOverride} onChange={e => setWindProbOverride(e.target.value)} />
            </div>
          </div>

          <button className="btn btn-primary" onClick={runScenario} disabled={loading} style={{ width: '100%', marginTop: 12 }}>
            {loading ? 'Running...' : 'Run Scenario'}
          </button>

          {result && (
            <div className="scenario-result">
              <div className="scenario-comparison">
                <div className="scenario-col">
                  <h4>Base Case</h4>
                  <span className="scenario-score" style={{ color: TIER_COLORS[result.base_case.tier] }}>
                    {result.base_case.composite}
                  </span>
                  <span className="scenario-tier">{result.base_case.tier}</span>
                </div>
                <ArrowRight size={24} />
                <div className="scenario-col">
                  <h4>Scenario</h4>
                  <span className="scenario-score" style={{ color: TIER_COLORS[result.scenario.tier] }}>
                    {result.scenario.composite}
                  </span>
                  <span className="scenario-tier">{result.scenario.tier}</span>
                </div>
              </div>

              <div className="delta-grid">
                {(['seismic', 'flood', 'wind', 'composite'] as const).map(peril => (
                  <div key={peril} className="delta-item">
                    <span className="delta-label">{peril.charAt(0).toUpperCase() + peril.slice(1)}</span>
                    <DeltaIcon value={result.delta[peril]} />
                    <span className={`delta-value ${result.delta[peril] > 0 ? 'text-red' : result.delta[peril] < 0 ? 'text-green' : ''}`}>
                      {result.delta[peril] > 0 ? '+' : ''}{result.delta[peril]}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
