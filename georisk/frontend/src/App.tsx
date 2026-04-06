import { useState, useCallback } from 'react';
import type { Journey, ThemeMode, Property } from './types';
import { Sidebar } from './components/Dashboard/Sidebar';
import { MapContainer } from './components/Map/MapContainer';
import { HazardLayerControls } from './components/Map/HazardLayers';
import { PropertySearch } from './components/Property/PropertySearch';
import { RiskScorecard } from './components/Property/RiskScorecard';
import { StatusPanel } from './components/Dashboard/StatusPanel';
import { PortfolioUpload } from './components/Portfolio/PortfolioUpload';
import { PortfolioTable } from './components/Portfolio/PortfolioTable';
import { PortfolioCharts } from './components/Portfolio/PortfolioCharts';
import { SyntheticBrowser } from './components/CAT/SyntheticBrowser';
import { CATResults } from './components/CAT/CATResults';
import { LocationDetail } from './components/CAT/LocationDetail';
import { useMapLayers } from './hooks/useMapLayers';
import { useRiskQuery } from './hooks/useRiskQuery';
import { usePortfolio } from './hooks/usePortfolio';
import { fetchPortfolioAccumulation, fetchSyntheticAccumulationHex, fetchSyntheticSummary } from './api/client';
import './App.css';

function App() {
  const [journey, setJourney] = useState<Journey>('explorer');
  const [theme, setTheme] = useState<ThemeMode>('dark');
  const [highlightCoords, setHighlightCoords] = useState<[number, number] | null>(null);
  const [portfolioGeoJSON, setPortfolioGeoJSON] = useState<GeoJSON.FeatureCollection | null>(null);
  const [syntheticInfo, setSyntheticInfo] = useState<any | null>(null);

  const [catBbox, setCatBbox] = useState<[number, number, number, number] | null>(null);
  const [catPortfolio, setCatPortfolio] = useState<{ id: string; name: string; count: number } | null>(null);
  const [catLocationId, setCatLocationId] = useState<number | null>(null);

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
        console.error('Failed to load accumulation:', err);
      }
      reloadLayers();
    }
    return result;
  }, [uploadPortfolio, reloadLayers]);

  const toggleTheme = useCallback(() => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  }, []);

  const handleBboxSelect = useCallback((bbox: [number, number, number, number]) => {
    setCatBbox(bbox);
  }, []);

  const isCatMode = journey === 'cat';

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
          />
          <div className="map-overlay-controls">
            <HazardLayerControls visibility={visibility} onToggle={toggleLayer} />
          </div>
          {isCatMode && (
            <div className="map-overlay-hint">
              Shift + drag to select area
            </div>
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
              {catLocationId ? (
                <LocationDetail propertyId={catLocationId} onClose={() => setCatLocationId(null)} />
              ) : catPortfolio ? (
                <CATResults
                  portfolioId={catPortfolio.id}
                  portfolioName={catPortfolio.name}
                  nProperties={catPortfolio.count}
                  onPropertyClick={(id) => setCatLocationId(id)}
                />
              ) : (
                <SyntheticBrowser
                  bbox={catBbox}
                  onClearBbox={() => setCatBbox(null)}
                  onPortfolioCreated={(id, name, count) => setCatPortfolio({ id, name, count })}
                  onPropertyClick={(id) => setCatLocationId(id)}
                />
              )}
              {(catPortfolio || catLocationId) && !catLocationId && (
                <button className="btn btn-outline" style={{ marginTop: 8, width: '100%' }}
                  onClick={() => { setCatPortfolio(null); setCatLocationId(null); }}>
                  Back to Browser
                </button>
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
