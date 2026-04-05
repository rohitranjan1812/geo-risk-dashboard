import { X, Mountain, Droplets, Wind, Shield } from 'lucide-react';
import type { RiskScorecard as RiskScorecardType } from '../../types';
import { RiskRadarChart } from '../common/Charts';
import { WhatIfScenario } from './WhatIfScenario';

interface RiskScorecardProps {
  scorecard: RiskScorecardType;
  onClose: () => void;
}

const TIER_COLORS: Record<string, string> = {
  Low: '#4caf50',
  Moderate: '#ff9800',
  High: '#f44336',
  'Very High': '#d32f2f',
  Extreme: '#880e4f',
};

function ScoreGauge({ score, label, color }: { score: number; label: string; color: string }) {
  const rotation = (score / 100) * 180 - 90;

  return (
    <div className="score-gauge">
      <svg viewBox="0 0 120 70" className="gauge-svg">
        <path d="M 10 65 A 50 50 0 0 1 110 65" fill="none" stroke="#333" strokeWidth="8" strokeLinecap="round" />
        <path
          d="M 10 65 A 50 50 0 0 1 110 65"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={`${(score / 100) * 157} 157`}
        />
        <text x="60" y="55" textAnchor="middle" fill="#fff" fontSize="20" fontWeight="bold">
          {Math.round(score)}
        </text>
      </svg>
      <span className="gauge-label">{label}</span>
    </div>
  );
}

function PerilCard({
  peril,
  icon: Icon,
  score,
  rawValue,
  unit,
  description,
  color,
}: {
  peril: string;
  icon: React.ElementType;
  score: number;
  rawValue: number | null;
  unit: string | null;
  description: string | null;
  color: string;
}) {
  return (
    <div className="peril-card" style={{ borderLeftColor: color }}>
      <div className="peril-header">
        <Icon size={18} style={{ color }} />
        <span className="peril-name">{peril}</span>
        <span className="peril-score" style={{ color }}>
          {Math.round(score)}
        </span>
      </div>
      <div className="peril-bar">
        <div className="peril-bar-fill" style={{ width: `${score}%`, backgroundColor: color }} />
      </div>
      {description && <p className="peril-desc">{description}</p>}
      {rawValue !== null && unit && (
        <span className="peril-raw">
          {rawValue} {unit}
        </span>
      )}
    </div>
  );
}

export function RiskScorecard({ scorecard, onClose }: RiskScorecardProps) {
  const tierColor = TIER_COLORS[scorecard.risk_tier] || '#999';

  return (
    <div className="risk-scorecard">
      <div className="scorecard-header">
        <div>
          <h2>Risk Assessment</h2>
          {scorecard.address && <p className="scorecard-address">{scorecard.address}</p>}
        </div>
        <button className="btn-icon" onClick={onClose}>
          <X size={20} />
        </button>
      </div>

      <div className="composite-section">
        <ScoreGauge score={scorecard.composite_score} label="Composite Risk" color={tierColor} />
        <div className="risk-tier" style={{ color: tierColor }}>
          <Shield size={20} />
          <span>{scorecard.risk_tier} Risk</span>
        </div>
      </div>

      <RiskRadarChart
        seismic={scorecard.seismic?.score || 0}
        flood={scorecard.flood?.score || 0}
        wind={scorecard.wind?.score || 0}
      />

      <div className="perils-grid">
        {scorecard.seismic && (
          <PerilCard
            peril="Seismic"
            icon={Mountain}
            score={scorecard.seismic.score}
            rawValue={scorecard.seismic.raw_value}
            unit={scorecard.seismic.unit}
            description={scorecard.seismic.description}
            color="#f44336"
          />
        )}
        {scorecard.flood && (
          <PerilCard
            peril="Flood"
            icon={Droplets}
            score={scorecard.flood.score}
            rawValue={scorecard.flood.raw_value}
            unit={scorecard.flood.unit}
            description={scorecard.flood.description}
            color="#2196f3"
          />
        )}
        {scorecard.wind && (
          <PerilCard
            peril="Wind"
            icon={Wind}
            score={scorecard.wind.score}
            rawValue={scorecard.wind.raw_value}
            unit={scorecard.wind.unit}
            description={scorecard.wind.description}
            color="#ff9800"
          />
        )}
      </div>

      <WhatIfScenario
        latitude={scorecard.latitude}
        longitude={scorecard.longitude}
        constructionType={scorecard.seismic?.unit?.includes('PGA') ? 'Unknown' : 'Unknown'}
      />

      {scorecard.scored_at && (
        <p className="scored-at">Assessed: {new Date(scorecard.scored_at).toLocaleString()}</p>
      )}
    </div>
  );
}
