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
});

