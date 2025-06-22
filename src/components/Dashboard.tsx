import React, { useState } from 'react';
import { Upload } from 'lucide-react';
import { MetricsGrid } from './MetricsGrid';
import { OptionsChart } from './OptionsChart';
import { PositionsTable } from './PositionsTable';
import { WatchlistCard } from './WatchlistCard';
import { VolatilityChart } from './VolatilityChart';
import { CSVImport } from './CSVImport';

interface ImportedPosition {
  id: string;
  symbol: string;
  strategy: string;
  tradeDate: string;
  expirationDate: string;
  quantity: number;
  daysLeft: number | string;
  creditAmount: number;
  isValid: boolean;
  errors: string[];
}

export const Dashboard: React.FC = () => {
  const [showCSVImport, setShowCSVImport] = useState(false);
  const [importedPositions, setImportedPositions] = useState<ImportedPosition[]>([]);

  const handleCSVImport = (positions: ImportedPosition[]) => {
    setImportedPositions(prev => [...prev, ...positions]);
    console.log('Imported positions:', positions);
    // Here you would typically save to your backend or state management system
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold text-gray-900">Dashboard</h2>
          <p className="text-gray-600 mt-1">Monitor your options trading performance</p>
          {importedPositions.length > 0 && (
            <p className="text-sm text-green-600 mt-1">
              {importedPositions.length} position{importedPositions.length !== 1 ? 's' : ''} imported from CSV
            </p>
          )}
        </div>
        <div className="flex space-x-3">
          <button 
            onClick={() => setShowCSVImport(true)}
            className="btn-secondary flex items-center space-x-2"
          >
            <Upload className="w-4 h-4" />
            <span>Import CSV</span>
          </button>
          <button className="btn-secondary">Export Data</button>
          <button className="btn-primary">New Position</button>
        </div>
      </div>

      {/* Metrics Grid */}
      <MetricsGrid />

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <OptionsChart />
        <VolatilityChart />
      </div>

      {/* Tables and Lists */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <PositionsTable importedPositions={importedPositions} />
        </div>
        <div>
          <WatchlistCard />
        </div>
      </div>

      {/* CSV Import Modal */}
      {showCSVImport && (
        <CSVImport
          onImport={handleCSVImport}
          onClose={() => setShowCSVImport(false)}
        />
      )}
    </div>
  );
};