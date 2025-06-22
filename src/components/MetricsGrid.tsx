import React from 'react';
import { TrendingUp, TrendingDown, DollarSign, Target, Activity, Percent } from 'lucide-react';

interface MetricCardProps {
  title: string;
  value: string;
  change: string;
  changeType: 'positive' | 'negative' | 'neutral';
  icon: React.ReactNode;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, change, changeType, icon }) => {
  const changeColor = {
    positive: 'text-success-600',
    negative: 'text-danger-600',
    neutral: 'text-gray-500'
  }[changeType];

  const changeIcon = changeType === 'positive' ? 
    <TrendingUp className="w-4 h-4" /> : 
    changeType === 'negative' ? 
    <TrendingDown className="w-4 h-4" /> : null;

  return (
    <div className="metric-card">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-primary-50 rounded-lg">
            {icon}
          </div>
          <div>
            <p className="metric-label">{title}</p>
            <p className="metric-value">{value}</p>
          </div>
        </div>
        <div className={`flex items-center space-x-1 ${changeColor}`}>
          {changeIcon}
          <span className="metric-change">{change}</span>
        </div>
      </div>
    </div>
  );
};

export const MetricsGrid: React.FC = () => {
  const metrics = [
    {
      title: 'Portfolio Value',
      value: '$127,450',
      change: '+5.2%',
      changeType: 'positive' as const,
      icon: <DollarSign className="w-5 h-5 text-primary-600" />
    },
    {
      title: 'Total P&L',
      value: '+$8,240',
      change: '+12.4%',
      changeType: 'positive' as const,
      icon: <TrendingUp className="w-5 h-5 text-primary-600" />
    },
    {
      title: 'Win Rate',
      value: '68.5%',
      change: '+2.1%',
      changeType: 'positive' as const,
      icon: <Target className="w-5 h-5 text-primary-600" />
    },
    {
      title: 'Active Positions',
      value: '24',
      change: '+3',
      changeType: 'positive' as const,
      icon: <Activity className="w-5 h-5 text-primary-600" />
    },
    {
      title: 'Avg. IV Rank',
      value: '42.3%',
      change: '-1.8%',
      changeType: 'negative' as const,
      icon: <Percent className="w-5 h-5 text-primary-600" />
    },
    {
      title: 'Theta Decay',
      value: '-$156',
      change: 'Daily',
      changeType: 'neutral' as const,
      icon: <Activity className="w-5 h-5 text-primary-600" />
    }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
      {metrics.map((metric, index) => (
        <MetricCard key={index} {...metric} />
      ))}
    </div>
  );
};