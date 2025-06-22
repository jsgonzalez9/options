import React from 'react';
import { TrendingUp, TrendingDown, Plus, Star } from 'lucide-react';

interface WatchlistItem {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  iv: number;
  volume: number;
  isFavorite: boolean;
}

const watchlistItems: WatchlistItem[] = [
  {
    symbol: 'AAPL',
    name: 'Apple Inc.',
    price: 182.45,
    change: -2.15,
    changePercent: -1.16,
    iv: 28.5,
    volume: 45230,
    isFavorite: true
  },
  {
    symbol: 'TSLA',
    name: 'Tesla Inc.',
    price: 238.80,
    change: 8.45,
    changePercent: 3.67,
    iv: 42.3,
    volume: 78920,
    isFavorite: true
  },
  {
    symbol: 'NVDA',
    name: 'NVIDIA Corp.',
    price: 742.30,
    change: 15.60,
    changePercent: 2.15,
    iv: 35.8,
    volume: 32150,
    isFavorite: false
  },
  {
    symbol: 'SPY',
    name: 'SPDR S&P 500',
    price: 485.20,
    change: 3.80,
    changePercent: 0.79,
    iv: 18.7,
    volume: 125840,
    isFavorite: true
  },
  {
    symbol: 'QQQ',
    name: 'Invesco QQQ',
    price: 392.15,
    change: -1.25,
    changePercent: -0.32,
    iv: 24.1,
    volume: 67430,
    isFavorite: false
  },
  {
    symbol: 'IWM',
    name: 'iShares Russell 2000',
    price: 198.75,
    change: 2.40,
    changePercent: 1.22,
    iv: 31.2,
    volume: 28950,
    isFavorite: false
  }
];

export const WatchlistCard: React.FC = () => {
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Watchlist</h3>
          <p className="text-sm text-gray-500">Track your favorite symbols</p>
        </div>
        <button className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
          <Plus className="w-4 h-4" />
        </button>
      </div>
      
      <div className="space-y-3">
        {watchlistItems.map((item) => (
          <div key={item.symbol} className="flex items-center justify-between p-3 hover:bg-gray-50 rounded-lg transition-colors cursor-pointer">
            <div className="flex items-center space-x-3">
              <button className={`p-1 rounded ${
                item.isFavorite ? 'text-yellow-500' : 'text-gray-300 hover:text-yellow-500'
              }`}>
                <Star className={`w-4 h-4 ${item.isFavorite ? 'fill-current' : ''}`} />
              </button>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="font-medium text-gray-900">{item.symbol}</span>
                  <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                    IV: {item.iv}%
                  </span>
                </div>
                <p className="text-xs text-gray-500">{item.name}</p>
              </div>
            </div>
            
            <div className="text-right">
              <div className="font-medium text-gray-900">${item.price.toFixed(2)}</div>
              <div className={`flex items-center justify-end space-x-1 text-xs ${
                item.change >= 0 ? 'text-success-600' : 'text-danger-600'
              }`}>
                {item.change >= 0 ? (
                  <TrendingUp className="w-3 h-3" />
                ) : (
                  <TrendingDown className="w-3 h-3" />
                )}
                <span>
                  {item.change >= 0 ? '+' : ''}{item.change.toFixed(2)} ({item.changePercent >= 0 ? '+' : ''}{item.changePercent.toFixed(2)}%)
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
      
      <div className="mt-4 pt-4 border-t border-gray-200">
        <button className="w-full text-sm text-primary-600 hover:text-primary-700 font-medium">
          View All Symbols
        </button>
      </div>
    </div>
  );
};