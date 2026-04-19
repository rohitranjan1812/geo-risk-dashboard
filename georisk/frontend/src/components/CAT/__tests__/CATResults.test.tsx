import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CATResults } from '../CATResults';

describe('CATResults', () => {
  it('renders header', () => {
    render(
      <CATResults
        portfolioId="p1"
        portfolioName="Test Portfolio"
        nProperties={10}
        onPropertyClick={() => {}}
      />
    );
    expect(screen.getByText('Test Portfolio')).toBeInTheDocument();
    expect(screen.getByText(/10 properties/i)).toBeInTheDocument();
  });

  it('hydrates from initialResult (loaded session) without firing a simulation', () => {
    // Shape returned by /cat/sessions/{id}: dashboard should populate immediately.
    const session = {
      session: {
        session_id: 'abc123',
        portfolio_tiv: 5_000_000,
        portfolio_aal: 50_000,
        portfolio_premium: 75_000,
      },
      property_rows: [
        { property_id: 1, tiv: 1_000_000, total_aal: 10_000, technical_rate_pct: 1.0,
          total_loaded_rate_pct: 1.5, total_premium: 15_000, pml_250: 50_000 },
      ],
      ep_curves: {
        seismic: { oep: [{ return_period: 250, loss: 10_000, probability: 0.004 }], aep: [], models: [] },
        flood: { oep: [], aep: [], models: [] },
        wind: { oep: [], aep: [], models: [] },
        all_perils: { oep: [{ return_period: 250, loss: 50_000, probability: 0.004 }] },
      },
      diversification: {
        return_period: 250,
        diversification_pct: 12.5,
        portfolio_pml: 40_000,
        hhi_concentration: 0.2,
        accounts: [],
      },
    };

    render(
      <CATResults
        portfolioId="p1"
        portfolioName="Loaded Portfolio"
        nProperties={1}
        onPropertyClick={() => {}}
        initialResult={session}
      />
    );

    // Summary cards from the loaded session should be visible without any fetch.
    expect(screen.getByText(/Portfolio TIV/i)).toBeInTheDocument();
    expect(screen.getByText(/Portfolio AAL/i)).toBeInTheDocument();
    // Tabs are rendered only after a model result is available.
    expect(screen.getByRole('button', { name: /Overview/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Ep$/i })).toBeInTheDocument();
  });
});

