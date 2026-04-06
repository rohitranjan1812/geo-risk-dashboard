import { useState, useEffect } from 'react';
import { X, MapPin, Mountain, Droplets, Wind, Shield, DollarSign, TrendingUp } from 'lucide-react';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { MDRChart } from './MDRChart';
import { EPCurveChart } from './EPCurveChart';
import axios from 'axios';

interface LocationDetailProps {
  propertyId: number;
  onClose: () => void;
}

const TIER_COLORS: Record<string, string> = {
  Low: '#4caf50', Moderate: '#ff9800', High: '#f44336', 'Very High': '#d32f2f', Extreme: '#880e4f',
};

export function LocationDetail({ propertyId, onClose }: LocationDetailProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    axios.get(`http://localhost:8000/api/cat/location-detail/${propertyId}?n_years=5000`)
      .then(res => setData(res.data))
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  }, [propertyId]);

  if (loading) return <LoadingSpinner text="Running stochastic model..." />;
  if (!data) return <div className="error-banner">Failed to load location detail</div>;

  const { exposure, hazard, vulnerability, loss, ep_curves } = data;
  const totalScore = loss.technical_rate_pct || 0;
  const tier = totalScore < 0.5 ? 'Low' : totalScore < 1.5 ? 'Moderate' : totalScore < 3 ? 'High' : totalScore < 5 ? 'Very High' : 'Extreme';

  return (
    <div className="location-detail">
      <div className="scorecard-header">
        <h2>Location Risk Detail</h2>
        <button className="btn-icon" onClick={onClose}><X size={20} /></button>
      </div>

      <div className="hve-section">
        <div className="hve-card exposure-card">
          <h3><MapPin size={16} /> Exposure</h3>
          <div className="hve-grid">
            <div><span className="hve-label">TIV</span><span className="hve-value">${(exposure.tiv / 1e6).toFixed(2)}M</span></div>
            <div><span className="hve-label">Construction</span><span className="hve-value">{exposure.construction_type}</span></div>
            <div><span className="hve-label">Occupancy</span><span className="hve-value">{exposure.occupancy}</span></div>
            <div><span className="hve-label">Stories</span><span className="hve-value">{exposure.stories}</span></div>
            <div><span className="hve-label">Year Built</span><span className="hve-value">{exposure.year_built || 'N/A'}</span></div>
            <div><span className="hve-label">Coords</span><span className="hve-value">{exposure.latitude.toFixed(4)}, {exposure.longitude.toFixed(4)}</span></div>
          </div>
        </div>

        {(['seismic', 'flood', 'wind'] as const).map(peril => {
          const h = hazard[peril];
          const v = vulnerability[peril];
          const pb = loss.peril_breakdown?.[peril];
          const icon = peril === 'seismic' ? Mountain : peril === 'flood' ? Droplets : Wind;
          const Icon = icon;
          const epData = ep_curves?.[peril];
          const perilColor = peril === 'seismic' ? '#f44336' : peril === 'flood' ? '#2196f3' : '#ff9800';

          return (
            <div key={peril} className="hve-card" style={{ borderLeftColor: perilColor }}>
              <h3><Icon size={16} /> {peril.charAt(0).toUpperCase() + peril.slice(1)}</h3>

              <div className="hve-sub">
                <h4>Hazard</h4>
                <div className="hve-grid">
                  {peril === 'seismic' && <div><span className="hve-label">PGA</span><span className="hve-value">{h.pga_g?.toFixed(3)}g</span></div>}
                  {peril === 'flood' && <>
                    <div><span className="hve-label">Zone</span><span className="hve-value">{h.zone}</span></div>
                    <div><span className="hve-label">Est. Depth</span><span className="hve-value">{h.estimated_depth_ft?.toFixed(1)} ft</span></div>
                  </>}
                  {peril === 'wind' && <>
                    <div><span className="hve-label">Wind Prob</span><span className="hve-value">{h.max_wind_prob?.toFixed(0)}%</span></div>
                    <div><span className="hve-label">Est. Speed</span><span className="hve-value">{h.estimated_speed_mph?.toFixed(0)} mph</span></div>
                  </>}
                </div>
              </div>

              <div className="hve-sub">
                <h4>Vulnerability (MDR)</h4>
                <div className="hve-grid">
                  <div><span className="hve-label">Mean DR</span><span className="hve-value">{(v.mdr.mean_dr * 100).toFixed(2)}%</span></div>
                  <div><span className="hve-label">Sigma</span><span className="hve-value">{(v.mdr.sigma_dr * 100).toFixed(2)}%</span></div>
                </div>
                <MDRChart curve={v.curve} operatingPoint={{ intensity: v.mdr.intensity, mean_dr: v.mdr.mean_dr }}
                  peril={peril} intensityUnit={v.mdr.intensity_unit} />
              </div>

              <div className="hve-sub">
                <h4>Loss / Pricing</h4>
                <div className="hve-grid">
                  <div><span className="hve-label">AAL</span><span className="hve-value">${pb?.aal?.toLocaleString()}</span></div>
                  <div><span className="hve-label">Tech Rate</span><span className="hve-value">{pb?.technical_rate_pct?.toFixed(3)}%</span></div>
                  <div><span className="hve-label">Loaded Rate</span><span className="hve-value">{pb?.loaded_rate_pct?.toFixed(3)}%</span></div>
                  <div><span className="hve-label">Premium</span><span className="hve-value">${pb?.premium?.toLocaleString()}</span></div>
                  <div><span className="hve-label">OEP-250</span><span className="hve-value">${pb?.oep_250?.toLocaleString()}</span></div>
                </div>
              </div>

              {epData && <EPCurveChart oep={epData.oep} aep={epData.aep} models={epData.models} peril={peril} height={180} />}
            </div>
          );
        })}

        <div className="hve-card composite-card">
          <h3><Shield size={16} /> Composite</h3>
          <div className="composite-banner" style={{ borderColor: TIER_COLORS[tier] }}>
            <div className="composite-big">
              <span className="composite-rate" style={{ color: TIER_COLORS[tier] }}>{loss.technical_rate_pct?.toFixed(3)}%</span>
              <span className="composite-label">Technical Rate</span>
            </div>
            <div className="composite-big">
              <span className="composite-rate">{loss.total_loaded_rate_pct?.toFixed(3)}%</span>
              <span className="composite-label">Loaded Rate</span>
            </div>
            <div className="composite-big">
              <span className="composite-rate">${loss.total_premium?.toLocaleString()}</span>
              <span className="composite-label">Total Premium</span>
            </div>
          </div>
          <div className="hve-grid" style={{ marginTop: 8 }}>
            <div><span className="hve-label">Total AAL</span><span className="hve-value">${loss.total_aal?.toLocaleString()}</span></div>
            <div><span className="hve-label">Risk Load</span><span className="hve-value">{(loss.total_risk_load_factor * 100)?.toFixed(1)}%</span></div>
            <div><span className="hve-label">PML-250</span><span className="hve-value">${loss.pml?.['250']?.toLocaleString()}</span></div>
            <div><span className="hve-label">PML-500</span><span className="hve-value">${loss.pml?.['500']?.toLocaleString()}</span></div>
          </div>
          {ep_curves?.all_perils && <EPCurveChart oep={ep_curves.all_perils.oep} peril="all_perils" height={180} />}
        </div>
      </div>
    </div>
  );
}
