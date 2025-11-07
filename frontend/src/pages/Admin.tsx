import React, { useState, useEffect } from 'react';
import { useApiClient } from '../utils/apiClient';
import { useAuthSetup } from '../hooks/useAuthSetup';
import { AuthGuard } from '../components/AuthGuard';

interface Athlete {
  athlete_id: number;
  user_id: string;
  display_name: string;
}

interface SyncResult {
  status: string;
  result?: any;
  message?: string;
  athlete_id?: number;
  date_range?: string;
}

const Admin: React.FC = () => {
  const { isReady, userId } = useAuthSetup(); // ✅ Centralized auth
  const apiClient = useApiClient();
  const [athletes, setAthletes] = useState<Athlete[]>([]);
  const [selectedAthlete, setSelectedAthlete] = useState<number | ''>('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SyncResult | null>(null);
  const [refreshingMetrics, setRefreshingMetrics] = useState(false);

  // Set default date range (last 7 days)
  useEffect(() => {
    const today = new Date();
    const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

    setEndDate(today.toISOString().split('T')[0]);
    setStartDate(weekAgo.toISOString().split('T')[0]);
  }, []);

  // Load athletes on component mount
  useEffect(() => {
    if (!isReady || !userId) return; // ✅ Wait for auth setup

    const loadAthletes = async () => {
      try {
        const response = await apiClient.get('/admin/athletes');
        setAthletes(response.data.athletes || []);
      } catch (error) {
        console.error('Failed to load athletes:', error);
        setResult({
          status: 'error',
          message: 'Failed to load athletes list'
        });
      }
    };

    loadAthletes();
  }, [isReady, userId, apiClient]); // ✅ Depend on auth setup

  const handleSync = async () => {
    if (!selectedAthlete || !startDate || !endDate) {
      setResult({
        status: 'error',
        message: 'Please select an athlete and date range'
      });
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const response = await apiClient.post('/admin/sync-activities', {
        athlete_id: selectedAthlete,
        start_date: startDate,
        end_date: endDate
      });

      setResult(response.data);
    } catch (error: any) {
      console.error('Sync failed:', error);
      setResult({
        status: 'error',
        message: error.response?.data?.message || 'Sync failed'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshMetrics = async () => {
    console.log('🔴 [BROWSER] Refresh Metrics button clicked!');
    setRefreshingMetrics(true);
    setResult(null);

    try {
      console.log('🔴 [BROWSER] Making POST request to /admin/refresh-metrics');
      const response = await apiClient.post('/admin/refresh-metrics');
      console.log('🔴 [BROWSER] Response received:', response.data);
      setResult(response.data);
    } catch (error: any) {
      console.error('Refresh metrics failed:', error);
      setResult({
        status: 'error',
        message: error.response?.data?.message || 'Metrics refresh failed'
      });
    } finally {
      setRefreshingMetrics(false);
    }
  };

  return (
    <AuthGuard>
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4">
        <div className="bg-white rounded-lg shadow p-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-6">Admin Tools</h1>

          {/* Refresh Metrics Section */}
          <div className="mb-8 p-4 bg-blue-50 rounded-lg border border-blue-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Metrics Refresh</h2>
            <p className="text-sm text-gray-600 mb-3">
              Manually trigger the metrics refresh to update bar graphs with the latest week's data.
            </p>
            <button
              onClick={handleRefreshMetrics}
              disabled={refreshingMetrics}
              className="bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {refreshingMetrics ? 'Refreshing Metrics...' : '🔄 Refresh Metrics'}
            </button>
          </div>

          <h2 className="text-xl font-semibold text-gray-900 mb-4">Activity Sync Admin</h2>

          <div className="space-y-4">
            {/* Athlete Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Athlete
              </label>
              <select
                value={selectedAthlete}
                onChange={(e) => setSelectedAthlete(e.target.value ? Number(e.target.value) : '')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Choose an athlete...</option>
                {athletes.map((athlete) => (
                  <option key={athlete.athlete_id} value={athlete.athlete_id}>
                    {athlete.display_name} (ID: {athlete.athlete_id})
                  </option>
                ))}
              </select>
            </div>

            {/* Date Range */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Start Date
                </label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  End Date
                </label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Sync Button */}
            <button
              onClick={handleSync}
              disabled={loading || !selectedAthlete || !startDate || !endDate}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {loading ? 'Syncing...' : 'Download & Enrich Activities'}
            </button>

            {/* Results */}
            {result && (
              <div className={`p-4 rounded-md ${
                result.status === 'success'
                  ? 'bg-green-50 border border-green-200'
                  : 'bg-red-50 border border-red-200'
              }`}>
                <h3 className={`font-medium ${
                  result.status === 'success' ? 'text-green-800' : 'text-red-800'
                }`}>
                  {result.status === 'success' ? 'Sync Successful' : 'Sync Failed'}
                </h3>
                {result.message && (
                  <p className={`mt-1 text-sm ${
                    result.status === 'success' ? 'text-green-700' : 'text-red-700'
                  }`}>
                    {result.message}
                  </p>
                )}
                {result.result && (
                  <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto">
                    {JSON.stringify(result.result, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
    </AuthGuard>
  );
};

export default Admin;
