import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, CheckCircle, AlertCircle, Clock } from 'lucide-react';
import type { ScrapeStatus } from '../../types';
import { fetchDataCatalog, triggerScrape } from '../../api/client';
import { LoadingSpinner } from '../common/LoadingSpinner';

export function StatusPanel() {
  const [catalog, setCatalog] = useState<ScrapeStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [scraping, setScraping] = useState<string | null>(null);

  const loadCatalog = useCallback(async () => {
    try {
      const data = await fetchDataCatalog();
      setCatalog(data);
    } catch (err) {
      console.error('Failed to load catalog:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCatalog();
    const interval = setInterval(loadCatalog, 30000);
    return () => clearInterval(interval);
  }, [loadCatalog]);

  const handleScrape = async (source: string) => {
    setScraping(source);
    try {
      await triggerScrape(source);
      await loadCatalog();
    } catch (err) {
      console.error('Scrape failed:', err);
    } finally {
      setScraping(null);
    }
  };

  const formatTime = (dateStr: string | null) => {
    if (!dateStr) return 'Never';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHrs = Math.floor(diffMs / 3600000);
    if (diffHrs < 1) return `${Math.floor(diffMs / 60000)}m ago`;
    if (diffHrs < 24) return `${diffHrs}h ago`;
    return `${Math.floor(diffHrs / 24)}d ago`;
  };

  if (loading) return <LoadingSpinner text="Loading data catalog..." />;

  return (
    <div className="status-panel">
      <div className="panel-header">
        <h2>Data Sources</h2>
        <button className="btn btn-sm" onClick={loadCatalog}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      <div className="source-grid">
        {catalog.map((source) => (
          <div key={source.source} className={`source-card ${source.status}`}>
            <div className="source-header">
              <div className="source-status-icon">
                {source.status === 'fresh' ? (
                  <CheckCircle size={18} className="text-green" />
                ) : (
                  <AlertCircle size={18} className="text-amber" />
                )}
              </div>
              <div className="source-info">
                <h4>{source.source.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</h4>
                <p>{source.description}</p>
              </div>
            </div>

            <div className="source-stats">
              <div className="stat">
                <Clock size={14} />
                <span>Last scraped: {formatTime(source.last_scraped)}</span>
              </div>
              <div className="stat">
                <span>{source.record_count.toLocaleString()} records</span>
              </div>
            </div>

            <button
              className="btn btn-scrape"
              onClick={() => handleScrape(source.source)}
              disabled={scraping === source.source}
            >
              {scraping === source.source ? (
                <LoadingSpinner size={14} text="Scraping..." />
              ) : (
                <>
                  <RefreshCw size={14} /> Scrape Now
                </>
              )}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
