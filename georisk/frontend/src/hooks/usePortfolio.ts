import { useState, useCallback } from 'react';
import type { PortfolioResult, PortfolioSummary, PortfolioProperty } from '../types';
import {
  uploadPortfolio,
  fetchPortfolioSummary,
  fetchPortfolioProperties,
} from '../api/client';

export function usePortfolio() {
  const [portfolioId, setPortfolioId] = useState<string | null>(null);
  const [results, setResults] = useState<PortfolioProperty[]>([]);
  const [summary, setSummary] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);

  const upload = useCallback(async (file: File) => {
    setLoading(true);
    setError(null);
    try {
      const data = await uploadPortfolio(file);
      setPortfolioId(data.portfolio_id);
      setResults(data.results);
      setUploadErrors(data.errors);

      const summ = await fetchPortfolioSummary(data.portfolio_id);
      setSummary(summ);

      return data;
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Portfolio upload failed');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const loadPortfolio = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      setPortfolioId(id);
      const [summ, props] = await Promise.all([
        fetchPortfolioSummary(id),
        fetchPortfolioProperties(id),
      ]);
      setSummary(summ);
      setResults(props);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load portfolio');
    } finally {
      setLoading(false);
    }
  }, []);

  const clearPortfolio = useCallback(() => {
    setPortfolioId(null);
    setResults([]);
    setSummary(null);
    setError(null);
    setUploadErrors([]);
  }, []);

  return {
    portfolioId,
    results,
    summary,
    loading,
    error,
    uploadErrors,
    upload,
    loadPortfolio,
    clearPortfolio,
  };
}
