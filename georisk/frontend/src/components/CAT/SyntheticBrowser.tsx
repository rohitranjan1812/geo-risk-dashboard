import { useState, useCallback, useEffect } from 'react';
import { Filter, ChevronLeft, ChevronRight, FolderPlus, MapPin, X } from 'lucide-react';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { buildSyntheticPortfolio, filterSynthetic } from '../../api/client';

const CONSTRUCTION_TYPES = ['Wood Frame', 'Masonry', 'Reinforced Concrete', 'Steel Frame', 'Concrete Tilt-Up'];
const OCCUPANCIES = ['Residential', 'Commercial', 'Industrial', 'Hospitality', 'Healthcare'];

interface SyntheticBrowserProps {
  bbox: [number, number, number, number] | null;
  onClearBbox: () => void;
  onPortfolioCreated: (portfolioId: string, name: string, count: number) => void;
  selectedPropertyId?: number | null;
  onPropertyClick: (propertyId: number) => void;
}

export function SyntheticBrowser({ bbox, onClearBbox, onPortfolioCreated, selectedPropertyId, onPropertyClick }: SyntheticBrowserProps) {
  const [results, setResults] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [portfolioName, setPortfolioName] = useState('');
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [selectAll, setSelectAll] = useState(true);
  const [building, setBuilding] = useState(false);

  const [tivMin, setTivMin] = useState('');
  const [tivMax, setTivMax] = useState('');
  const [ctypes, setCtypes] = useState<string[]>([]);
  const [occs, setOccs] = useState<string[]>([]);
  const [ybMin, setYbMin] = useState('');
  const [ybMax, setYbMax] = useState('');

  const doFilter = useCallback(async (pg = 1) => {
    setLoading(true);
    try {
      const body: any = { page: pg, page_size: 50 };
      if (bbox) body.bbox = bbox;
      if (tivMin) body.tiv_min = parseFloat(tivMin);
      if (tivMax) body.tiv_max = parseFloat(tivMax);
      if (ctypes.length > 0) body.construction_types = ctypes;
      if (occs.length > 0) body.occupancies = occs;
      if (ybMin) body.year_built_min = parseInt(ybMin);
      if (ybMax) body.year_built_max = parseInt(ybMax);

      const data = await filterSynthetic(body);
      setResults(data.results);
      setTotal(data.total);
      setPage(data.page);
      setPages(data.pages);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [bbox, tivMin, tivMax, ctypes, occs, ybMin, ybMax]);

  // Auto-load properties when component mounts (e.g., after seeding completes)
  useEffect(() => {
    doFilter(1);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const buildPortfolio = async () => {
    setBuilding(true);
    try {
      const body: any = { name: portfolioName || 'CAT Portfolio', max_properties: 500 };
      if (!selectAll && selectedIds.size > 0) {
        body.property_ids = Array.from(selectedIds);
      } else {
        body.filter = {} as any;
        if (bbox) body.filter.bbox = bbox;
        if (tivMin) body.filter.tiv_min = parseFloat(tivMin);
        if (tivMax) body.filter.tiv_max = parseFloat(tivMax);
        if (ctypes.length > 0) body.filter.construction_types = ctypes;
        if (occs.length > 0) body.filter.occupancies = occs;
        if (ybMin) body.filter.year_built_min = parseInt(ybMin);
        if (ybMax) body.filter.year_built_max = parseInt(ybMax);
      }
      const data = await buildSyntheticPortfolio(body);
      onPortfolioCreated(data.portfolio_id, data.name, data.n_properties);
    } catch (e) {
      console.error(e);
    } finally {
      setBuilding(false);
    }
  };

  const toggleId = (id: number) => {
    setSelectAll(false);
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  return (
    <div className="synthetic-browser">
      <h2>Property Browser</h2>
      <p className="text-muted" style={{ fontSize: 12, marginBottom: 12 }}>
        Shift+drag on the map to draw a bounding box. Use filters below to narrow properties. Build a portfolio to run CAT models.
      </p>

      {bbox && (
        <div className="bbox-badge">
          <MapPin size={14} />
          <span>Bbox: [{bbox.map(v => v.toFixed(2)).join(', ')}]</span>
          <button onClick={onClearBbox}><X size={12} /></button>
        </div>
      )}

      <div className="filter-grid">
        <div className="filter-row">
          <label>TIV Min</label>
          <input type="number" placeholder="0" value={tivMin} onChange={e => setTivMin(e.target.value)} />
          <label>Max</label>
          <input type="number" placeholder="any" value={tivMax} onChange={e => setTivMax(e.target.value)} />
        </div>
        <div className="filter-row">
          <label>Construction</label>
          <div className="chip-group">
            {CONSTRUCTION_TYPES.map(c => (
              <button key={c} className={`chip ${ctypes.includes(c) ? 'active' : ''}`}
                onClick={() => setCtypes(prev => prev.includes(c) ? prev.filter(x => x !== c) : [...prev, c])}>
                {c}
              </button>
            ))}
          </div>
        </div>
        <div className="filter-row">
          <label>Occupancy</label>
          <div className="chip-group">
            {OCCUPANCIES.map(o => (
              <button key={o} className={`chip ${occs.includes(o) ? 'active' : ''}`}
                onClick={() => setOccs(prev => prev.includes(o) ? prev.filter(x => x !== o) : [...prev, o])}>
                {o}
              </button>
            ))}
          </div>
        </div>
        <div className="filter-row">
          <label>Year Built</label>
          <input type="number" placeholder="1950" value={ybMin} onChange={e => setYbMin(e.target.value)} />
          <label>to</label>
          <input type="number" placeholder="2025" value={ybMax} onChange={e => setYbMax(e.target.value)} />
        </div>
      </div>

      <button className="btn btn-primary" onClick={() => doFilter(1)} disabled={loading} style={{ width: '100%', marginBottom: 12 }}>
        {loading ? <LoadingSpinner size={14} /> : <><Filter size={14} /> Search Properties</>}
      </button>

      {total > 0 && (
        <>
          <div className="results-header">
            <span>{total.toLocaleString()} properties found</span>
            <div className="pagination">
              <button disabled={page <= 1} onClick={() => doFilter(page - 1)}><ChevronLeft size={14} /></button>
              <span>{page}/{pages}</span>
              <button disabled={page >= pages} onClick={() => doFilter(page + 1)}><ChevronRight size={14} /></button>
            </div>
          </div>

          <div className="table-scroll" style={{ maxHeight: 280 }}>
            <table className="portfolio-table">
              <thead>
                <tr>
                  <th><input type="checkbox" checked={selectAll} onChange={() => setSelectAll(!selectAll)} /></th>
                  <th>ID</th><th>TIV</th><th>Construction</th><th>Occupancy</th><th>Yr</th>
                </tr>
              </thead>
              <tbody>
                {results.map(r => (
                  <tr
                    key={r.property_id}
                    onClick={() => onPropertyClick(r.property_id)}
                    style={{ cursor: 'pointer' }}
                    className={selectedPropertyId === r.property_id ? 'row-selected' : ''}
                  >
                    <td onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={selectAll || selectedIds.has(r.property_id)} onChange={() => toggleId(r.property_id)} />
                    </td>
                    <td>{r.property_id}</td>
                    <td>${(r.tiv / 1e6).toFixed(1)}M</td>
                    <td>{r.construction_type}</td>
                    <td>{r.occupancy}</td>
                    <td>{r.year_built}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="build-section">
            <input type="text" placeholder="Portfolio name..." value={portfolioName}
              onChange={e => setPortfolioName(e.target.value)} className="portfolio-name-input" />
            <button className="btn btn-primary" onClick={buildPortfolio} disabled={building}>
              {building ? <LoadingSpinner size={14} /> : <><FolderPlus size={14} /> Build Portfolio ({selectAll ? `top ${Math.min(total, 500)}` : selectedIds.size})</>}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
