import axios from 'axios';
import type {
  Property,
  RiskScorecard,
  ScrapeStatus,
  MapLayer,
  PortfolioResult,
  PortfolioSummary,
  PortfolioProperty,
} from '../types';

/** Default API client (60s) — fine for map layers, CRUD, and small queries. */
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  timeout: 60000,
});

/**
 * CAT simulation, EP aggregation, location drill-down, and manual scrapes can exceed 60s.
 * Use this client so the browser does not abort while the backend is still computing.
 */
const apiLong = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  timeout: 20 * 60 * 1000,
});

export async function fetchProperties(): Promise<Property[]> {
  const { data } = await api.get('/properties/');
  return data;
}

export async function fetchPropertyRisk(propertyId: number): Promise<RiskScorecard> {
  const { data } = await api.get(`/properties/${propertyId}/risk`);
  return data;
}

export async function lookupAddress(address: string): Promise<{ property: Property; risk: RiskScorecard }> {
  const { data } = await api.post(`/properties/lookup-address?address=${encodeURIComponent(address)}`);
  return data;
}

export async function fetchDataCatalog(): Promise<ScrapeStatus[]> {
  const { data } = await api.get('/data/catalog');
  return data;
}

export async function triggerScrape(source: string): Promise<{ source: string; status: string; records_fetched: number; message: string }> {
  const { data } = await apiLong.post('/data/scrape', { source });
  return data;
}

export async function fetchMapLayers(): Promise<MapLayer[]> {
  const { data } = await api.get('/map/layers');
  return data;
}

export async function fetchLayerGeoJSON(layerId: string): Promise<GeoJSON.FeatureCollection> {
  const { data } = await api.get(`/map/layer/${layerId}`);
  return data;
}

export async function fetchPropertiesGeoJSON(): Promise<GeoJSON.FeatureCollection> {
  const { data } = await api.get('/map/properties-geojson');
  return data;
}

