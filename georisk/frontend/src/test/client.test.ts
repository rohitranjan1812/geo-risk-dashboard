import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';

// Mock axios before importing the client module
vi.mock('axios', () => {
  const mockAxios: any = {
    create: vi.fn(() => mockAxios),
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  return { default: mockAxios };
});

// Import after mocking
import * as client from '../api/client';

const mockedAxios = axios as any;

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('fetchProperties', () => {
    it('calls GET /properties/', async () => {
      const mockData = [{ id: 1, name: 'Test', latitude: 37.77, longitude: -122.42 }];
      mockedAxios.get.mockResolvedValue({ data: mockData });

      const result = await client.fetchProperties();
      expect(mockedAxios.get).toHaveBeenCalledWith('/properties/');
      expect(result).toEqual(mockData);
    });
  });

  describe('fetchPropertyRisk', () => {
    it('calls GET /properties/{id}/risk', async () => {
      const mockData = { property_id: 1, composite_score: 45 };
      mockedAxios.get.mockResolvedValue({ data: mockData });

      const result = await client.fetchPropertyRisk(1);
      expect(mockedAxios.get).toHaveBeenCalledWith('/properties/1/risk');
      expect(result.composite_score).toBe(45);
    });
  });

  describe('lookupAddress', () => {
    it('calls POST /properties/lookup-address', async () => {
      const mockData = {
        property: { id: 1, latitude: 37.77, longitude: -122.42 },
        risk: { composite_score: 50 },
      };
      mockedAxios.post.mockResolvedValue({ data: mockData });

      const result = await client.lookupAddress('123 Main St');
      expect(mockedAxios.post).toHaveBeenCalled();
      expect(result.risk.composite_score).toBe(50);
    });
  });

  describe('fetchDataCatalog', () => {
    it('calls GET /data/catalog', async () => {
      const mockData = [{ source: 'usgs_earthquake', status: 'fresh' }];
      mockedAxios.get.mockResolvedValue({ data: mockData });

      const result = await client.fetchDataCatalog();
      expect(mockedAxios.get).toHaveBeenCalledWith('/data/catalog');
      expect(result[0].source).toBe('usgs_earthquake');
    });
  });

  describe('triggerScrape', () => {
    it('calls POST /data/scrape', async () => {
      const mockData = { source: 'usgs_earthquake', status: 'success', records_fetched: 100 };
      mockedAxios.post.mockResolvedValue({ data: mockData });

      const result = await client.triggerScrape('usgs_earthquake');
      expect(mockedAxios.post).toHaveBeenCalledWith('/data/scrape', { source: 'usgs_earthquake' });
      expect(result.records_fetched).toBe(100);
    });
  });

  describe('fetchMapLayers', () => {
    it('calls GET /map/layers', async () => {
      const mockData = [{ id: 'earthquakes', name: 'Recent Earthquakes' }];
      mockedAxios.get.mockResolvedValue({ data: mockData });

      const result = await client.fetchMapLayers();
      expect(mockedAxios.get).toHaveBeenCalledWith('/map/layers');
      expect(result[0].id).toBe('earthquakes');
    });
  });

  describe('fetchLayerGeoJSON', () => {
    it('calls GET /map/layer/{id}', async () => {
      const mockData = { type: 'FeatureCollection', features: [] };
      mockedAxios.get.mockResolvedValue({ data: mockData });

      const result = await client.fetchLayerGeoJSON('earthquakes');
      expect(mockedAxios.get).toHaveBeenCalledWith('/map/layer/earthquakes');
      expect(result.type).toBe('FeatureCollection');
    });
  });

  describe('uploadPortfolio', () => {
    it('calls POST /portfolio/upload with form data', async () => {
      const mockData = {
        portfolio_id: 'p-123',
        properties_loaded: 10,
        errors: [],
        results: [],
      };
      mockedAxios.post.mockResolvedValue({ data: mockData });

      const file = new File(['csv data'], 'test.csv', { type: 'text/csv' });
      const result = await client.uploadPortfolio(file);
      expect(mockedAxios.post).toHaveBeenCalledWith(
        '/portfolio/upload',
        expect.any(FormData),
        expect.objectContaining({ headers: { 'Content-Type': 'multipart/form-data' } }),
      );
      expect(result.portfolio_id).toBe('p-123');
    });
  });

  describe('fetchPortfolioSummary', () => {
    it('calls GET /portfolio/{id}/summary', async () => {
      const mockData = { portfolio_id: 'p-1', total_properties: 5 };
      mockedAxios.get.mockResolvedValue({ data: mockData });

      const result = await client.fetchPortfolioSummary('p-1');
      expect(mockedAxios.get).toHaveBeenCalledWith('/portfolio/p-1/summary');
      expect(result.total_properties).toBe(5);
    });
  });

  describe('getPortfolioExportUrl', () => {
    it('returns correct URL', () => {
      const url = client.getPortfolioExportUrl('abc-123');
      expect(url).toBe('http://localhost:8000/api/portfolio/abc-123/export');
    });
  });

  describe('fetchCATSessions', () => {
    it('calls GET /cat/sessions', async () => {
      const mockData = [{ session_id: 's-1', status: 'created' }];
      mockedAxios.get.mockResolvedValue({ data: mockData });

      const result = await client.fetchCATSessions();
      expect(mockedAxios.get).toHaveBeenCalledWith('/cat/sessions');
      expect(result[0].session_id).toBe('s-1');
    });
  });

  describe('deleteCATSession', () => {
    it('calls DELETE /cat/sessions/{id}', async () => {
      mockedAxios.delete.mockResolvedValue({ data: { status: 'deleted' } });

      const result = await client.deleteCATSession('s-1');
      expect(mockedAxios.delete).toHaveBeenCalledWith('/cat/sessions/s-1');
      expect(result.status).toBe('deleted');
    });
  });

  describe('seedSynthetic', () => {
    it('calls POST /synthetic/seed', async () => {
      const body = { count: 1000, bbox: [-125, 24, -66, 50] };
      mockedAxios.post.mockResolvedValue({ data: { count: 1000 } });

      const result = await client.seedSynthetic(body);
      expect(mockedAxios.post).toHaveBeenCalledWith('/synthetic/seed', body);
      expect(result.count).toBe(1000);
    });
  });
});
