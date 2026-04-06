import { useState, useEffect } from 'react';
import { Clock, Trash2, Play, FolderOpen, Plus } from 'lucide-react';
import { LoadingSpinner } from '../common/LoadingSpinner';
import axios from 'axios';

const API = 'http://localhost:8000/api';

interface SessionHistoryProps {
  onLoadSession: (session: any) => void;
  onNewAnalysis: () => void;
}

export function SessionHistory({ onLoadSession, onNewAnalysis }: SessionHistoryProps) {
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    axios.get(`${API}/cat/sessions`)
      .then(res => setSessions(res.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('Delete this session and its results?')) return;
    await axios.delete(`${API}/cat/sessions/${id}`);
    load();
  };

  const handleLoad = async (session: any) => {
    try {
      const { data } = await axios.get(`${API}/cat/sessions/${session.session_id}`);
      onLoadSession(data);
    } catch (e) {
      console.error(e);
    }
  };

  const fmt = (v: number) => v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `$${(v / 1e3).toFixed(0)}K` : `$${v?.toFixed(0) || 0}`;
  const fmtDate = (d: string | null) => d ? new Date(d).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-';

  const STATUS_COLORS: Record<string, string> = { created: '#ff9800', modelled: '#4caf50', priced: '#2196f3' };

  if (loading) return <LoadingSpinner text="Loading sessions..." />;

  return (
    <div className="session-history">
      <div className="session-header">
        <h2><Clock size={18} /> Analysis History</h2>
        <button className="btn btn-primary btn-sm" onClick={onNewAnalysis}><Plus size={14} /> New Analysis</button>
      </div>

      {sessions.length === 0 ? (
        <div className="empty-state">
          <p>No past analyses found. Start a new analysis to build a portfolio and run the CAT model.</p>
          <button className="btn btn-primary" onClick={onNewAnalysis}><Plus size={14} /> Start New Analysis</button>
        </div>
      ) : (
        <div className="session-list">
          {sessions.map(s => (
            <div key={s.session_id} className="session-card" onClick={() => handleLoad(s)}>
              <div className="session-card-top">
                <div className="session-name">
                  <FolderOpen size={14} />
                  <span>{s.name || s.session_id}</span>
                </div>
                <span className="session-status" style={{ color: STATUS_COLORS[s.status] || '#999' }}>
                  {s.status}
                </span>
              </div>
              <div className="session-card-stats">
                <span>{s.n_properties} props</span>
                <span>TIV: {fmt(s.portfolio_tiv)}</span>
                <span>AAL: {fmt(s.portfolio_aal)}</span>
                <span>Premium: {fmt(s.portfolio_premium)}</span>
              </div>
              <div className="session-card-footer">
                <span className="session-date">{fmtDate(s.created_at)}</span>
                <button className="btn-icon" onClick={(e) => handleDelete(s.session_id, e)} title="Delete">
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
