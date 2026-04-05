import { useState, useRef } from 'react';
import { Upload, FileText, AlertCircle, Download } from 'lucide-react';
import { LoadingSpinner } from '../common/LoadingSpinner';

interface PortfolioUploadProps {
  onUpload: (file: File) => Promise<any>;
  loading: boolean;
  error: string | null;
}

const SAMPLE_CSV = `name,address,latitude,longitude,tiv,construction_type,occupancy,year_built,stories
Downtown Office,100 Broadway New York NY,40.7128,-74.006,12000000,Steel Frame,Commercial,2005,25
Beach Resort,200 Collins Ave Miami Beach FL,25.7907,-80.13,8500000,Reinforced Concrete,Hospitality,2010,15
Warehouse District,300 Magazine St New Orleans LA,29.9391,-90.0715,3200000,Concrete Tilt-Up,Industrial,1998,2
Tech Campus,400 University Ave Palo Alto CA,37.4419,-122.143,15000000,Steel Frame,Commercial,2015,4
Gulf Refinery,500 Refinery Rd Texas City TX,29.3838,-94.9027,25000000,Steel,Industrial,1990,3
Historic Inn,600 Meeting St Charleston SC,32.7876,-79.937,2100000,Wood Frame,Hospitality,1870,3
Mountain Lodge,700 Ski Run Blvd Lake Tahoe CA,38.9399,-119.9772,4500000,Wood Frame,Hospitality,2008,3
Port Facility,800 Harbor Dr Long Beach CA,33.7524,-118.1937,18000000,Steel,Industrial,1985,1
Medical Center,900 Hospital Dr Memphis TN,35.1269,-89.9253,9000000,Reinforced Concrete,Healthcare,2012,8
Retail Mall,1000 Mall Dr Anchorage AK,61.1904,-149.8929,7500000,Steel Frame,Commercial,2003,2`;

export function PortfolioUpload({ onUpload, loading, error }: PortfolioUploadProps) {
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    if (!file.name.endsWith('.csv')) {
      alert('Please upload a CSV file');
      return;
    }
    await onUpload(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const downloadSample = () => {
    const blob = new Blob([SAMPLE_CSV], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sample_portfolio.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const uploadSampleDirect = async () => {
    const blob = new Blob([SAMPLE_CSV], { type: 'text/csv' });
    const file = new File([blob], 'sample_portfolio.csv', { type: 'text/csv' });
    await onUpload(file);
  };

  return (
    <div className="portfolio-upload">
      <h2>Portfolio Risk Analysis</h2>
      <p className="upload-desc">
        Upload a CSV of properties to score each against all hazard layers and get portfolio-level analytics.
      </p>

      <div
        className={`drop-zone ${dragOver ? 'drag-over' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
      >
        {loading ? (
          <LoadingSpinner size={32} text="Processing portfolio..." />
        ) : (
          <>
            <Upload size={40} />
            <p>Drop CSV file here or click to browse</p>
            <span className="drop-hint">Required: latitude, longitude (or address), tiv</span>
          </>
        )}
        <input
          ref={fileRef}
          type="file"
          accept=".csv"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
      </div>

      <div className="sample-actions">
        <button className="btn btn-outline" onClick={downloadSample}>
          <Download size={16} /> Download Sample CSV
        </button>
        <button className="btn btn-primary" onClick={uploadSampleDirect} disabled={loading}>
          <FileText size={16} /> Load Sample Portfolio
        </button>
      </div>

      {error && (
        <div className="error-banner">
          <AlertCircle size={16} /> {error}
        </div>
      )}
    </div>
  );
}
