import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
} from 'recharts';

const RISK_COLORS: Record<string, string> = {
  Low: '#4caf50',
  Moderate: '#ff9800',
  High: '#f44336',
  'Very High': '#d32f2f',
  Extreme: '#880e4f',
};

const PERIL_COLORS: Record<string, string> = {
  seismic: '#f44336',
  flood: '#2196f3',
  wind: '#ff9800',
};

interface RiskDistributionProps {
  data: Record<string, number>;
}

export function RiskDistributionChart({ data }: RiskDistributionProps) {
  const chartData = Object.entries(data)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));

  return (
    <div className="chart-container">
      <h4>Risk Distribution</h4>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie data={chartData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={70} label={({ name, value }) => `${name}: ${value}`}>
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={RISK_COLORS[entry.name] || '#999'} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

interface PerilAveragesProps {
  data: Record<string, number>;
}

export function PerilAveragesChart({ data }: PerilAveragesProps) {
  const chartData = Object.entries(data).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    score: value,
  }));

  return (
    <div className="chart-container">
      <h4>Average Peril Scores</h4>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="name" stroke="#aaa" />
          <YAxis domain={[0, 100]} stroke="#aaa" />
          <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid #333' }} />
          <Bar dataKey="score" radius={[4, 4, 0, 0]}>
            {chartData.map((entry) => (
              <Cell key={entry.name} fill={PERIL_COLORS[entry.name.toLowerCase()] || '#666'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

interface RadarProps {
  seismic: number;
  flood: number;
  wind: number;
}

export function RiskRadarChart({ seismic, flood, wind }: RadarProps) {
  const chartData = [
    { peril: 'Seismic', score: seismic },
    { peril: 'Flood', score: flood },
    { peril: 'Wind', score: wind },
  ];

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={220}>
        <RadarChart data={chartData}>
          <PolarGrid stroke="#444" />
          <PolarAngleAxis dataKey="peril" stroke="#ccc" />
          <PolarRadiusAxis domain={[0, 100]} stroke="#555" />
          <Radar dataKey="score" stroke="#00e5ff" fill="#00e5ff" fillOpacity={0.3} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
