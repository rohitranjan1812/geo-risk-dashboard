import { useEffect, useMemo, useState } from 'react';
import { BarChart3 } from 'lucide-react';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import { fetchSessionCompare } from '../../api/client';

interface SessionCompareProps {
  sessionIds: string[];
  onBack: () => void;
}

export function SessionCompare({ sessionIds, onBack }: SessionCompareProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const ids = (sessionIds || []).filter(Boolean).slice(0, 3);
    if (ids.length < 2) {
      setData(null);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchSessionCompare(ids)
      .then(d => { if (!cancelled) setData(d); })
      .catch(e => { if (!cancelled) console.error(e); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [sessionIds]);

  const chartData = useMemo(() => {
    const sessions = data?.sessions || [];
    const curves = data?.ep_curves || {};
    if (!sessions.length) return [];

    const pointsByRp: Record<string, any> = {};
    for (const s of sessions) {
      const sid = String(s.session_id);
      const oep = curves?.[sid]?.all_perils?.oep || [];
      for (const pt of oep) {
        const rp = String(pt.return_period);
        if (!pointsByRp[rp]) pointsByRp[rp] = { return_period: Number(pt.return_period) };
        pointsByRp[rp][sid] = Number(pt.loss || 0);
      }
    }
    return Object.values(pointsByRp).sort((a: any, b: any) => a.return_period - b.return_period);
  }, [data]);

  if (loading) return <LoadingSpinner text="Loading comparison..." />;
  if (!data) return <div className="error-banner">Select at least two sessions to compare.</div>;

  const sessions = data.sessions || [];

  return (
    <div className="cat-results">
      <div className="cat-results-header">
        <div>
          <h2><BarChart3 size={18} /> Session Comparison</h2>
          <span className="text-muted">{sessions.length} sessions</span>
        </div>
        <button className="btn btn-outline btn-sm" onClick={onBack}>Back</button>
      </div>

      <div className="summary-cards" style={{ marginBottom: 12 }}>
        {sessions.map((s: any) => (
          <div key={s.session_id} className="summary-card">
            <div>
              <span className="summary-value" style={{ fontSize: 14 }}>{s.name || s.session_id}</span>
              <span className="summary-label">ID: {s.session_id}</span>
              <div className="text-muted" style={{ fontSize: 12, marginTop: 6 }}>
                TIV: ${Number(s.portfolio_tiv || 0).toLocaleString()}<br />
                AAL: ${Number(s.portfolio_aal || 0).toLocaleString()}<br />
                Premium: ${Number(s.portfolio_premium || 0).toLocaleString()}<br />
                Props: {Number(s.n_properties || 0).toLocaleString()}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="chart-container">
        <h4>All-Perils OEP (by return period)</h4>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="return_period" stroke="#aaa" tick={{ fontSize: 10 }} />
            <YAxis stroke="#aaa" tick={{ fontSize: 10 }} />
            <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333', fontSize: 11 }} />
            <Legend wrapperStyle={{ fontSize: 10 }} />
            {sessions.map((s: any, idx: number) => (
              <Line
                key={s.session_id}
                type="monotone"
                dataKey={String(s.session_id)}
                name={s.name || s.session_id}
                strokeWidth={2}
                dot={false}
                stroke={idx === 0 ? '#00e5ff' : idx === 1 ? '#ff9800' : '#f44336'}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

