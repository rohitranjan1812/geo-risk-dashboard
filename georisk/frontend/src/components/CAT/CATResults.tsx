import { useState, useMemo, memo, useCallback, useEffect } from 'react';
import { Play, Download, Shield, TrendingUp, DollarSign, BarChart3, Target } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, Legend } from 'recharts';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { EPCurveChart } from './EPCurveChart';
import axios from 'axios';
import { getCatExportEpCurveUrl, getCatExportResultsUrl } from '../../api/client';
import { runCATModel } from '../../api/client';

const TIER_COLORS: Record<string, string> = { Low: '#4caf50', Moderate: '#ff9800', High: '#f44336', 'Very High': '#d32f2f', Extreme: '#880e4f' };

interface CATResultsProps {
  portfolioId: string;
  portfolioName: string;
  nProperties: number;
  selectedPropertyId?: number | null;
  selectedIds?: number[];
  onPropertyClick: (id: number) => void;
  onModelComplete?: (portfolioId: string) => void;
  onSessionCreated?: (sessionId: string) => void;
  /** Optional pre-computed model payload, used when loading a historical session
   * so the UI is hydrated without firing another simulation. Accepts either a
   * /cat/run-model response or a /cat/sessions/{id} payload. */
  initialResult?: any | null;
}

export function CATResults({
  portfolioId,
  portfolioName,
  nProperties,
  selectedPropertyId,
  selectedIds,
  onPropertyClick,
  onModelComplete,
  onSessionCreated,
  initialResult,
}: CATResultsProps) {
  const [modelResult, setModelResult] = useState<any>(null);
  const [epData, setEpData] = useState<any>(null);
  const [divData, setDivData] = useState<any>(null);
  const [running, setRunning] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'pricing' | 'diversification' | 'ep'>('overview');
  const [aalMin, setAalMin] = useState('');
  const [aalMax, setAalMax] = useState('');
  const [techMin, setTechMin] = useState('');
  const [techMax, setTechMax] = useState('');
  const [runError, setRunError] = useState<string | null>(null);

  // Hydrate from a loaded session so the full dashboard shows immediately,
  // without requiring the user to click "Run CAT Model" again.
  useEffect(() => {
    if (!initialResult) return;
    // /cat/sessions/{id} returns { session, property_rows, ep_curves, diversification, ... }
    // /cat/run-model returns { session_id, properties, ep_curves, diversification, ... }
    const sessionObj = initialResult.session || null;
    const sid = initialResult.session_id || sessionObj?.session_id || null;
    const runModelShape = Array.isArray(initialResult.properties)
      && initialResult.properties.length > 0
      && initialResult.properties[0]?.total_aal !== undefined;
    const properties = runModelShape
      ? initialResult.properties
      : (Array.isArray(initialResult.property_rows) ? initialResult.property_rows : []);

    setModelResult({
      session_id: sid,
      portfolio_tiv: sessionObj?.portfolio_tiv ?? initialResult.portfolio_tiv ?? 0,
      portfolio_aal: sessionObj?.portfolio_aal ?? initialResult.portfolio_aal ?? 0,
      portfolio_technical_rate_pct: initialResult.portfolio_technical_rate_pct
        ?? (sessionObj && sessionObj.portfolio_tiv ? (sessionObj.portfolio_aal / sessionObj.portfolio_tiv) * 100 : 0),
      portfolio_premium: sessionObj?.portfolio_premium ?? initialResult.portfolio_premium ?? 0,
      properties,
    });
    if (initialResult.ep_curves) setEpData(initialResult.ep_curves);
    if (initialResult.diversification) setDivData(initialResult.diversification);
  }, [initialResult]);

  const runModel = async () => {
    setRunning(true);
    setRunError(null);
    // Clear stale results so the previous run's numbers don't linger while the
    // next simulation is in flight — the old code would keep showing prior
    // values under the spinner, which users interpreted as "stuck".
    setModelResult(null);
    setEpData(null);
    setDivData(null);
    try {
      const data = await runCATModel({
        portfolio_id: portfolioId, n_years: 10000, max_properties: Math.min(nProperties, 200),
      });
      setModelResult(data);
      if (onSessionCreated && data?.session_id) onSessionCreated(String(data.session_id));
      // EP curves and diversification now ship with the /run-model response,
      // eliminating two additional full-simulation round-trips that previously
      // made analysis triggers appear stuck.
      if (data?.ep_curves) setEpData(data.ep_curves);
      if (data?.diversification) setDivData(data.diversification);
      if (onModelComplete) onModelComplete(portfolioId);
    } catch (e) {
      console.error(e);
      if (axios.isAxiosError(e) && e.code === 'ECONNABORTED') {
        setRunError('Request timed out. The simulation may still be running on the server—wait and refresh, or try fewer properties / a smaller year count.');
      } else if (axios.isAxiosError(e) && e.response?.data?.detail) {
        setRunError(String(e.response.data.detail));
      } else {
        setRunError('Simulation failed. Check the browser console and backend logs.');
      }
    } finally {
      setRunning(false);
    }
  };

  const fmt = (v: number) => v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `$${(v / 1e3).toFixed(0)}K` : `$${v.toFixed(0)}`;

  const selectionCount = (selectedIds || []).length;
  const parsedAalMin = aalMin ? parseFloat(aalMin) : null;
  const parsedAalMax = aalMax ? parseFloat(aalMax) : null;
  const parsedTechMin = techMin ? parseFloat(techMin) : null;
  const parsedTechMax = techMax ? parseFloat(techMax) : null;

  const filteredProperties = useMemo(() => {
    if (!modelResult?.properties) return [];
    return modelResult.properties
      .filter((p: any) => {
        if (parsedAalMin != null && p.total_aal < parsedAalMin) return false;
        if (parsedAalMax != null && p.total_aal > parsedAalMax) return false;
        if (parsedTechMin != null && p.technical_rate_pct < parsedTechMin) return false;
        if (parsedTechMax != null && p.technical_rate_pct > parsedTechMax) return false;
        if (selectionCount > 0 && !(selectedIds || []).includes(p.property_id)) return false;
        return true;
      })
      .sort((a: any, b: any) => b.total_aal - a.total_aal);
  }, [modelResult?.properties, parsedAalMin, parsedAalMax, parsedTechMin, parsedTechMax, selectionCount, selectedIds]);

  return (
    <div className="cat-results">
      <div className="cat-results-header">
        <div>
          <h2>{portfolioName}</h2>
          <span className="text-muted">{nProperties} properties | ID: {portfolioId}</span>
          {selectionCount > 0 && (
            <div className="text-muted" style={{ fontSize: 12, marginTop: 4 }}>
              Active selection: {selectionCount.toLocaleString()} point(s)
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {modelResult?.session_id && (
            <>
              <a
                className="btn btn-outline btn-sm"
                href={getCatExportResultsUrl(portfolioId, String(modelResult.session_id))}
                target="_blank"
                rel="noreferrer"
                title="Download account-level results as CSV"
              >
                <Download size={14} /> Results CSV
              </a>
              <a
                className="btn btn-outline btn-sm"
                href={getCatExportEpCurveUrl(portfolioId, String(modelResult.session_id))}
                target="_blank"
                rel="noreferrer"
                title="Download EP curve points as CSV"
              >
                <Download size={14} /> EP CSV
              </a>
            </>
          )}
          <button className="btn btn-primary" onClick={runModel} disabled={running}>
            {running ? <LoadingSpinner size={14} text="Running simulation (often 2–15 min for large portfolios)..." /> : <><Play size={14} /> Run CAT Model</>}
          </button>
        </div>
      </div>

      {runError && <div className="error-banner" style={{ marginBottom: 10 }}>{runError}</div>}

      {modelResult && (
        <>
          <div className="summary-cards" style={{ marginBottom: 12 }}>
            <div className="summary-card"><div className="summary-icon"><DollarSign size={24} /></div><div>
              <span className="summary-value">{fmt(modelResult.portfolio_tiv)}</span><span className="summary-label">Portfolio TIV</span>
            </div></div>
            <div className="summary-card"><div className="summary-icon"><TrendingUp size={24} /></div><div>
              <span className="summary-value">{fmt(modelResult.portfolio_aal)}</span><span className="summary-label">Portfolio AAL</span>
            </div></div>
            <div className="summary-card"><div className="summary-icon"><Target size={24} /></div><div>
              <span className="summary-value">{modelResult.portfolio_technical_rate_pct?.toFixed(3)}%</span><span className="summary-label">Technical Rate</span>
            </div></div>
            <div className="summary-card"><div className="summary-icon"><Shield size={24} /></div><div>
              <span className="summary-value">{fmt(modelResult.portfolio_premium)}</span><span className="summary-label">Total Premium</span>
            </div></div>
          </div>

          <div className="tab-bar">
            {(['overview', 'pricing', 'diversification', 'ep'] as const).map(t => (
              <button key={t} className={`tab ${activeTab === t ? 'active' : ''}`} onClick={() => setActiveTab(t)}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>

          {activeTab === 'overview' && (
            <div className="cat-overview">
              <AALWaterfall properties={modelResult.properties} />
              {divData && (
                <div className="div-summary-row">
                  <div className="summary-card"><div><span className="summary-value text-green">{divData.diversification_pct?.toFixed(1)}%</span><span className="summary-label">Diversification Benefit</span></div></div>
                  <div className="summary-card"><div><span className="summary-value">{fmt(divData.portfolio_pml)}</span><span className="summary-label">Portfolio PML-250</span></div></div>
                  <div className="summary-card"><div><span className="summary-value">{divData.hhi_concentration?.toFixed(4)}</span><span className="summary-label">HHI Concentration</span></div></div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'pricing' && (
            <div className="cat-pricing-tab">
              <div className="filter-grid" style={{ marginBottom: 10 }}>
                <div className="filter-row">
                  <label>AAL Min</label>
                  <input type="number" value={aalMin} onChange={(e) => setAalMin(e.target.value)} placeholder="0" />
                  <label>Max</label>
                  <input type="number" value={aalMax} onChange={(e) => setAalMax(e.target.value)} placeholder="any" />
                </div>
                <div className="filter-row">
                  <label>Tech % Min</label>
                  <input type="number" value={techMin} onChange={(e) => setTechMin(e.target.value)} placeholder="0" />
                  <label>Max</label>
                  <input type="number" value={techMax} onChange={(e) => setTechMax(e.target.value)} placeholder="any" />
                </div>
              </div>
              <div className="table-scroll" style={{ maxHeight: 400 }}>
                <table className="portfolio-table">
                  <thead><tr><th>#</th><th>Property</th><th>TIV</th><th>AAL</th><th>Tech Rate</th><th>Loaded Rate</th><th>Premium</th><th>PML-250</th></tr></thead>
                  <tbody>
                    {filteredProperties.map((p: any, i: number) => (
                        <tr
                          key={p.property_id}
                          onClick={() => onPropertyClick(p.property_id)}
                          style={{ cursor: 'pointer' }}
                          className={selectedPropertyId === p.property_id ? 'row-selected' : ''}
                        >
                          <td>{i + 1}</td>
                          <td>{p.property_id}</td>
                          <td>{fmt(p.tiv)}</td>
                          <td>{fmt(p.total_aal)}</td>
                          <td>{p.technical_rate_pct?.toFixed(3)}%</td>
                          <td>{p.total_loaded_rate_pct?.toFixed(3)}%</td>
                          <td>{fmt(p.total_premium)}</td>
                          <td>{fmt(p.pml_250)}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'diversification' && divData && (
            <div className="cat-div-tab">
              <DiversificationChart data={divData} />
              <div className="table-scroll" style={{ maxHeight: 300, marginTop: 12 }}>
                <table className="portfolio-table">
                  <thead><tr><th>Property</th><th>Standalone PML</th><th>Marginal PML</th><th>Diversified PML</th><th>Benefit</th><th>Share</th></tr></thead>
                  <tbody>
                    {divData.accounts?.slice(0, 50).map((a: any) => (
                      <tr
                        key={a.property_id}
                        onClick={() => onPropertyClick(a.property_id)}
                        style={{ cursor: 'pointer' }}
                        className={selectedPropertyId === a.property_id ? 'row-selected' : ''}
                      >
                        <td>{a.property_id}</td>
                        <td>{fmt(a.standalone_pml)}</td>
                        <td>{fmt(a.marginal_pml)}</td>
                        <td>{fmt(a.diversified_pml)}</td>
                        <td className="text-green">{fmt(a.diversification_benefit)}</td>
                        <td>{a.pml_share_pct?.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'ep' && epData && (
            <div className="cat-ep-tab">
              {['seismic', 'flood', 'wind'].map(peril => (
                epData[peril] && <EPCurveChart key={peril} oep={epData[peril].oep} aep={epData[peril].aep}
                  models={epData[peril].models} peril={peril} height={200} />
              ))}
              {epData.all_perils && <EPCurveChart oep={epData.all_perils.oep} peril="all_perils" height={220} />}
            </div>
          )}
        </>
      )}
    </div>
  );
}


function AALWaterfall({ properties }: { properties: any[] }) {
  const sorted = [...properties].sort((a, b) => b.total_aal - a.total_aal).slice(0, 20);
  const data = sorted.map(p => ({
    name: `#${p.property_id}`,
    aal: p.total_aal,
    tiv: p.tiv,
  }));

  return (
    <div className="chart-container">
      <h4>Top 20 Accounts by AAL</h4>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="name" stroke="#aaa" tick={{ fontSize: 9 }} />
          <YAxis stroke="#aaa" tick={{ fontSize: 10 }} tickFormatter={v => v >= 1e3 ? `$${(v / 1e3).toFixed(0)}K` : `$${v}`} />
          <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333', fontSize: 11 }} />
          <Bar dataKey="aal" name="AAL" radius={[3, 3, 0, 0]}>
            {data.map((_, i) => <Cell key={i} fill={i < 5 ? '#f44336' : i < 10 ? '#ff9800' : '#4caf50'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}


function DiversificationChart({ data }: { data: any }) {
  const accounts = data.accounts?.slice(0, 15) || [];
  const chartData = accounts.map((a: any) => ({
    name: `#${a.property_id}`,
    standalone: a.standalone_pml,
    marginal: a.marginal_pml,
    diversified: a.diversified_pml,
  }));

  return (
    <div className="chart-container">
      <h4>Standalone vs Marginal vs Diversified PML</h4>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="name" stroke="#aaa" tick={{ fontSize: 9 }} />
          <YAxis stroke="#aaa" tick={{ fontSize: 10 }} tickFormatter={v => v >= 1e3 ? `$${(v / 1e3).toFixed(0)}K` : `$${v}`} />
          <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333', fontSize: 11 }} />
          <Legend wrapperStyle={{ fontSize: 10 }} />
          <Bar dataKey="standalone" name="Standalone" fill="#f44336" opacity={0.6} />
          <Bar dataKey="marginal" name="Marginal" fill="#ff9800" />
          <Bar dataKey="diversified" name="Diversified" fill="#4caf50" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
