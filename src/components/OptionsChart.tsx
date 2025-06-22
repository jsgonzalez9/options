import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';

const data = [
  { date: '2024-01-01', pnl: 1200, cumulative: 1200 },
  { date: '2024-01-02', pnl: -800, cumulative: 400 },
  { date: '2024-01-03', pnl: 1500, cumulative: 1900 },
  { date: '2024-01-04', pnl: 300, cumulative: 2200 },
  { date: '2024-01-05', pnl: -400, cumulative: 1800 },
  { date: '2024-01-06', pnl: 2100, cumulative: 3900 },
  { date: '2024-01-07', pnl: 800, cumulative: 4700 },
  { date: '2024-01-08', pnl: -600, cumulative: 4100 },
  { date: '2024-01-09', pnl: 1300, cumulative: 5400 },
  { date: '2024-01-10', pnl: 900, cumulative: 6300 },
  { date: '2024-01-11', pnl: -200, cumulative: 6100 },
  { date: '2024-01-12', pnl: 1600, cumulative: 7700 },
  { date: '2024-01-13', pnl: 400, cumulative: 8100 },
  { date: '2024-01-14', pnl: 140, cumulative: 8240 }
];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-3 border border-gray-200 rounded-lg shadow-lg">
        <p className="text-sm text-gray-600">{`Date: ${label}`}</p>
        <p className="text-sm font-medium text-primary-600">
          {`Cumulative P&L: $${payload[0].value.toLocaleString()}`}
        </p>
      </div>
    );
  }
  return null;
};

export const OptionsChart: React.FC = () => {
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Portfolio Performance</h3>
          <p className="text-sm text-gray-500">Cumulative P&L over time</p>
        </div>
        <div className="flex space-x-2">
          <button className="px-3 py-1 text-xs font-medium bg-primary-100 text-primary-700 rounded-md">7D</button>
          <button className="px-3 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 rounded-md">30D</button>
          <button className="px-3 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 rounded-md">90D</button>
          <button className="px-3 py-1 text-xs font-medium text-gray-500 hover:bg-gray-100 rounded-md">1Y</button>
        </div>
      </div>
      
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <defs>
              <linearGradient id="colorPnl" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.1}/>
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
            <XAxis 
              dataKey="date" 
              stroke="#6b7280"
              fontSize={12}
              tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            />
            <YAxis 
              stroke="#6b7280"
              fontSize={12}
              tickFormatter={(value) => `$${value.toLocaleString()}`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="cumulative"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#colorPnl)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};