export async function uploadPortfolio(file: File): Promise<PortfolioResult> {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await api.post('/portfolio/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function runCATForUploadedPortfolio(portfolioId: string, params: { n_years?: number; max_properties?: number } = {}): Promise<any> {
  const qs = new URLSearchParams();
  if (params.n_years) qs.set('n_years', String(params.n_years));
  if (params.max_properties) qs.set('max_properties', String(params.max_properties));
  const { data } = await apiLong.post(`/portfolio/${encodeURIComponent(portfolioId)}/run-cat?${qs.toString()}`);
  return data;
}

export async function fetchPortfolioSummary(portfolioId: string): Promise<PortfolioSummary> {
  const { data } = await api.get(`/portfolio/${portfolioId}/summary`);
  return data;
}

export async function fetchPortfolioProperties(portfolioId: string): Promise<PortfolioProperty[]> {
  const { data } = await api.get(`/portfolio/${portfolioId}/properties`);
  return data;
}

export async function fetchPortfolioAccumulation(portfolioId: string): Promise<GeoJSON.FeatureCollection> {
  const { data } = await api.get(`/portfolio/${portfolioId}/accumulation-geojson`);
  return data;
}

export function getPortfolioExportUrl(portfolioId: string): string {
  const base = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
  return `${base}/portfolio/${portfolioId}/export`;
}

export function getCatExportResultsUrl(portfolioId: string, sessionId?: string | null): string {
  const base = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
  const qs = sessionId ? `?session_id=${encodeURIComponent(String(sessionId))}` : '';
  return `${base}/cat/export/results/${encodeURIComponent(String(portfolioId))}${qs}`;
}

export function getCatExportEpCurveUrl(portfolioId: string, sessionId?: string | null): string {
  const base = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
  const qs = sessionId ? `?session_id=${encodeURIComponent(String(sessionId))}` : '';
  return `${base}/cat/export/ep-curve/${encodeURIComponent(String(portfolioId))}${qs}`;
}

export function getCatExportEventSetUrl(eventSetId: string): string {
  const base = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
  return `${base}/cat/export/event-set/${encodeURIComponent(String(eventSetId))}`;
}

export async function fetchSyntheticSummary(sampleN = 20000): Promise<any> {
  const { data } = await api.get(`/synthetic/summary?sample_n=${sampleN}`);
  return data;
}

export async function fetchSyntheticAccumulationHex(resolution = 5, sampleN = 200000, topK = 200): Promise<GeoJSON.FeatureCollection> {
  const { data } = await api.get(`/synthetic/accumulation-hex?resolution=${resolution}&sample_n=${sampleN}&top_k=${topK}`);
  return data;
}

export async function fetchSyntheticStats(): Promise<any> {
  const { data } = await api.get('/synthetic/stats');
  return data;
}

export async function seedSynthetic(body: any): Promise<any> {
  const { data } = await apiLong.post('/synthetic/seed', body);
  return data;
}

export async function fetchCATSessions(): Promise<any[]> {
  const { data } = await api.get('/cat/sessions');
  return data;
}

export async function fetchCATSession(sessionId: string): Promise<any> {
  const { data } = await api.get(`/cat/sessions/${sessionId}`);
  return data;
}

export async function deleteCATSession(sessionId: string): Promise<any> {
  const { data } = await api.delete(`/cat/sessions/${sessionId}`);
  return data;
}

export async function runCATModel(body: { portfolio_id: string; n_years?: number; max_properties?: number }): Promise<any> {
  const { data } = await apiLong.post('/cat/run-model', body);
  return data;
}

export async function fetchCATEpCurve(portfolioId: string, params: { n_years?: number; max_properties?: number } = {}): Promise<any> {
  const qs = new URLSearchParams();
  if (params.n_years) qs.set('n_years', String(params.n_years));
  if (params.max_properties) qs.set('max_properties', String(params.max_properties));
  const { data } = await apiLong.get(`/cat/ep-curve/${encodeURIComponent(portfolioId)}?${qs.toString()}`);
  return data;
}

export async function fetchCATDiversification(portfolioId: string, returnPeriod = 250): Promise<any> {
  const { data } = await apiLong.get(`/cat/diversification/${encodeURIComponent(portfolioId)}?return_period=${returnPeriod}`);
  return data;
}

export async function fetchCatLocationDetail(propertyId: number, nYears = 5000): Promise<any> {
  const { data } = await apiLong.get(`/cat/location-detail/${propertyId}?n_years=${nYears}`);
  return data;
}

export async function fetchPortfolioGeoJSON(portfolioId: string, limit = 5000): Promise<GeoJSON.FeatureCollection> {
  const { data } = await api.get(`/synthetic/portfolio/${portfolioId}/geojson?limit=${limit}`);
  return data;
}

export async function fetchScoredGeoJSON(portfolioId: string, limit = 5000): Promise<GeoJSON.FeatureCollection> {
  const { data } = await api.get(`/synthetic/portfolio/${portfolioId}/scored-geojson?limit=${limit}`);
  return data;
}

export async function filterSynthetic(body: any): Promise<any> {
  const { data } = await api.post('/synthetic/filter', body);
  return data;
}

export async function buildSyntheticPortfolio(body: any): Promise<any> {
  const { data } = await api.post('/synthetic/build-portfolio', body);
  return data;
}

export async function fetchCatEventSets(sessionId: string, propertyId?: number): Promise<any[]> {
  const qs = new URLSearchParams({ session_id: sessionId });
  if (typeof propertyId === 'number') qs.set('property_id', String(propertyId));
  const { data } = await api.get(`/cat/event-sets?${qs.toString()}`);
  return data;
}

export async function fetchCatEventSet(eventSetId: string): Promise<any> {
  const { data } = await apiLong.get(`/cat/event-set/${eventSetId}`);
  return data;
}

export async function fetchCatEventSetEvents(eventSetId: string, params: any): Promise<any> {
  const qs = new URLSearchParams(params || {});
  const { data } = await api.get(`/cat/event-set/${eventSetId}/events?${qs.toString()}`);
  return data;
}
