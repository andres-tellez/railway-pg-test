import React, { useState } from 'react';
import { useApiClient } from '../utils/apiClient';
import { format, subWeeks, subMonths, startOfToday } from 'date-fns';

interface ActivityExportProps {
  className?: string;
}

type DateRangePreset = 'lastWeek' | 'last2Weeks' | 'last4Weeks' | 'lastMonth' | 'last3Months' | 'last6Months' | 'custom';

const ActivityExport: React.FC<ActivityExportProps> = ({ className = '' }) => {
  const api = useApiClient();
  const [selectedPreset, setSelectedPreset] = useState<DateRangePreset>('last4Weeks');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Calculate date ranges based on preset
  const getDateRange = (preset: DateRangePreset): { start: Date; end: Date } => {
    const today = startOfToday();
    let start: Date;

    switch (preset) {
      case 'lastWeek':
        start = subWeeks(today, 1);
        break;
      case 'last2Weeks':
        start = subWeeks(today, 2);
        break;
      case 'last4Weeks':
        start = subWeeks(today, 4);
        break;
      case 'lastMonth':
        start = subMonths(today, 1);
        break;
      case 'last3Months':
        start = subMonths(today, 3);
        break;
      case 'last6Months':
        start = subMonths(today, 6);
        break;
      case 'custom':
        // For custom, use the input dates
        return {
          start: startDate ? new Date(startDate) : subWeeks(today, 4),
          end: endDate ? new Date(endDate) : today,
        };
      default:
        start = subWeeks(today, 4);
    }

    return { start, end: today };
  };

  // Update date inputs when preset changes
  React.useEffect(() => {
    if (selectedPreset !== 'custom') {
      const range = getDateRange(selectedPreset);
      setStartDate(format(range.start, 'yyyy-MM-dd'));
      setEndDate(format(range.end, 'yyyy-MM-dd'));
    }
  }, [selectedPreset]);

  // Initialize with default dates
  React.useEffect(() => {
    const range = getDateRange(selectedPreset);
    setStartDate(format(range.start, 'yyyy-MM-dd'));
    setEndDate(format(range.end, 'yyyy-MM-dd'));
  }, []);

  const handlePresetChange = (preset: DateRangePreset) => {
    setSelectedPreset(preset);
    setError(null);
    setSuccess(false);
  };

  const handleCustomDateChange = (type: 'start' | 'end', value: string) => {
    if (type === 'start') {
      setStartDate(value);
    } else {
      setEndDate(value);
    }
    setError(null);
    setSuccess(false);
    setSelectedPreset('custom');
  };

  const handleExport = async () => {
    if (!startDate || !endDate) {
      setError('Please select both start and end dates');
      return;
    }

    // Validate dates
    const start = new Date(startDate);
    const end = new Date(endDate);

    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      setError('Invalid date format');
      return;
    }

    if (start > end) {
      setError('Start date must be before or equal to end date');
      return;
    }

    setIsExporting(true);
    setError(null);
    setSuccess(false);

    try {
      // Use api client with blob response type for file download
      const response = await api.get('/api/activities/export', {
        params: {
          start_date: startDate,
          end_date: endDate,
        },
        responseType: 'blob',
      });

      // Create blob from response
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      });

      // Create download link
      const url = window.URL.createObjectURL(blob);
      const downloadLink = document.createElement('a');
      downloadLink.href = url;
      downloadLink.download = `activities_${startDate}_to_${endDate}.xlsx`;
      document.body.appendChild(downloadLink);
      downloadLink.click();
      document.body.removeChild(downloadLink);
      window.URL.revokeObjectURL(url);

      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      console.error('Export error:', err);

      // Try to parse error message from blob response if available
      if (err.response?.data instanceof Blob) {
        try {
          const text = await err.response.data.text();
          const errorData = JSON.parse(text);
          setError(errorData.error || 'Failed to export activities. Please try again.');
        } catch {
          setError('Failed to export activities. Please try again.');
        }
      } else {
        setError(err.response?.data?.error || err.message || 'Failed to export activities. Please try again.');
      }
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className={`space-y-4 ${className}`}>
      <h3 className="text-lg font-medium text-gray-900 mb-4">
        Export Activities
      </h3>
      <p className="text-sm text-gray-600 mb-4">
        Export your activities to Excel for analysis. Select a date range or use a preset.
      </p>

      {/* Preset buttons */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Quick Select
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {[
            { value: 'lastWeek', label: 'Last Week' },
            { value: 'last2Weeks', label: 'Last 2 Weeks' },
            { value: 'last4Weeks', label: 'Last 4 Weeks' },
            { value: 'lastMonth', label: 'Last Month' },
            { value: 'last3Months', label: 'Last 3 Months' },
            { value: 'last6Months', label: 'Last 6 Months' },
          ].map((preset) => (
            <button
              key={preset.value}
              type="button"
              onClick={() => handlePresetChange(preset.value as DateRangePreset)}
              className={`px-3 py-2 text-sm font-medium rounded-md border transition-colors ${
                selectedPreset === preset.value
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
              }`}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      {/* Custom date range */}
      <div className="space-y-2">
        <label className="block text-sm font-medium text-gray-700">
          Date Range
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="start-date" className="block text-xs text-gray-500 mb-1">
              Start Date
            </label>
            <input
              type="date"
              id="start-date"
              value={startDate}
              onChange={(e) => handleCustomDateChange('start', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div>
            <label htmlFor="end-date" className="block text-xs text-gray-500 mb-1">
              End Date
            </label>
            <input
              type="date"
              id="end-date"
              value={endDate}
              onChange={(e) => handleCustomDateChange('end', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="rounded-md bg-red-50 p-3">
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {/* Success message */}
      {success && (
        <div className="rounded-md bg-green-50 p-3">
          <p className="text-sm text-green-800">Export started! Your file should download shortly.</p>
        </div>
      )}

      {/* Export button */}
      <button
        type="button"
        onClick={handleExport}
        disabled={isExporting || !startDate || !endDate}
        className={`w-full sm:w-auto px-6 py-2 rounded-md font-medium text-white transition-colors ${
          isExporting || !startDate || !endDate
            ? 'bg-gray-400 cursor-not-allowed'
            : 'bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500'
        }`}
      >
        {isExporting ? 'Exporting...' : 'Export to Excel'}
      </button>
    </div>
  );
};

export default ActivityExport;
