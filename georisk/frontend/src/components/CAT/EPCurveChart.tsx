import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface EPPoint { return_period: number; loss: number }
interface ModelCurve { model_id: string; label: string; weight: number; oep: EPPoint[] }

interface EPCurveChartProps {
  oep: EPPoint[];
  aep?: EPPoint[];
  models?: ModelCurve[];
  peril: string;
  height?: number;
}

const MODEL_COLORS = ['#ff6b6b', '#51cf66', '#339af0'];
const PERIL_COLORS: Record<string, string> = { seismic: '#f44336', flood: '#2196f3', wind: '#ff9800', all_perils: '#00e5ff' };

export function EPCurveChart({ oep, aep, models, peril, height = 250 }: EPCurveChartProps) {
  const rps = [10, 25, 50, 100, 250, 500, 1000];
  const blendColor = PERIL_COLORS[peril] || '#00e5ff';

  const data = rps.map(rp => {
    const row: any = { rp };
    const oepPt = oep.find(p => p.return_period === rp);
    row.blended_oep = oepPt ? oepPt.loss : 0;
    if (aep) {
      const aepPt = aep.find(p => p.return_period === rp);
      row.blended_aep = aepPt ? aepPt.loss : 0;
    }
    models?.forEach((m, i) => {
      const mPt = m.oep.find(p => p.return_period === rp);
      row[`model_${i}`] = mPt ? mPt.loss : 0;
    });
    return row;
  });

  const fmt = (v: number) => {
    if (v >= 1e6) return `$${(v / 1e6).toFixed(1)}M`;
    if (v >= 1e3) return `$${(v / 1e3).toFixed(0)}K`;
    return `$${v.toFixed(0)}`;
  };

  return (
    <div className="chart-container">
      <h4 style={{ fontSize: 12, marginBottom: 4 }}>
        {peril === 'all_perils' ? 'All Perils' : peril.charAt(0).toUpperCase() + peril.slice(1)} EP Curve
      </h4>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="rp" stroke="#aaa" tick={{ fontSize: 10 }}
            label={{ value: 'Return Period (yr)', position: 'insideBottom', offset: -2, fontSize: 10, fill: '#888' }} />
          <YAxis stroke="#aaa" tick={{ fontSize: 10 }} tickFormatter={fmt} />
          <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333', fontSize: 11 }}
            formatter={(v: any) => [fmt(Number(v || 0)), 'Loss']} labelFormatter={(v: any) => `${v}-yr`} />
          <Legend wrapperStyle={{ fontSize: 10 }} />
          <Line type="monotone" dataKey="blended_oep" name="Blended OEP" stroke={blendColor} strokeWidth={3} dot={{ r: 3 }} />
          {aep && <Line type="monotone" dataKey="blended_aep" name="Blended AEP" stroke={blendColor} strokeWidth={2} strokeDasharray="5 5" dot={{ r: 2 }} />}
          {models?.map((m, i) => (
            <Line key={m.model_id} type="monotone" dataKey={`model_${i}`} name={`${m.label} (${(m.weight * 100).toFixed(0)}%)`}
              stroke={MODEL_COLORS[i % MODEL_COLORS.length]} strokeWidth={1} strokeDasharray="3 3" dot={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
