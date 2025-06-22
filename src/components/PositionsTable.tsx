import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, MoreHorizontal, Upload, Edit, Trash2, Settings, X, Save } from 'lucide-react';

interface Position {
  id: string;
  symbol: string;
  strategy: string;
  type: 'call' | 'put';
  strike: number;
  expiry: string;
  quantity: number;
  premium: number;
  currentValue: number;
  pnl: number;
  pnlPercent: number;
  delta: number;
  theta: number;
  iv: number;
}

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

interface PositionsTableProps {
  importedPositions?: ImportedPosition[];
}

const positions: Position[] = [
  {
    id: '1',
    symbol: 'AAPL',
    strategy: 'Iron Condor',
    type: 'call',
    strike: 185,
    expiry: '2024-02-16',
    quantity: 10,
    premium: 2.45,
    currentValue: 1.85,
    pnl: -600,
    pnlPercent: -24.5,
    delta: -0.32,
    theta: -0.08,
    iv: 28.5
  },
  {
    id: '2',
    symbol: 'TSLA',
    strategy: 'Cash Secured Put',
    type: 'put',
    strike: 220,
    expiry: '2024-02-09',
    quantity: 5,
    premium: 8.20,
    currentValue: 5.40,
    pnl: -1400,
    pnlPercent: -34.1,
    delta: 0.45,
    theta: -0.15,
    iv: 42.3
  },
  {
    id: '3',
    symbol: 'SPY',
    strategy: 'Bull Call Spread',
    type: 'call',
    strike: 480,
    expiry: '2024-03-15',
    quantity: 20,
    premium: 3.80,
    currentValue: 4.95,
    pnl: 2300,
    pnlPercent: 30.3,
    delta: 0.68,
    theta: -0.05,
    iv: 18.7
  },
  {
    id: '4',
    symbol: 'NVDA',
    strategy: 'Covered Call',
    type: 'call',
    strike: 750,
    expiry: '2024-02-23',
    quantity: 2,
    premium: 15.60,
    currentValue: 12.30,
    pnl: 660,
    pnlPercent: 21.2,
    delta: -0.55,
    theta: -0.22,
    iv: 35.8
  },
  {
    id: '5',
    symbol: 'QQQ',
    strategy: 'Straddle',
    type: 'call',
    strike: 390,
    expiry: '2024-02-16',
    quantity: 8,
    premium: 12.40,
    currentValue: 14.80,
    pnl: 1920,
    pnlPercent: 19.4,
    delta: 0.12,
    theta: -0.18,
    iv: 24.1
  }
];

