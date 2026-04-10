import { useState, useCallback, useMemo } from 'react';
import type { Journey, ThemeMode, Property } from './types';
import type { ColorByField } from './components/Map/MapContainer';
import { Sidebar } from './components/Dashboard/Sidebar';
import { MapContainer } from './components/Map/MapContainer';
import { HazardLayerControls } from './components/Map/HazardLayers';
import { MapColorControl } from './components/Map/MapColorControl';
import { MapLegend } from './components/Map/MapLegend';
import { PropertySearch } from './components/Property/PropertySearch';
import { RiskScorecard } from './components/Property/RiskScorecard';
import { StatusPanel } from './components/Dashboard/StatusPanel';
import { PortfolioUpload } from './components/Portfolio/PortfolioUpload';
import { PortfolioTable } from './components/Portfolio/PortfolioTable';
import { PortfolioCharts } from './components/Portfolio/PortfolioCharts';
import { SeedConfig } from './components/CAT/SeedConfig';
import { SyntheticBrowser } from './components/CAT/SyntheticBrowser';
import { SessionHistory } from './components/CAT/SessionHistory';
import { CATResults } from './components/CAT/CATResults';
import { LocationDetail } from './components/CAT/LocationDetail';
import { SessionCompare } from './components/CAT/SessionCompare';
import { useMapLayers } from './hooks/useMapLayers';
import { useRiskQuery } from './hooks/useRiskQuery';
import { usePortfolio } from './hooks/usePortfolio';
import { fetchCATSession, fetchPortfolioAccumulation, fetchSyntheticAccumulationHex, fetchSyntheticSummary, runCATForUploadedPortfolio } from './api/client';
import { fetchScoredGeoJSON, fetchPortfolioGeoJSON } from './api/client';
import './App.css';

type CatStep = 'seed' | 'browse' | 'history' | 'results' | 'location' | 'compare';

