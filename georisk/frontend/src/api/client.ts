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

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 60000,
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
  const { data } = await api.post('/data/scrape', { source });
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
  return `http://localhost:8000/api/portfolio/${portfolioId}/export`;
}

export async function fetchSyntheticSummary(sampleN = 20000): Promise<any> {
  const { data } = await api.get(`/synthetic/summary?sample_n=${sampleN}`);
  return data;
}

export async function fetchSyntheticAccumulationHex(resolution = 5, sampleN = 200000, topK = 200): Promise<GeoJSON.FeatureCollection> {
  const { data } = await api.get(`/synthetic/accumulation-hex?resolution=${resolution}&sample_n=${sampleN}&top_k=${topK}`);
  return data;
}
