export interface Property {
  id: number;
  name: string | null;
  address: string | null;
  latitude: number;
  longitude: number;
  tiv: number;
  construction_type: string;
  occupancy: string;
  year_built: number | null;
  stories: number;
  created_at?: string;
}

export interface HazardScore {
  peril: string;
  score: number;
  raw_value: number | null;
  unit: string | null;
  source: string | null;
  description: string | null;
}

export interface RiskScorecard {
  property_id: number;
  latitude: number;
  longitude: number;
  address: string | null;
  seismic: HazardScore | null;
  flood: HazardScore | null;
  wind: HazardScore | null;
  composite_score: number;
  risk_tier: string;
  scored_at: string | null;
}

export interface ScrapeStatus {
  source: string;
  description: string | null;
  last_scraped: string | null;
  record_count: number;
  freshness_hours: number | null;
  status: string;
}

export interface MapLayer {
  id: string;
  name: string;
  type: string;
  source: string;
  file: string;
  available: boolean;
}

export interface PortfolioResult {
  portfolio_id: string;
  properties_loaded: number;
  errors: string[];
  results: PortfolioProperty[];
}

export interface PortfolioProperty {
  property_id: number;
  name?: string;
  address?: string;
  latitude: number;
  longitude: number;
  tiv: number;
  seismic_score: number;
  flood_score: number;
  wind_score: number;
  composite_score: number;
  rate_factor: number;
  risk_tier?: string;
  h3_index?: string;
}

export interface PortfolioSummary {
  portfolio_id: string;
  total_properties: number;
  total_tiv: number;
  avg_composite_score: number;
  max_composite_score: number;
  risk_distribution: Record<string, number>;
  peril_averages: Record<string, number>;
  top_accumulations: Array<{
    h3_index: string;
    count: number;
    total_tiv: number;
    avg_score: number;
  }>;
}

export type Journey = 'explorer' | 'portfolio' | 'cat' | 'monitor';

export type ThemeMode = 'dark' | 'light';