export const PositionsTable: React.FC<PositionsTableProps> = ({ importedPositions = [] }) => {
  const hasImportedPositions = importedPositions.length > 0;
  const [openDropdown, setOpenDropdown] = useState<string | null>(null);
  const [showManageModal, setShowManageModal] = useState(false);
  const [editingPosition, setEditingPosition] = useState<Position | ImportedPosition | null>(null);
  const [editForm, setEditForm] = useState<any>({});
  const [allPositions, setAllPositions] = useState<Position[]>(positions);

  const handleEdit = (positionId: string) => {
    console.log('Edit position:', positionId);
    setOpenDropdown(null);
    
    // Find position in either imported or regular positions
    const importedPos = importedPositions.find(p => p.id === positionId);
    const regularPos = allPositions.find(p => p.id === positionId);
    
    const position = importedPos || regularPos;
    if (position) {
      setEditingPosition(position);
      setEditForm({ ...position });
    }
  };

  const handleDelete = (positionId: string) => {
    console.log('Delete position:', positionId);
    setOpenDropdown(null);
    
    if (window.confirm('Are you sure you want to delete this position?')) {
      // Remove from regular positions (imported positions are read-only for deletion)
      setAllPositions(prev => prev.filter(p => p.id !== positionId));
      alert('Position deleted successfully!');
    }
  };
  
  const handleSaveEdit = () => {
    if (!editingPosition) return;
    
    // Update regular positions
    if ('strike' in editForm) {
      setAllPositions(prev => 
        prev.map(p => p.id === editingPosition.id ? { ...editForm } : p)
      );
      alert('Position updated successfully!');
    } else {
      // For imported positions, just show success (they're typically read-only)
      alert('Imported position details noted (read-only)');
    }
    
    setEditingPosition(null);
    setEditForm({});
  };
  
  const handleCancelEdit = () => {
    setEditingPosition(null);
    setEditForm({});
  };
  
  const handleFormChange = (field: string, value: any) => {
    setEditForm((prev: any) => ({ ...prev, [field]: value }));
  };

  const handleManageAll = () => {
    console.log('Manage all positions');
    setShowManageModal(true);
  };

  const toggleDropdown = (positionId: string) => {
    setOpenDropdown(openDropdown === positionId ? null : positionId);
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setOpenDropdown(null);
    };
    
    if (openDropdown) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [openDropdown]);
  
  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Active Positions</h3>
          <p className="text-sm text-gray-500">
            Current options positions and performance
            {hasImportedPositions && (
              <span className="ml-2 text-green-600">• {importedPositions.length} imported</span>
            )}
          </p>
        </div>
        <button 
          onClick={handleManageAll}
          className="btn-secondary text-sm flex items-center space-x-2"
        >
          <Settings className="w-4 h-4" />
          <span>Manage All</span>
        </button>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="text-left py-3 px-2 text-xs font-medium text-gray-500 uppercase tracking-wider">Symbol</th>
              <th className="text-left py-3 px-2 text-xs font-medium text-gray-500 uppercase tracking-wider">Strategy</th>
              <th className="text-left py-3 px-2 text-xs font-medium text-gray-500 uppercase tracking-wider">Strike/Expiry</th>
              <th className="text-right py-3 px-2 text-xs font-medium text-gray-500 uppercase tracking-wider">Qty</th>
              <th className="text-right py-3 px-2 text-xs font-medium text-gray-500 uppercase tracking-wider">P&L</th>
              <th className="text-right py-3 px-2 text-xs font-medium text-gray-500 uppercase tracking-wider">Delta</th>
              <th className="text-right py-3 px-2 text-xs font-medium text-gray-500 uppercase tracking-wider">Theta</th>
              <th className="text-right py-3 px-2 text-xs font-medium text-gray-500 uppercase tracking-wider">IV</th>
              <th className="text-right py-3 px-2 text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {/* Imported Positions */}
            {importedPositions.map((position) => (
              <tr key={position.id} className="hover:bg-blue-50 bg-blue-25">
                <td className="py-4 px-2">
                  <div className="flex items-center space-x-2">
                    <span className="font-medium text-gray-900">{position.symbol}</span>
                    <span className="px-2 py-1 text-xs rounded-full bg-blue-100 text-blue-700 flex items-center space-x-1">
                      <Upload className="w-3 h-3" />
                      <span>IMPORTED</span>
                    </span>
                  </div>
                </td>
                <td className="py-4 px-2 text-sm text-gray-600">{position.strategy}</td>
                <td className="py-4 px-2">
                  <div className="text-sm">
                    <div className="font-medium text-gray-900">{position.expirationDate}</div>
                    <div className="text-gray-500">{position.daysLeft} days left</div>
                  </div>
                </td>
                <td className="py-4 px-2 text-right text-sm text-gray-900">{position.quantity}</td>
                <td className="py-4 px-2 text-right">
                  <div className="flex items-center justify-end space-x-1">
                    <TrendingUp className="w-4 h-4 text-blue-500" />
                    <div className="text-sm">
                      <div className="font-medium text-blue-600">
                        ${position.creditAmount.toFixed(2)}
                      </div>
                      <div className="text-xs text-blue-500">
                        Credit
                      </div>
                    </div>
                  </div>
                </td>
                <td className="py-4 px-2 text-right text-sm text-gray-400">-</td>
                <td className="py-4 px-2 text-right text-sm text-gray-400">-</td>
                <td className="py-4 px-2 text-right text-sm text-gray-400">-</td>
                <td className="py-4 px-2 text-right relative">
                  <button 
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleDropdown(position.id);
                    }}
                    className="p-1 text-gray-400 hover:text-gray-600"
                  >
                    <MoreHorizontal className="w-4 h-4" />
                  </button>
                  {openDropdown === position.id && (
                    <div 
                      className="absolute right-0 top-12 bg-white border border-gray-200 rounded-lg shadow-lg z-10 min-w-[120px]"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEdit(position.id);
                        }}
                        className="w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center space-x-2"
                      >
                        <Edit className="w-4 h-4" />
                        <span>Edit</span>
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(position.id);
                        }}
                        className="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center space-x-2"
                      >
                        <Trash2 className="w-4 h-4" />
                        <span>Delete</span>
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
            
            {/* Existing Mock Positions */}
            {allPositions.map((position) => (
              <tr key={position.id} className="hover:bg-gray-50">
                <td className="py-4 px-2">
                  <div className="flex items-center space-x-2">
                    <span className="font-medium text-gray-900">{position.symbol}</span>
                    <span className={`px-2 py-1 text-xs rounded-full ${
                      position.type === 'call' 
                        ? 'bg-success-100 text-success-700' 
                        : 'bg-danger-100 text-danger-700'
                    }`}>
                      {position.type.toUpperCase()}
                    </span>
                  </div>
                </td>
                <td className="py-4 px-2 text-sm text-gray-600">{position.strategy}</td>
                <td className="py-4 px-2">
                  <div className="text-sm">
                    <div className="font-medium text-gray-900">${position.strike}</div>
                    <div className="text-gray-500">{position.expiry}</div>
                  </div>
                </td>
                <td className="py-4 px-2 text-right text-sm text-gray-900">{position.quantity}</td>
                <td className="py-4 px-2 text-right">
                  <div className="flex items-center justify-end space-x-1">
                    {position.pnl >= 0 ? (
                      <TrendingUp className="w-4 h-4 text-success-500" />
                    ) : (
                      <TrendingDown className="w-4 h-4 text-danger-500" />
                    )}
                    <div className="text-sm">
                      <div className={`font-medium ${
                        position.pnl >= 0 ? 'text-success-600' : 'text-danger-600'
                      }`}>
                        ${Math.abs(position.pnl).toLocaleString()}
                      </div>
                      <div className={`text-xs ${
                        position.pnl >= 0 ? 'text-success-500' : 'text-danger-500'
                      }`}>
                        {position.pnlPercent > 0 ? '+' : ''}{position.pnlPercent}%
                      </div>
                    </div>
                  </div>
                </td>
                <td className="py-4 px-2 text-right text-sm text-gray-900">
                  {position.delta > 0 ? '+' : ''}{position.delta.toFixed(2)}
                </td>
                <td className="py-4 px-2 text-right text-sm text-gray-900">
                  {position.theta.toFixed(2)}
                </td>
                <td className="py-4 px-2 text-right text-sm text-gray-900">{position.iv}%</td>
                <td className="py-4 px-2 text-right relative">
                  <button 
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleDropdown(position.id);
                    }}
                    className="p-1 text-gray-400 hover:text-gray-600"
                  >
                    <MoreHorizontal className="w-4 h-4" />
                  </button>
                  {openDropdown === position.id && (
                    <div 
                      className="absolute right-0 top-12 bg-white border border-gray-200 rounded-lg shadow-lg z-10 min-w-[120px]"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEdit(position.id);
                        }}
                        className="w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center space-x-2"
                      >
                        <Edit className="w-4 h-4" />
                        <span>Edit</span>
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDelete(position.id);
                        }}
                        className="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center space-x-2"
                      >
                        <Trash2 className="w-4 h-4" />
                        <span>Delete</span>
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {/* Edit Position Modal */}
      {editingPosition && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-gray-900">
                Edit Position: {editForm.symbol}
              </h3>
              <button 
                onClick={handleCancelEdit}
                className="p-2 text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Symbol</label>
                <input
                  type="text"
                  value={editForm.symbol || ''}
                  onChange={(e) => handleFormChange('symbol', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Strategy</label>
                <input
                  type="text"
                  value={editForm.strategy || ''}
                  onChange={(e) => handleFormChange('strategy', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              {/* Regular Position Fields */}
              {'strike' in editForm && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
                    <select
                      value={editForm.type || 'call'}
                      onChange={(e) => handleFormChange('type', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="call">Call</option>
                      <option value="put">Put</option>
                    </select>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Strike Price</label>
                    <input
                      type="number"
                      value={editForm.strike || ''}
                      onChange={(e) => handleFormChange('strike', parseFloat(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Expiry Date</label>
                    <input
                      type="date"
                      value={editForm.expiry || ''}
                      onChange={(e) => handleFormChange('expiry', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Premium</label>
                    <input
                      type="number"
                      step="0.01"
                      value={editForm.premium || ''}
                      onChange={(e) => handleFormChange('premium', parseFloat(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Current Value</label>
                    <input
                      type="number"
                      step="0.01"
                      value={editForm.currentValue || ''}
                      onChange={(e) => handleFormChange('currentValue', parseFloat(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Delta</label>
                    <input
                      type="number"
                      step="0.01"
                      value={editForm.delta || ''}
                      onChange={(e) => handleFormChange('delta', parseFloat(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Theta</label>
                    <input
                      type="number"
                      step="0.01"
                      value={editForm.theta || ''}
                      onChange={(e) => handleFormChange('theta', parseFloat(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">IV (%)</label>
                    <input
                      type="number"
                      step="0.1"
                      value={editForm.iv || ''}
                      onChange={(e) => handleFormChange('iv', parseFloat(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </>
              )}
              
              {/* Imported Position Fields */}
              {'expirationDate' in editForm && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Trade Date</label>
                    <input
                      type="date"
                      value={editForm.tradeDate || ''}
                      onChange={(e) => handleFormChange('tradeDate', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      disabled
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Expiration Date</label>
                    <input
                      type="date"
                      value={editForm.expirationDate || ''}
                      onChange={(e) => handleFormChange('expirationDate', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      disabled
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Credit Amount</label>
                    <input
                      type="number"
                      step="0.01"
                      value={editForm.creditAmount || ''}
                      onChange={(e) => handleFormChange('creditAmount', parseFloat(e.target.value))}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      disabled
                    />
                  </div>
                </>
              )}
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Quantity</label>
                <input
                  type="number"
                  value={editForm.quantity || ''}
                  onChange={(e) => handleFormChange('quantity', parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            
            <div className="flex justify-end space-x-3 mt-6">
              <button 
                onClick={handleCancelEdit}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button 
                onClick={handleSaveEdit}
                className="btn-primary flex items-center space-x-2"
              >
                <Save className="w-4 h-4" />
                <span>Save Changes</span>
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Manage All Modal */}
      {showManageModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Manage All Positions</h3>
            <p className="text-gray-600 mb-6">
              Bulk actions for all positions. Choose an action to apply to all positions.
            </p>
            <div className="space-y-3">
              <button className="w-full btn-secondary text-left flex items-center space-x-2">
                <Edit className="w-4 h-4" />
                <span>Edit All Positions</span>
              </button>
              <button 
                onClick={() => {
                  if (window.confirm('Are you sure you want to delete all positions?')) {
                    setAllPositions([]);
                    setShowManageModal(false);
                    alert('All positions deleted successfully!');
                  }
                }}
                className="w-full btn-danger text-left flex items-center space-x-2"
              >
                <Trash2 className="w-4 h-4" />
                <span>Delete All Positions</span>
              </button>
              <button 
                onClick={() => {
                  const csvContent = allPositions.map(p => 
                    `${p.symbol},${p.strategy},${p.type},${p.strike},${p.expiry},${p.quantity},${p.premium},${p.currentValue}`
                  ).join('\n');
                  const blob = new Blob([`Symbol,Strategy,Type,Strike,Expiry,Quantity,Premium,Current Value\n${csvContent}`], { type: 'text/csv' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = 'positions.csv';
                  a.click();
                  URL.revokeObjectURL(url);
                  setShowManageModal(false);
                  alert('Positions exported successfully!');
                }}
                className="w-full btn-secondary text-left flex items-center space-x-2"
              >
                <Settings className="w-4 h-4" />
                <span>Export Positions</span>
              </button>
            </div>
            <div className="flex justify-end space-x-3 mt-6">
              <button 
                onClick={() => setShowManageModal(false)}
                className="btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};