import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LocationDetail } from '../LocationDetail';

vi.mock('../../../api/client', async () => {
  const actual = await vi.importActual<any>('../../../api/client');
  return {
    ...actual,
    fetchCatLocationDetail: vi.fn(async () => ({
      exposure: {
        tiv: 1000000,
        construction_type: 'Wood Frame',
        occupancy: 'Residential',
        stories: 1,
        year_built: 2000,
        latitude: 37.77,
        longitude: -122.42,
      },
      hazard: { seismic: { pga_g: 0.3 }, flood: { zone: 'X', estimated_depth_ft: 0.5 }, wind: { max_wind_prob: 10, estimated_speed_mph: 55 } },
      vulnerability: {
        seismic: { mdr: { mean_dr: 0.01, sigma_dr: 0.01, intensity: 0.3, intensity_unit: 'g' }, curve: [] },
        flood: { mdr: { mean_dr: 0.01, sigma_dr: 0.01, intensity: 0.5, intensity_unit: 'ft' }, curve: [] },
        wind: { mdr: { mean_dr: 0.01, sigma_dr: 0.01, intensity: 55, intensity_unit: 'mph' }, curve: [] },
      },
      loss: { technical_rate_pct: 1.0, total_loaded_rate_pct: 1.2, total_premium: 12000, total_aal: 10000, total_risk_load_factor: 0.1, pml: { '250': 500000, '500': 700000 }, peril_breakdown: {} },
      ep_curves: {},
    })),
    fetchCatEventSets: vi.fn(async () => []),
    fetchCatEventSet: vi.fn(async () => null),
  };
});

describe('LocationDetail', () => {
  it('renders exposure section', async () => {
    render(<LocationDetail propertyId={1} sessionId={null} onClose={() => {}} />);
    expect(await screen.findByText(/Location Risk Detail/i)).toBeInTheDocument();
    expect(await screen.findByText(/Exposure/i)).toBeInTheDocument();
  });
});

