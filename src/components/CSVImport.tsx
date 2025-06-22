import React, { useState, useRef } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle, X } from 'lucide-react';

interface CSVRow {
  Symbol: string;
  strategy: string;
  trade_date: string;
  expiration_date: string;
  quantity: number;
  Days_left: number | string;
  credit_amount: number;
}

interface ParsedPosition {
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

interface CSVImportProps {
  onImport: (positions: ParsedPosition[]) => void;
  onClose: () => void;
}

export const CSVImport: React.FC<CSVImportProps> = ({ onImport, onClose }) => {
  const [dragActive, setDragActive] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [parsedData, setParsedData] = useState<ParsedPosition[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [step, setStep] = useState<'upload' | 'preview' | 'complete'>('upload');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const expectedHeaders = ['Symbol', 'strategy', 'trade_date', 'expiration_date', 'quantity', 'Days left', 'credit_amount'];

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    const files = e.dataTransfer.files;
    if (files && files[0]) {
      handleFile(files[0]);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files[0]) {
      handleFile(files[0]);
    }
  };

  const handleFile = (selectedFile: File) => {
    if (selectedFile.type !== 'text/csv' && !selectedFile.name.endsWith('.csv')) {
      alert('Please select a CSV file');
      return;
    }
    setFile(selectedFile);
    parseCSV(selectedFile);
  };

  const parseCSV = async (csvFile: File) => {
    setIsProcessing(true);
    
    try {
      const text = await csvFile.text();
      const lines = text.split('\n').filter(line => line.trim());
      
      if (lines.length < 2) {
        throw new Error('CSV file must contain at least a header row and one data row');
      }

      const headers = lines[0].split(',').map(h => h.trim());
      
      // Validate headers
      const missingHeaders = expectedHeaders.filter(expected => 
        !headers.some(header => header.toLowerCase().replace(/\s+/g, '_') === expected.toLowerCase().replace(/\s+/g, '_'))
      );
      
      if (missingHeaders.length > 0) {
        throw new Error(`Missing required headers: ${missingHeaders.join(', ')}`);
      }

      const dataRows = lines.slice(1);
      const parsed: ParsedPosition[] = dataRows.map((line, index) => {
        // Handle CSV parsing with proper quote handling
        const values: string[] = [];
        let current = '';
        let inQuotes = false;
        
        for (let i = 0; i < line.length; i++) {
          const char = line[i];
          if (char === '"') {
            inQuotes = !inQuotes;
          } else if (char === ',' && !inQuotes) {
            values.push(current.trim());
            current = '';
          } else {
            current += char;
          }
        }
        values.push(current.trim()); // Add the last value
        
        const errors: string[] = [];
        
        const row: Partial<CSVRow> = {};
        headers.forEach((header, i) => {
          const value = values[i] || '';
          const normalizedHeader = header.toLowerCase().replace(/\s+/g, '_');
          
          if (normalizedHeader === 'symbol') {
            row.Symbol = value;
          } else if (normalizedHeader === 'strategy') {
            row.strategy = value;
          } else if (normalizedHeader === 'trade_date') {
            row.trade_date = value;
          } else if (normalizedHeader === 'expiration_date') {
            row.expiration_date = value;
          } else if (normalizedHeader === 'quantity') {
            const qty = parseFloat(value);
            row.quantity = isNaN(qty) ? 0 : qty;
          } else if (normalizedHeader === 'days_left' || normalizedHeader === 'days left') {
            // Handle various formats for days left
            if (value && value.toLowerCase() === 'expired') {
              row.Days_left = 'Expired';
            } else if (value && value.trim() !== '') {
              const parsed = parseFloat(value);
              row.Days_left = isNaN(parsed) ? 0 : parsed;
            } else {
              row.Days_left = 0;
            }
          } else if (normalizedHeader === 'credit_amount') {
            // Clean up currency formatting
            const cleanValue = value.replace(/[$,]/g, '');
            const amount = parseFloat(cleanValue);
            row.credit_amount = isNaN(amount) ? 0 : amount;
          }
        });

        // Enhanced validation with better error messages
         const isStock = row.strategy && row.strategy.toLowerCase().trim() === 'stock';
         
         if (!row.Symbol || row.Symbol.trim() === '') {
           errors.push('Symbol is required');
         }
         if (!row.strategy || row.strategy.trim() === '') {
           errors.push('Strategy is required');
         }
         if (!row.trade_date || row.trade_date.trim() === '') {
           errors.push('Trade date is required');
         }
         
         // For stocks, expiration date is not required
         if (!isStock && (!row.expiration_date || row.expiration_date.trim() === '')) {
           errors.push('Expiration date is required for options strategies');
         }
         
         if (!row.quantity || row.quantity <= 0) {
           errors.push('Quantity must be greater than 0');
         }
         
         // For stocks, days left doesn't apply (they don't expire)
         if (!isStock && row.Days_left === undefined) {
           errors.push('Days left is required for options strategies');
         }
         
         // For stocks, credit amount might be 0 (no premium collected, just holding)
         if (!isStock && (row.credit_amount === undefined || row.credit_amount === 0)) {
           errors.push('Credit amount is required for options strategies');
         }

        // Process and clean the data
         const cleanedData = {
           Symbol: row.Symbol?.trim() || '',
           strategy: row.strategy?.trim() || '',
           trade_date: row.trade_date?.trim() || '',
           expiration_date: isStock ? 'N/A' : (row.expiration_date?.trim() || ''),
           quantity: parseInt(row.quantity?.toString() || '0') || 0,
           Days_left: isStock ? 'N/A' : row.Days_left,
           credit_amount: row.credit_amount || 0
         };

        return {
          id: `import-${index}`,
          symbol: row.Symbol || '',
          strategy: row.strategy || '',
          tradeDate: row.trade_date || '',
          expirationDate: row.expiration_date || '',
          quantity: row.quantity || 0,
          daysLeft: row.Days_left || 0,
          creditAmount: row.credit_amount || 0,
          isValid: errors.length === 0,
          errors
        };
      });

      setParsedData(parsed);
      setStep('preview');
    } catch (error) {
      alert(`Error parsing CSV: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleImport = () => {
    const validPositions = parsedData.filter(p => p.isValid);
    onImport(validPositions);
    setStep('complete');
  };

  const validCount = parsedData.filter(p => p.isValid).length;
  const invalidCount = parsedData.length - validCount;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-2xl max-w-4xl w-full mx-4 max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Import Positions from CSV</h2>
            <p className="text-sm text-gray-500 mt-1">
              {step === 'upload' && 'Upload a CSV file with your options positions'}
              {step === 'preview' && 'Review and validate imported data'}
              {step === 'complete' && 'Import completed successfully'}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6">
          {step === 'upload' && (
            <div className="space-y-6">
              {/* Expected Format */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <h3 className="text-sm font-medium text-blue-900 mb-2">Expected CSV Format</h3>
                <div className="text-xs text-blue-700 font-mono bg-white p-2 rounded border">
                  {expectedHeaders.join(', ')}
                </div>
              </div>

              {/* Upload Area */}
              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                  dragActive
                    ? 'border-primary-400 bg-primary-50'
                    : 'border-gray-300 hover:border-gray-400'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
              >
                <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <p className="text-lg font-medium text-gray-900 mb-2">
                  {dragActive ? 'Drop your CSV file here' : 'Drag and drop your CSV file'}
                </p>
                <p className="text-sm text-gray-500 mb-4">or</p>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="btn-primary"
                  disabled={isProcessing}
                >
                  {isProcessing ? 'Processing...' : 'Choose File'}
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  onChange={handleFileInput}
                  className="hidden"
                />
              </div>

              {file && (
                <div className="flex items-center space-x-3 p-3 bg-gray-50 rounded-lg">
                  <FileText className="w-5 h-5 text-gray-500" />
                  <span className="text-sm text-gray-700">{file.name}</span>
                  <span className="text-xs text-gray-500">({(file.size / 1024).toFixed(1)} KB)</span>
                </div>
              )}
            </div>
          )}

          {step === 'preview' && (
            <div className="space-y-6">
              {/* Summary */}
              <div className="grid grid-cols-3 gap-4">
                <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                  <div className="flex items-center space-x-2">
                    <CheckCircle className="w-5 h-5 text-green-600" />
                    <span className="text-sm font-medium text-green-900">Valid Rows</span>
                  </div>
                  <p className="text-2xl font-bold text-green-900 mt-1">{validCount}</p>
                </div>
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <div className="flex items-center space-x-2">
                    <AlertCircle className="w-5 h-5 text-red-600" />
                    <span className="text-sm font-medium text-red-900">Invalid Rows</span>
                  </div>
                  <p className="text-2xl font-bold text-red-900 mt-1">{invalidCount}</p>
                </div>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-center space-x-2">
                    <FileText className="w-5 h-5 text-blue-600" />
                    <span className="text-sm font-medium text-blue-900">Total Rows</span>
                  </div>
                  <p className="text-2xl font-bold text-blue-900 mt-1">{parsedData.length}</p>
                </div>
              </div>

              {/* Data Preview */}
              <div className="border border-gray-200 rounded-lg overflow-hidden">
                <div className="max-h-96 overflow-y-auto">
                  <table className="w-full">
                    <thead className="bg-gray-50 sticky top-0">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Strategy</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Quantity</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Days Left</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Credit</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Errors</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {parsedData.map((position, index) => (
                        <tr key={index} className={position.isValid ? 'bg-white' : 'bg-red-50'}>
                          <td className="px-4 py-3">
                            {position.isValid ? (
                              <CheckCircle className="w-4 h-4 text-green-500" />
                            ) : (
                              <AlertCircle className="w-4 h-4 text-red-500" />
                            )}
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-900">{position.symbol}</td>
                          <td className="px-4 py-3 text-sm text-gray-900">{position.strategy}</td>
                          <td className="px-4 py-3 text-sm text-gray-900">{position.quantity}</td>
                          <td className="px-4 py-3 text-sm text-gray-900">{position.daysLeft}</td>
                          <td className="px-4 py-3 text-sm text-gray-900">${position.creditAmount.toFixed(2)}</td>
                          <td className="px-4 py-3 text-sm text-red-600">
                            {position.errors.length > 0 && (
                              <div className="text-xs">
                                {position.errors.join(', ')}
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Actions */}
              <div className="flex justify-between">
                <button
                  onClick={() => setStep('upload')}
                  className="btn-secondary"
                >
                  Back
                </button>
                <button
                  onClick={handleImport}
                  disabled={validCount === 0}
                  className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Import {validCount} Valid Position{validCount !== 1 ? 's' : ''}
                </button>
              </div>
            </div>
          )}

          {step === 'complete' && (
            <div className="text-center py-8">
              <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Import Successful!</h3>
              <p className="text-gray-600 mb-6">
                Successfully imported {validCount} position{validCount !== 1 ? 's' : ''} to your dashboard.
              </p>
              <button onClick={onClose} className="btn-primary">
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};