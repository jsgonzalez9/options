import React from 'react';
import { 
  BarChart3, 
  TrendingUp, 
  Wallet, 
  Settings, 
  BookOpen, 
  AlertCircle,
  PieChart,
  Activity
} from 'lucide-react';

interface NavItemProps {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
}

const NavItem: React.FC<NavItemProps> = ({ icon, label, active = false }) => {
  return (
    <a
      href="#"
      className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${
        active
          ? 'bg-primary-50 text-primary-700 border-r-2 border-primary-600'
          : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
      }`}
    >
      {icon}
      <span className="font-medium">{label}</span>
    </a>
  );
};

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 bg-white border-r border-gray-200 min-h-screen">
      <nav className="p-4 space-y-2">
        <NavItem icon={<BarChart3 className="w-5 h-5" />} label="Dashboard" active />
        <NavItem icon={<TrendingUp className="w-5 h-5" />} label="Options Chain" />
        <NavItem icon={<PieChart className="w-5 h-5" />} label="Portfolio" />
        <NavItem icon={<Activity className="w-5 h-5" />} label="Positions" />
        <NavItem icon={<Wallet className="w-5 h-5" />} label="Watchlist" />
        <NavItem icon={<AlertCircle className="w-5 h-5" />} label="Alerts" />
        <NavItem icon={<BookOpen className="w-5 h-5" />} label="Education" />
        <NavItem icon={<Settings className="w-5 h-5" />} label="Settings" />
      </nav>
      
      {/* Market Status */}
      <div className="p-4 mt-8">
        <div className="bg-success-50 border border-success-200 rounded-lg p-3">
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-success-500 rounded-full animate-pulse"></div>
            <span className="text-sm font-medium text-success-700">Market Open</span>
          </div>
          <p className="text-xs text-success-600 mt-1">NYSE: 9:30 AM - 4:00 PM EST</p>
        </div>
      </div>
    </aside>
  );
};