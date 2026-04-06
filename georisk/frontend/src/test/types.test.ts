import { describe, it, expect } from 'vitest';
import type {
  Property,
  HazardScore,
  RiskScorecard,
  ScrapeStatus,
  MapLayer,
  PortfolioResult,
  PortfolioProperty,
  PortfolioSummary,
} from '../types';

describe('TypeScript interfaces', () => {
  it('creates a valid Property', () => {
    const prop: Property = {
      id: 1,
      name: 'Test Property',
      address: '123 Main St',
      latitude: 37.77,
      longitude: -122.42,
      tiv: 1_000_000,
      construction_type: 'Steel Frame',
      occupancy: 'Commercial',
      year_built: 2005,
      stories: 10,
    };
    expect(prop.id).toBe(1);
    expect(prop.latitude).toBe(37.77);
  });

  it('allows null optional Property fields', () => {
    const prop: Property = {
      id: 2,
      name: null,
      address: null,
      latitude: 0,
      longitude: 0,
      tiv: 0,
      construction_type: 'Unknown',
      occupancy: 'Unknown',
      year_built: null,
      stories: 1,
    };
    expect(prop.name).toBeNull();
    expect(prop.year_built).toBeNull();
  });

  it('creates a valid HazardScore', () => {
    const hs: HazardScore = {
      peril: 'seismic',
      score: 75.5,
      raw_value: 0.7,
      unit: 'g (PGA)',
      source: 'USGS',
      description: 'Very high seismic hazard',
    };
    expect(hs.score).toBe(75.5);
    expect(hs.peril).toBe('seismic');
  });

  it('creates a valid RiskScorecard', () => {
    const sc: RiskScorecard = {
      property_id: 1,
      latitude: 37.77,
      longitude: -122.42,
      address: '123 Main St',
      seismic: { peril: 'seismic', score: 70, raw_value: 0.5, unit: 'g', source: 'USGS', description: 'High' },
      flood: { peril: 'flood', score: 30, raw_value: null, unit: 'Zone X', source: 'FEMA', description: 'Low' },
      wind: { peril: 'wind', score: 10, raw_value: 5, unit: '%', source: 'NOAA', description: 'Minimal' },
      composite_score: 40.5,
      risk_tier: 'High',
      scored_at: '2024-01-01T00:00:00Z',
    };
    expect(sc.composite_score).toBe(40.5);
    expect(sc.risk_tier).toBe('High');
    expect(sc.seismic?.score).toBe(70);
  });

  it('creates a valid ScrapeStatus', () => {
    const ss: ScrapeStatus = {
      source: 'usgs_earthquake',
      description: 'USGS Earthquake Catalog',
      last_scraped: '2024-01-01T00:00:00Z',
      record_count: 500,
      freshness_hours: 0.5,
      status: 'fresh',
    };
    expect(ss.source).toBe('usgs_earthquake');
    expect(ss.record_count).toBe(500);
  });

  it('creates a valid MapLayer', () => {
    const ml: MapLayer = {
      id: 'earthquakes',
      name: 'Recent Earthquakes',
      type: 'circle',
      source: 'USGS',
      file: 'earthquakes_recent.geojson',
      available: true,
    };
    expect(ml.available).toBe(true);
  });

  it('creates a valid PortfolioProperty', () => {
    const pp: PortfolioProperty = {
      property_id: 1,
      latitude: 30.0,
      longitude: -90.0,
      tiv: 500_000,
      seismic_score: 50,
      flood_score: 80,
      wind_score: 60,
      composite_score: 63,
      rate_factor: 1.63,
    };
    expect(pp.composite_score).toBe(63);
    expect(pp.rate_factor).toBe(1.63);
  });

  it('creates a valid PortfolioSummary', () => {
    const ps: PortfolioSummary = {
      portfolio_id: 'abc-123',
      total_properties: 100,
      total_tiv: 50_000_000,
      avg_composite_score: 45.2,
      max_composite_score: 92.1,
      risk_distribution: { Low: 20, Moderate: 30, High: 25, 'Very High': 15, Extreme: 10 },
      peril_averages: { seismic: 40.5, flood: 55.2, wind: 38.7 },
      top_accumulations: [{ h3_index: '85283473fffffff', count: 5, total_tiv: 10_000_000, avg_score: 60 }],
    };
    expect(ps.total_properties).toBe(100);
    expect(ps.risk_distribution.Low).toBe(20);
  });
});
