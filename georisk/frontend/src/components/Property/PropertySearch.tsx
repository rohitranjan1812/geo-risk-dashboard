import { useState, useEffect } from 'react';
import { Search, MapPin, Building2 } from 'lucide-react';
import type { Property } from '../../types';
import { fetchProperties } from '../../api/client';
import { LoadingSpinner } from '../common/LoadingSpinner';

interface PropertySearchProps {
  onPropertySelect: (property: Property) => void;
  onAddressSearch: (address: string) => void;
  loading: boolean;
}

export function PropertySearch({ onPropertySelect, onAddressSearch, loading }: PropertySearchProps) {
  const [address, setAddress] = useState('');
  const [properties, setProperties] = useState<Property[]>([]);
  const [loadingProps, setLoadingProps] = useState(true);

  useEffect(() => {
    fetchProperties()
      .then(setProperties)
      .catch(console.error)
      .finally(() => setLoadingProps(false));
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (address.trim()) onAddressSearch(address.trim());
  };

  return (
    <div className="property-search">
      <form onSubmit={handleSearch} className="search-form">
        <div className="search-input-wrapper">
          <Search size={18} />
          <input
            type="text"
            placeholder="Enter a US address..."
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            disabled={loading}
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={loading || !address.trim()}>
          {loading ? <LoadingSpinner size={16} /> : 'Assess Risk'}
        </button>
      </form>

      <div className="property-list">
        <h3>Sample Properties</h3>
        {loadingProps ? (
          <LoadingSpinner text="Loading..." />
        ) : (
          <div className="property-cards">
            {properties.map((prop) => (
              <button
                key={prop.id}
                className="property-card"
                onClick={() => onPropertySelect(prop)}
              >
                <div className="property-card-header">
                  <Building2 size={16} />
                  <span className="property-name">{prop.name}</span>
                </div>
                <div className="property-card-details">
                  <MapPin size={12} />
                  <span>{prop.address}</span>
                </div>
                <div className="property-card-meta">
                  <span>TIV: ${(prop.tiv / 1e6).toFixed(1)}M</span>
                  <span>{prop.construction_type}</span>
                  <span>{prop.occupancy}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
