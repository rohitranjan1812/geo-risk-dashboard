import { useState, useCallback } from 'react';
import type { RiskScorecard, Property } from '../types';
import { fetchPropertyRisk, lookupAddress } from '../api/client';

export function useRiskQuery() {
  const [scorecard, setScorecard] = useState<RiskScorecard | null>(null);
  const [selectedProperty, setSelectedProperty] = useState<Property | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const queryPropertyRisk = useCallback(async (propertyId: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPropertyRisk(propertyId);
      setScorecard(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch risk data');
    } finally {
      setLoading(false);
    }
  }, []);

  const queryAddress = useCallback(async (address: string) => {
    setLoading(true);
    setError(null);
    try {
      const { property, risk } = await lookupAddress(address);
      setSelectedProperty(property);
      setScorecard(risk);
      return { property, risk };
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Address lookup failed');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const clearRisk = useCallback(() => {
    setScorecard(null);
    setSelectedProperty(null);
    setError(null);
  }, []);

  return {
    scorecard,
    selectedProperty,
    setSelectedProperty,
    loading,
    error,
    queryPropertyRisk,
    queryAddress,
    clearRisk,
  };
}
