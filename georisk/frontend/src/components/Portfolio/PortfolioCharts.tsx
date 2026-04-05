import { DollarSign, BarChart3, Target, TrendingUp } from 'lucide-react';
import type { PortfolioSummary } from '../../types';
import { RiskDistributionChart, PerilAveragesChart } from '../common/Charts';

interface PortfolioChartsProps {
  summary: PortfolioSummary;
}

const TIER_COLORS: Record<string, string> = {
  Low: '#4caf50',
  Moderate: '#ff9800',
  High: '#f44336',
  'Very High': '#d32f2f',
  Extreme: '#880e4f',
};

export function PortfolioCharts({ summary }: PortfolioChartsProps) {
  const avgTier =
    summary.avg_composite_score < 20 ? 'Low'
    : summary.avg_composite_score < 40 ? 'Moderate'
    : summary.avg_composite_score < 60 ? 'High'
    : summary.avg_composite_score < 80 ? 'Very High'
    : 'Extreme';

  return (
    <div className="portfolio-charts">
      <div className="summary-cards">
        <div className="summary-card">
          <div className="summary-icon">
            <BarChart3 size={24} />
          </div>
          <div>
            <span className="summary-value">{summary.total_properties}</span>
            <span className="summary-label">Properties</span>
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-icon">
            <DollarSign size={24} />
          </div>
          <div>
            <span className="summary-value">${(summary.total_tiv / 1e6).toFixed(1)}M</span>
            <span className="summary-label">Total TIV</span>
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-icon">
            <Target size={24} />
          </div>
          <div>
            <span className="summary-value" style={{ color: TIER_COLORS[avgTier] }}>
              {summary.avg_composite_score.toFixed(1)}
            </span>
            <span className="summary-label">Avg Risk Score</span>
          </div>
        </div>
        <div className="summary-card">
          <div className="summary-icon">
            <TrendingUp size={24} />
          </div>
          <div>
            <span className="summary-value" style={{ color: '#f44336' }}>
              {summary.max_composite_score.toFixed(1)}
            </span>
            <span className="summary-label">Max Risk Score</span>
          </div>
        </div>
      </div>

      <div className="charts-grid">
        <RiskDistributionChart data={summary.risk_distribution} />
        <PerilAveragesChart data={summary.peril_averages} />
      </div>

      {summary.top_accumulations.length > 0 && (
        <div className="accumulation-section">
          <h4>Top Accumulation Zones</h4>
          <div className="accum-list">
            {summary.top_accumulations.slice(0, 5).map((accum, i) => (
              <div key={accum.h3_index} className="accum-item">
                <span className="accum-rank">#{i + 1}</span>
                <div className="accum-details">
                  <span className="accum-tiv">${(accum.total_tiv / 1e6).toFixed(1)}M TIV</span>
                  <span className="accum-count">{accum.count} properties</span>
                  <span className="accum-score">Avg Score: {accum.avg_score}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
