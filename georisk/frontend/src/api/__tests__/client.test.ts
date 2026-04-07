import { describe, expect, it } from 'vitest';
import { getCatExportEventSetUrl, getCatExportEpCurveUrl, getCatExportResultsUrl } from '../client';

describe('api client url builders', () => {
  it('builds cat export results url', () => {
    const url = getCatExportResultsUrl('p1', 's1');
    expect(url).toContain('/cat/export/results/p1');
    expect(url).toContain('session_id=s1');
  });

  it('builds ep curve export url', () => {
    const url = getCatExportEpCurveUrl('p2', 's2');
    expect(url).toContain('/cat/export/ep-curve/p2');
    expect(url).toContain('session_id=s2');
  });

  it('builds event set export url', () => {
    const url = getCatExportEventSetUrl('ev123');
    expect(url).toContain('/cat/export/event-set/ev123');
  });
});

