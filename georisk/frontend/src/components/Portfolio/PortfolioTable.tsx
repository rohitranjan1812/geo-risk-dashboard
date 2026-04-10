import { ArrowUpDown, Download } from 'lucide-react';
import { useState, useMemo } from 'react';
import type { PortfolioProperty } from '../../types';
import { getPortfolioExportUrl } from '../../api/client';

interface PortfolioTableProps {
  properties: PortfolioProperty[];
  portfolioId: string;
}

const TIER_COLORS: Record<string, string> = {
  Low: '#4caf50',
  Moderate: '#ff9800',
  High: '#f44336',
  'Very High': '#d32f2f',
  Extreme: '#880e4f',
};

type SortKey = 'composite_score' | 'tiv' | 'seismic_score' | 'flood_score' | 'wind_score' | 'rate_factor';

export function PortfolioTable({ properties, portfolioId }: PortfolioTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('composite_score');
  const [sortAsc, setSortAsc] = useState(false);

  const sorted = useMemo(() =>
    [...properties].sort((a, b) => {
      const va = a[sortKey] ?? 0;
      const vb = b[sortKey] ?? 0;
      return sortAsc ? va - vb : vb - va;
    }),
    [properties, sortKey, sortAsc],
  );

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  const SortHeader = ({ label, field }: { label: string; field: SortKey }) => (
    <th onClick={() => handleSort(field)} className="sortable">
      {label} <ArrowUpDown size={12} />
    </th>
  );

  return (
    <div className="portfolio-table-wrapper">
      <div className="table-header">
        <h3>Scored Properties ({properties.length})</h3>
        <a
          href={getPortfolioExportUrl(portfolioId)}
          className="btn btn-outline btn-sm"
          download
        >
          <Download size={14} /> Export CSV
        </a>
      </div>

      <div className="table-scroll">
        <table className="portfolio-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Name</th>
              <SortHeader label="TIV" field="tiv" />
              <SortHeader label="Seismic" field="seismic_score" />
              <SortHeader label="Flood" field="flood_score" />
              <SortHeader label="Wind" field="wind_score" />
              <SortHeader label="Composite" field="composite_score" />
              <SortHeader label="Rate Factor" field="rate_factor" />
              <th>Tier</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((p, i) => {
              const tier = p.composite_score < 20 ? 'Low'
                : p.composite_score < 40 ? 'Moderate'
                : p.composite_score < 60 ? 'High'
                : p.composite_score < 80 ? 'Very High'
                : 'Extreme';
              return (
                <tr key={p.property_id}>
                  <td>{i + 1}</td>
                  <td>{p.name || `Property ${p.property_id}`}</td>
                  <td>${(p.tiv / 1e6).toFixed(1)}M</td>
                  <td>{p.seismic_score.toFixed(0)}</td>
                  <td>{p.flood_score.toFixed(0)}</td>
                  <td>{p.wind_score.toFixed(0)}</td>
                  <td className="score-cell">
                    <span className="inline-bar">
                      <span
                        className="inline-bar-fill"
                        style={{
                          width: `${p.composite_score}%`,
                          backgroundColor: TIER_COLORS[tier],
                        }}
                      />
                    </span>
                    {p.composite_score.toFixed(1)}
                  </td>
                  <td>{p.rate_factor.toFixed(2)}x</td>
                  <td>
                    <span className="tier-badge" style={{ color: TIER_COLORS[tier] }}>
                      {tier}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
