import { useState, useCallback } from 'react';
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
import { useMapLayers } from './hooks/useMapLayers';
import { useRiskQuery } from './hooks/useRiskQuery';
import { usePortfolio } from './hooks/usePortfolio';
import { fetchPortfolioAccumulation, fetchSyntheticAccumulationHex, fetchSyntheticSummary } from './api/client';
import axios from 'axios';
import './App.css';

const API = 'http://localhost:8000/api';

type CatStep = 'seed' | 'browse' | 'history' | 'results' | 'location';

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
  const [catPropertiesGeoJSON, setCatPropertiesGeoJSON] = useState<GeoJSON.FeatureCollection | null>(null);
  const [aalHeatmapGeoJSON, setAalHeatmapGeoJSON] = useState<GeoJSON.FeatureCollection | null>(null);
  const [colorBy, setColorBy] = useState<ColorByField>('composite_score');
  const [catModelResult, setCatModelResult] = useState<any>(null);

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

  const handleCatPropertyClickFromMap = useCallback((propertyId: number) => {
    setCatLocationId(propertyId);
    setCatStep('location');
  }, []);

  const loadPortfolioOnMap = useCallback(async (pid: string) => {
    try {
      const { data } = await axios.get(`${API}/synthetic/portfolio/${pid}/geojson?limit=5000`);
      setCatPropertiesGeoJSON(data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const loadScoredOnMap = useCallback(async (pid: string) => {
    try {
      const { data } = await axios.get(`${API}/synthetic/portfolio/${pid}/scored-geojson?limit=5000`);
      setCatPropertiesGeoJSON(data);
      setAalHeatmapGeoJSON(data);
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
    loadScoredOnMap(s.portfolio_id);
    setCatStep('results');
  }, [loadScoredOnMap]);

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
                    <button className="btn btn-outline" onClick={() => { clearPortfolio(); setPortfolioGeoJSON(null); }}>New Upload</button>
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
                  <LocationDetail propertyId={catLocationId} onClose={() => { setCatLocationId(null); setCatStep(catPortfolio ? 'results' : 'browse'); }} />
                </>
              ) : catStep === 'results' && catPortfolio ? (
                <>
                  <CATResults
                    portfolioId={catPortfolio.id}
                    portfolioName={catPortfolio.name}
                    nProperties={catPortfolio.count}
                    onPropertyClick={(id) => { setCatLocationId(id); setCatStep('location'); }}
                    onModelComplete={handleModelComplete}
                  />
                  <div className="cat-nav-buttons">
                    <button className="btn btn-outline btn-sm" onClick={() => setCatStep('history')}>Session History</button>
                    <button className="btn btn-outline btn-sm" onClick={() => { setCatPortfolio(null); setCatPropertiesGeoJSON(null); setAalHeatmapGeoJSON(null); setCatStep('browse'); }}>New Portfolio</button>
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
                    onPropertyClick={(id) => { setCatLocationId(id); setCatStep('location'); }}
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
