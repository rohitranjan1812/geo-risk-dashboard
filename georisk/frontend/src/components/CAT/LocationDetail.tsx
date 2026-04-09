import { useState, useEffect, useMemo } from 'react';
import { X, MapPin, Mountain, Droplets, Wind, Shield, TrendingUp } from 'lucide-react';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { MDRChart } from './MDRChart';
import { EPCurveChart } from './EPCurveChart';
import { fetchCatEventSets, fetchCatEventSet, fetchCatLocationDetail, getCatExportEventSetUrl } from '../../api/client';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';

interface LocationDetailProps {
  propertyId: number;
  sessionId?: string | null;
  onClose: () => void;
}

const TIER_COLORS: Record<string, string> = {
  Low: '#4caf50', Moderate: '#ff9800', High: '#f44336', 'Very High': '#d32f2f', Extreme: '#880e4f',
};

export function LocationDetail({ propertyId, sessionId, onClose }: LocationDetailProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [eventSets, setEventSets] = useState<any[]>([]);
  const [eventSetLoading, setEventSetLoading] = useState(false);
  const [selectedEventSetId, setSelectedEventSetId] = useState<string | null>(null);
  const [selectedEventSet, setSelectedEventSet] = useState<any>(null);

  useEffect(() => {
    setLoading(true);
    fetchCatLocationDetail(propertyId, 5000)
      .then(res => setData(res))
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  }, [propertyId]);

  // Event sets (requires sessionId context)
  useEffect(() => {
    setEventSets([]);
    setSelectedEventSetId(null);
    setSelectedEventSet(null);
  }, [propertyId]);

  useEffect(() => {
    // sessionId is optional; without it we cannot scope event sets.
    if (!sessionId) return;
    setEventSetLoading(true);
    fetchCatEventSets(String(sessionId), propertyId)
      .then((rows) => setEventSets(rows || []))
      .catch((e) => console.error(e))
      .finally(() => setEventSetLoading(false));
  }, [propertyId, sessionId]);

  useEffect(() => {
    if (!selectedEventSetId) return;
    setSelectedEventSet(null);
    fetchCatEventSet(selectedEventSetId)
      .then((d) => setSelectedEventSet(d))
      .catch((e) => console.error(e));
  }, [selectedEventSetId]);

  const eventSetsByPeril = useMemo(() => {
    const out: Record<string, any[]> = { seismic: [], flood: [], wind: [] };
    for (const r of eventSets || []) {
      const p = r.peril || 'unknown';
      if (!out[p]) out[p] = [];
      out[p].push(r);
    }
    return out;
  }, [eventSets]);

  const annualLossHistogram = useMemo(() => {
    const annual = (selectedEventSet?.annual_losses || []) as Array<{ year: number; annual_loss: number }>;
    if (!annual || annual.length < 10) return [];
    const values = annual.map((r) => Number(r.annual_loss || 0)).filter((x) => Number.isFinite(x) && x >= 0);
    if (values.length < 10) return [];
    const minV = Math.min(...values);
    const maxV = Math.max(...values);
    if (!(maxV > minV)) return [];
    const bins = 24;
    const width = (maxV - minV) / bins;
    const counts = new Array(bins).fill(0);
    for (const v of values) {
      const idx = Math.min(bins - 1, Math.max(0, Math.floor((v - minV) / width)));
      counts[idx] += 1;
    }
    return counts.map((c, i) => {
      const lo = minV + i * width;
      const hi = lo + width;
      const mid = (lo + hi) / 2;
      return { bin: i + 1, mid, lo, hi, count: c };
    });
  }, [selectedEventSet]);

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

        <div className="hve-card">
          <h3><TrendingUp size={16} /> Event Sets Used</h3>
          {!sessionId ? (
            <div className="text-muted" style={{ fontSize: 12 }}>
              Run or load a CAT session to view persisted event sets for this location.
            </div>
          ) : eventSetLoading ? (
            <LoadingSpinner text="Loading event sets..." />
          ) : (
            <>
              <div className="hve-sub">
                <h4>Choose peril/model</h4>
                <div className="filter-grid" style={{ marginBottom: 8 }}>
                  {(['seismic', 'flood', 'wind'] as const).map(p => (
                    <div key={p} className="filter-row" style={{ alignItems: 'center' }}>
                      <label style={{ minWidth: 60 }}>{p}</label>
                      <select
                        value={eventSetsByPeril[p]?.some((x: any) => x.event_set_id === selectedEventSetId) ? selectedEventSetId || '' : ''}
                        onChange={(e) => setSelectedEventSetId(e.target.value || null)}
                        style={{ width: '100%' }}
                      >
                        <option value="">Select model...</option>
                        {(eventSetsByPeril[p] || []).map((r: any) => (
                          <option key={r.event_set_id} value={r.event_set_id}>
                            {r.model_id} ({r.n_years}y)
                          </option>
                        ))}
                      </select>
                    </div>
                  ))}
                </div>
              </div>

              {selectedEventSet && (
                <div className="hve-sub">
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <h4>Sampled events (top losses + random)</h4>
                    <a
                      className="btn btn-outline btn-sm"
                      href={getCatExportEventSetUrl(String(selectedEventSetId))}
                      target="_blank"
                      rel="noreferrer"
                      title="Download sampled events as CSV"
                    >
                      <TrendingUp size={14} /> Export CSV
                    </a>
                  </div>
                  <div className="hve-grid" style={{ marginBottom: 8 }}>
                    <div><span className="hve-label">Peril</span><span className="hve-value">{selectedEventSet.meta?.peril}</span></div>
                    <div><span className="hve-label">Model</span><span className="hve-value">{selectedEventSet.meta?.model_id}</span></div>
                    <div><span className="hve-label">Seed</span><span className="hve-value">{selectedEventSet.meta?.seed}</span></div>
                    <div><span className="hve-label">Annual years stored</span><span className="hve-value">{selectedEventSet.annual_losses?.length || 0}</span></div>
                    <div><span className="hve-label">Events stored</span><span className="hve-value">{selectedEventSet.events?.length || 0}</span></div>
                  </div>

                  {annualLossHistogram.length > 0 && (
                    <div className="chart-container" style={{ marginBottom: 10 }}>
                      <h4 style={{ marginBottom: 6 }}>Annual Loss Distribution (sample)</h4>
                      <ResponsiveContainer width="100%" height={180}>
                        <BarChart data={annualLossHistogram}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                          <XAxis dataKey="bin" stroke="#aaa" tick={{ fontSize: 10 }} />
                          <YAxis stroke="#aaa" tick={{ fontSize: 10 }} />
                          <Tooltip
                            contentStyle={{ background: '#1a1a2e', border: '1px solid #333', fontSize: 11 }}
                            formatter={(v: any) => [Number(v || 0).toLocaleString(), 'count']}
                            labelFormatter={(l: any) => `bin ${l}`}
                          />
                          <Bar dataKey="count" fill="rgba(0, 229, 255, 0.55)" />
                        </BarChart>
                      </ResponsiveContainer>
                      <div className="text-muted" style={{ fontSize: 11 }}>
                        Histogram built from persisted annual losses for this event set (up to 2,000 years stored).
                      </div>
                    </div>
                  )}

                  <div className="table-scroll" style={{ maxHeight: 260 }}>
                    <table className="portfolio-table">
                      <thead>
                        <tr>
                          <th>Year</th>
                          <th>Event</th>
                          <th>Intensity</th>
                          <th>DR</th>
                          <th>Loss</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(selectedEventSet.events || []).slice(0, 200).map((r: any, i: number) => (
                          <tr key={i}>
                            <td>{r.year}</td>
                            <td>{r.event_index}</td>
                            <td>{r.intensity?.toFixed?.(3)} {r.intensity_unit}</td>
                            <td>{(r.dr * 100).toFixed(2)}%</td>
                            <td>${Number(r.loss || 0).toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
