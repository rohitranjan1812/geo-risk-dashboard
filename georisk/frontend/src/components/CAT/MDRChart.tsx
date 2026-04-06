import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceDot } from 'recharts';

interface MDRChartProps {
  curve: Array<{ intensity: number; mean_dr: number; sigma_dr: number }>;
  operatingPoint?: { intensity: number; mean_dr: number };
  peril: string;
  intensityUnit: string;
}

const PERIL_COLORS: Record<string, string> = { seismic: '#f44336', flood: '#2196f3', wind: '#ff9800' };

export function MDRChart({ curve, operatingPoint, peril, intensityUnit }: MDRChartProps) {
  const color = PERIL_COLORS[peril] || '#999';
  const data = curve.map(p => ({
    intensity: p.intensity,
    mean_dr: p.mean_dr,
    upper: Math.min(1, p.mean_dr + p.sigma_dr),
    lower: Math.max(0, p.mean_dr - p.sigma_dr),
  }));

  return (
    <div className="chart-container" style={{ padding: 8 }}>
      <h4 style={{ fontSize: 12, marginBottom: 4 }}>{peril.charAt(0).toUpperCase() + peril.slice(1)} Damage Function</h4>
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="intensity" stroke="#aaa" tick={{ fontSize: 10 }}
            label={{ value: intensityUnit, position: 'insideBottom', offset: -2, fontSize: 10, fill: '#888' }} />
          <YAxis domain={[0, 1]} stroke="#aaa" tick={{ fontSize: 10 }}
            label={{ value: 'MDR', angle: -90, position: 'insideLeft', fontSize: 10, fill: '#888' }} />
          <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333', fontSize: 11 }}
            formatter={(v: any) => [`${(Number(v || 0) * 100).toFixed(1)}%`, 'MDR']} />
          <Area type="monotone" dataKey="upper" stroke="none" fill={color} fillOpacity={0.1} />
          <Area type="monotone" dataKey="lower" stroke="none" fill={color} fillOpacity={0.1} />
          <Area type="monotone" dataKey="mean_dr" stroke={color} fill={color} fillOpacity={0.25} strokeWidth={2} />
          {operatingPoint && (
            <ReferenceDot x={operatingPoint.intensity} y={operatingPoint.mean_dr}
              r={6} fill="#fff" stroke={color} strokeWidth={2} />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
