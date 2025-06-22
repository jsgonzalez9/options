import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const volatilityData = [
  { date: '2024-01-01', iv: 28.5, hv: 24.2, ivRank: 45 },
  { date: '2024-01-02', iv: 31.2, hv: 25.8, ivRank: 52 },
  { date: '2024-01-03', iv: 29.8, hv: 26.1, ivRank: 48 },
  { date: '2024-01-04', iv: 33.4, hv: 27.3, ivRank: 58 },
  { date: '2024-01-05', iv: 35.1, hv: 28.9, ivRank: 62 },
  { date: '2024-01-06', iv: 32.7, hv: 27.8, ivRank: 55 },
  { date: '2024-01-07', iv: 30.9, hv: 26.4, ivRank: 51 },
  { date: '2024-01-08', iv: 34.2, hv: 29.1, ivRank: 59 },
  { date: '2024-01-09', iv: 31.8, hv: 27.6, ivRank: 53 },
  { date: '2024-01-10', iv: 29.3, hv: 25.9, ivRank: 47 },
  { date: '2024-01-11', iv: 27.6, hv: 24.8, ivRank: 42 },
  { date: '2024-01-12', iv: 26.9, hv: 23.7, ivRank: 39 },
  { date: '2024-01-13', iv: 28.1, hv: 24.5, ivRank: 44 },
  { date: '2024-01-14', iv: 27.3, hv: 24.1, ivRank: 41 }
];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-white p-3 border border-gray-200 rounded-lg shadow-lg">
        <p className="text-sm text-gray-600 mb-2">{`Date: ${label}`}</p>
        {payload.map((entry: any, index: number) => (
          <p key={index} className="text-sm font-medium" style={{ color: entry.color }}>
            {`${entry.name}: ${entry.value}${entry.dataKey === 'ivRank' ? '' : '%'}`}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export const VolatilityChart: React.FC = () => {
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Volatility Analysis</h3>
          <p className="text-sm text-gray-500">Implied vs Historical Volatility</p>
        </div>
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-primary-500 rounded-full"></div>
            <span className="text-xs text-gray-600">Implied Vol</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-success-500 rounded-full"></div>
            <span className="text-xs text-gray-600">Historical Vol</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-orange-500 rounded-full"></div>
            <span className="text-xs text-gray-600">IV Rank</span>
          </div>
        </div>
      </div>
      
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={volatilityData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
            <XAxis 
              dataKey="date" 
              stroke="#6b7280"
              fontSize={12}
              tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            />
            <YAxis 
              yAxisId="volatility"
              stroke="#6b7280"
              fontSize={12}
              tickFormatter={(value) => `${value}%`}
            />
            <YAxis 
              yAxisId="rank"
              orientation="right"
              stroke="#6b7280"
              fontSize={12}
              domain={[0, 100]}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              yAxisId="volatility"
              type="monotone"
              dataKey="iv"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ fill: '#3b82f6', strokeWidth: 2, r: 3 }}
              name="Implied Vol"
            />
            <Line
              yAxisId="volatility"
              type="monotone"
              dataKey="hv"
              stroke="#10b981"
              strokeWidth={2}
              dot={{ fill: '#10b981', strokeWidth: 2, r: 3 }}
              name="Historical Vol"
            />
            <Line
              yAxisId="rank"
              type="monotone"
              dataKey="ivRank"
              stroke="#f59e0b"
              strokeWidth={2}
              strokeDasharray="5 5"
              dot={{ fill: '#f59e0b', strokeWidth: 2, r: 3 }}
              name="IV Rank"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};