import { MapPin, Briefcase, Radio, BarChart3, Sun, Moon } from 'lucide-react';
import type { Journey, ThemeMode } from '../../types';

interface SidebarProps {
  activeJourney: Journey;
  onJourneyChange: (journey: Journey) => void;
  theme: ThemeMode;
  onToggleTheme: () => void;
}

const journeys = [
  { id: 'explorer' as Journey, label: 'Property Explorer', icon: MapPin, desc: 'Assess individual property risk' },
  { id: 'portfolio' as Journey, label: 'Portfolio Manager', icon: Briefcase, desc: 'Analyze portfolio accumulation' },
  { id: 'cat' as Journey, label: 'CAT Modelling', icon: BarChart3, desc: 'Stochastic pricing & HVE' },
  { id: 'monitor' as Journey, label: 'Data Monitor', icon: Radio, desc: 'Scrape status & data freshness' },
];

export function Sidebar({ activeJourney, onJourneyChange, theme, onToggleTheme }: SidebarProps) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="logo">
          <div className="logo-icon">GR</div>
          <div>
            <h1>GeoRisk</h1>
            <span className="version">Live Dashboard</span>
          </div>
        </div>
      </div>

      <nav className="sidebar-nav">
        {journeys.map(({ id, label, icon: Icon, desc }) => (
          <button
            key={id}
            className={`nav-item ${activeJourney === id ? 'active' : ''}`}
            onClick={() => onJourneyChange(id)}
          >
            <Icon size={20} />
            <div>
              <span className="nav-label">{label}</span>
              <span className="nav-desc">{desc}</span>
            </div>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button className="theme-toggle" onClick={onToggleTheme}>
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          <span>{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>
        </button>
      </div>
    </aside>
  );
}
