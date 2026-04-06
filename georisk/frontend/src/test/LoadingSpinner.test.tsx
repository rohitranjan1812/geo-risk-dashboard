import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LoadingSpinner } from '../components/common/LoadingSpinner';

describe('LoadingSpinner', () => {
  it('renders spinner element', () => {
    const { container } = render(<LoadingSpinner />);
    expect(container.querySelector('.loading-spinner')).toBeTruthy();
  });

  it('renders with custom text', () => {
    render(<LoadingSpinner text="Loading data..." />);
    expect(screen.getByText('Loading data...')).toBeTruthy();
  });

  it('renders without text when not provided', () => {
    const { container } = render(<LoadingSpinner />);
    const spans = container.querySelectorAll('.loading-spinner span');
    expect(spans.length).toBe(0);
  });
});