function App() {
  const [journey, setJourney] = useState<Journey>('explorer');
  const [theme, setTheme] = useState<ThemeMode>('dark');
  const [highlightCoords, setHighlightCoords] = useState<[number, number] | null>(null);
  const [portfolioGeoJSON, setPortfolioGeoJSON] = useState<GeoJSON.FeatureCollection | null>(null);
  const [syntheticInfo, setSyntheticInfo] = useState<any | null>(null);

  const [catBbox, setCatBbox] = useState<[number, number, number, number] | null>(null);
  const [catStep, setCatStep] = useState<CatStep>('history');
  const [catPortfolio, setCatPortfolio] = useState<{ id: string; name: string; count: number } | null>(null);
  const [catLocationId, setCatLocationId] = useState<number | null>(null);
  const [catActiveSessionId, setCatActiveSessionId] = useState<string | null>(null);
  const [catCompareIds, setCatCompareIds] = useState<string[]>([]);
  const [catPropertiesGeoJSON, setCatPropertiesGeoJSON] = useState<GeoJSON.FeatureCollection | null>(null);
  const [aalHeatmapGeoJSON, setAalHeatmapGeoJSON] = useState<GeoJSON.FeatureCollection | null>(null);
  const [colorBy, setColorBy] = useState<ColorByField>('composite_score');
  const [catModelResult, setCatModelResult] = useState<any>(null);

  // CAT selection state (single source of truth for map + sidebar)
  const [selectedCatPropertyId, setSelectedCatPropertyId] = useState<number | null>(null);
  const [selectedCatCoords, setSelectedCatCoords] = useState<[number, number] | null>(null);
  const [selectedCatIds, setSelectedCatIds] = useState<number[]>([]);

  const { layers, visibility, toggleLayer, reload: reloadLayers } = useMapLayers();
  const {
    scorecard, loading: riskLoading, error: riskError,
    queryPropertyRisk, queryAddress, clearRisk, setSelectedProperty,
  } = useRiskQuery();
  const {
    portfolioId, results: portfolioResults, summary: portfolioSummary,
    loading: portfolioLoading, error: portfolioError, uploadErrors,
    upload: uploadPortfolio, clearPortfolio,
  } = usePortfolio();

  const handlePropertyClick = useCallback(async (property: Property) => {
    setSelectedProperty(property);
    setHighlightCoords([property.longitude, property.latitude]);
    await queryPropertyRisk(property.id);
  }, [queryPropertyRisk, setSelectedProperty]);

  const handleAddressSearch = useCallback(async (address: string) => {
    const result = await queryAddress(address);
    if (result) {
      setHighlightCoords([result.property.longitude, result.property.latitude]);
      reloadLayers();
    }
  }, [queryAddress, reloadLayers]);

  const handlePortfolioUpload = useCallback(async (file: File) => {
    const result = await uploadPortfolio(file);
    if (result) {
      try {
        const accum = await fetchPortfolioAccumulation(result.portfolio_id);
        setPortfolioGeoJSON(accum);
      } catch (err) {
        console.error(err);
      }
      reloadLayers();
    }
    return result;
  }, [uploadPortfolio, reloadLayers]);

  const toggleTheme = useCallback(() => setTheme(prev => prev === 'dark' ? 'light' : 'dark'), []);

  const handleBboxSelect = useCallback((bbox: [number, number, number, number]) => setCatBbox(bbox), []);

  const featureIndexById = useMemo(() => {
    const m = new Map<number, GeoJSON.Feature>();
    const feats = catPropertiesGeoJSON?.features || [];
    for (const f of feats) {
      const id = (f as any)?.properties?.id;
      if (typeof id === 'number') m.set(id, f as any);
    }
    return m;
  }, [catPropertiesGeoJSON]);

  const selectCatProperty = useCallback((propertyId: number, coords?: [number, number] | null) => {
    setSelectedCatPropertyId(propertyId);
    if (coords && coords.length === 2) {
      setSelectedCatCoords(coords);
      return;
    }
    const f = featureIndexById.get(propertyId);
    const c = (f?.geometry as any)?.coordinates;
    if (Array.isArray(c) && c.length >= 2 && typeof c[0] === 'number' && typeof c[1] === 'number') {
      setSelectedCatCoords([c[0], c[1]]);
    }
  }, [featureIndexById]);

  const handleCatPropertyClickFromMap = useCallback((propertyId: number, coords?: [number, number]) => {
    selectCatProperty(propertyId, coords || null);
    setCatLocationId(propertyId);
    setCatStep('location');
  }, [selectCatProperty]);

  const handleCatBoxSelectIds = useCallback((ids: number[]) => {
    setSelectedCatIds(ids);
  }, []);

  const loadPortfolioOnMap = useCallback(async (pid: string) => {
    try {
      const data = await fetchPortfolioGeoJSON(pid, 5000);
      setCatPropertiesGeoJSON(data as any);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadScoredOnMap = useCallback(async (pid: string) => {
    try {
      const data = await fetchScoredGeoJSON(pid, 5000);
      setCatPropertiesGeoJSON(data as any);
      setAalHeatmapGeoJSON(data as any);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const handlePortfolioCreated = useCallback((id: string, name: string, count: number) => {
    setCatPortfolio({ id, name, count });
    loadPortfolioOnMap(id);
    setCatStep('results');
  }, [loadPortfolioOnMap]);

  const handleLoadSession = useCallback((session: any) => {
    const s = session.session;
    setCatPortfolio({ id: s.portfolio_id, name: s.name, count: s.n_properties });
    setCatModelResult(session);
    setCatActiveSessionId(s.session_id || null);
    loadScoredOnMap(s.portfolio_id);
    setCatStep('results');
  }, [loadScoredOnMap]);

  const runCatFromUploadedPortfolio = useCallback(async () => {
    if (!portfolioId) return;
    try {
      const r = await runCATForUploadedPortfolio(portfolioId, { n_years: 10000, max_properties: 200 });
      const sid = String(r?.session_id || '');
      if (!sid) return;
      const full = await fetchCATSession(sid);
      setJourney('cat');
      handleLoadSession(full);
    } catch (e) {
      console.error(e);
    }
  }, [portfolioId, handleLoadSession]);

  const handleModelComplete = useCallback((pid: string) => {
    loadScoredOnMap(pid);
  }, [loadScoredOnMap]);

  const isCatMode = journey === 'cat';
  const catPointCount = catPropertiesGeoJSON?.features?.length || 0;

  return (
    <div className={`app ${theme}`}>
      <Sidebar activeJourney={journey} onJourneyChange={setJourney} theme={theme} onToggleTheme={toggleTheme} />

      <main className="main-content">
        <div className="map-section">
          <MapContainer
            layers={layers}
            visibility={visibility}
            onPropertyClick={handlePropertyClick}
            highlightCoords={highlightCoords}
            portfolioGeoJSON={portfolioGeoJSON}
            isDark={theme === 'dark'}
            enableBboxSelect={isCatMode}
            onBboxSelect={handleBboxSelect}
            catPropertiesGeoJSON={isCatMode ? catPropertiesGeoJSON : null}
            colorByField={colorBy}
            onCatPropertyClick={handleCatPropertyClickFromMap}
            aalHeatmapGeoJSON={isCatMode ? aalHeatmapGeoJSON : null}
            selectedCatPropertyId={isCatMode ? selectedCatPropertyId : null}
            selectedCatCoords={isCatMode ? selectedCatCoords : null}
            selectedCatIds={isCatMode ? selectedCatIds : []}
            onCatBoxSelectIds={isCatMode ? handleCatBoxSelectIds : undefined}
          />
          <div className="map-overlay-controls">
            <HazardLayerControls visibility={visibility} onToggle={toggleLayer} showCatLayers={isCatMode} />
            <MapColorControl value={colorBy} onChange={setColorBy} visible={isCatMode && catPointCount > 0} />
          </div>
          <MapLegend colorBy={colorBy} count={catPointCount} visible={isCatMode && catPointCount > 0} />
          {isCatMode && catStep === 'browse' && (
            <div className="map-overlay-hint">Shift + drag to select area</div>
          )}
        </div>

        <div className="panel-section">
          {journey === 'explorer' && (
            <div className="explorer-panel">
              <PropertySearch onPropertySelect={handlePropertyClick} onAddressSearch={handleAddressSearch} loading={riskLoading} />
              {riskError && <div className="error-banner">{riskError}</div>}
              {scorecard && <RiskScorecard scorecard={scorecard} onClose={() => { clearRisk(); setHighlightCoords(null); }} />}
            </div>
          )}

          {journey === 'portfolio' && (
            <div className="portfolio-panel">
              {!portfolioId ? (
                <>
                  <PortfolioUpload onUpload={handlePortfolioUpload} loading={portfolioLoading} error={portfolioError} />
                  <div style={{ marginTop: 12 }}>
                    <button className="btn btn-outline" onClick={async () => {
                      try {
                        const summary = await fetchSyntheticSummary(20000);
                        setSyntheticInfo(summary);
                        const hex = await fetchSyntheticAccumulationHex(5, 200000, 250);
                        setPortfolioGeoJSON(hex);
                      } catch (e) { console.error(e); }
                    }}>Load Synthetic Portfolio (1M+)</button>
                    {syntheticInfo && (
                      <div className="warning-banner" style={{ marginTop: 10 }}>
                        Seeded: {syntheticInfo.total_seeded?.toLocaleString()} | Sampled: {syntheticInfo.sampled?.toLocaleString()} | Avg: {syntheticInfo.avg_scores?.composite}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <>
                  <div className="portfolio-header">
                    <h2>Portfolio: {portfolioId}</h2>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <button className="btn btn-primary" onClick={runCatFromUploadedPortfolio}>
                        Run CAT Model
                      </button>
                      <button className="btn btn-outline" onClick={() => { clearPortfolio(); setPortfolioGeoJSON(null); }}>New Upload</button>
                    </div>
                  </div>
                  {uploadErrors.length > 0 && <div className="warning-banner">{uploadErrors.length} row(s) had issues</div>}
                  {portfolioSummary && <PortfolioCharts summary={portfolioSummary} />}
                  {portfolioResults.length > 0 && <PortfolioTable properties={portfolioResults} portfolioId={portfolioId} />}
                </>
              )}
            </div>
          )}

          {journey === 'cat' && (
            <div className="cat-panel">
              {catStep === 'location' && catLocationId ? (
                <>
                  <LocationDetail
                    propertyId={catLocationId}
                    sessionId={catActiveSessionId}
                    onClose={() => { setCatLocationId(null); setCatStep(catPortfolio ? 'results' : 'browse'); }}
                  />
                </>
              ) : catStep === 'compare' ? (
                <SessionCompare
                  sessionIds={catCompareIds}
                  onBack={() => setCatStep('history')}
                />
              ) : catStep === 'results' && catPortfolio ? (
                <>
                  <CATResults
                    portfolioId={catPortfolio.id}
                    portfolioName={catPortfolio.name}
                    nProperties={catPortfolio.count}
                    selectedPropertyId={selectedCatPropertyId}
                    selectedIds={selectedCatIds}
                    onPropertyClick={(id) => {
                      selectCatProperty(id);
                      setCatLocationId(id);
                      setCatStep('location');
                    }}
                    onModelComplete={handleModelComplete}
                    onSessionCreated={(sid) => setCatActiveSessionId(sid)}
                  />
                  <div className="cat-nav-buttons">
                    <button className="btn btn-outline btn-sm" onClick={() => setCatStep('history')}>Session History</button>
                    <button className="btn btn-outline btn-sm" onClick={() => { setCatPortfolio(null); setCatPropertiesGeoJSON(null); setAalHeatmapGeoJSON(null); setCatActiveSessionId(null); setCatStep('browse'); }}>New Portfolio</button>
                  </div>
                </>
              ) : catStep === 'seed' ? (
                <>
                  <SeedConfig bbox={catBbox} onClearBbox={() => setCatBbox(null)} onSeeded={() => setCatStep('browse')} />
                  <button className="btn btn-outline btn-sm" style={{ marginTop: 8, width: '100%' }} onClick={() => setCatStep('history')}>Back to History</button>
                </>
              ) : catStep === 'browse' ? (
                <>
                  <SyntheticBrowser
                    bbox={catBbox}
                    onClearBbox={() => setCatBbox(null)}
                    onPortfolioCreated={handlePortfolioCreated}
                    selectedPropertyId={selectedCatPropertyId}
                    onPropertyClick={(id) => {
                      selectCatProperty(id);
                      setCatLocationId(id);
                      setCatStep('location');
                    }}
                  />
                  <div className="cat-nav-buttons">
                    <button className="btn btn-outline btn-sm" onClick={() => setCatStep('seed')}>Re-seed Properties</button>
                    <button className="btn btn-outline btn-sm" onClick={() => setCatStep('history')}>Session History</button>
                  </div>
                </>
              ) : (
                <SessionHistory
                  onLoadSession={handleLoadSession}
                  onNewAnalysis={() => setCatStep('browse')}
                  onCompareSessions={(ids) => {
                    setCatCompareIds(ids);
                    setCatStep('compare');
                  }}
                />
              )}
            </div>
          )}

          {journey === 'monitor' && <div className="monitor-panel"><StatusPanel /></div>}
        </div>
      </main>
    </div>
  );
}

export default App;
