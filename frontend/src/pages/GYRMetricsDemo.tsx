import React, { useEffect, useState } from 'react';
import { useApiClient } from '../utils/apiClient';
import { useAuthSetup } from '../hooks/useAuthSetup';
import { AuthGuard } from '../components/AuthGuard';
import GYRMetricCard from '../components/cards/GYRMetricCard';

interface GYRScore {
  value: number;
  date: string;
  status: 'green' | 'yellow' | 'red' | 'gray';
}

interface GYRMetricData {
  historicalScores: GYRScore[];
  criteria: {
    green: string;
    yellow: string;
    red: string;
  };
}

interface GYRScoresResponse {
  totalRuns: GYRMetricData;
  weeklyPace: GYRMetricData;
  weeklyHRZones: GYRMetricData;
}

export default function GYRMetricsDemo() {
  const { isReady, userId } = useAuthSetup(); // ✅ Centralized auth
  const apiClient = useApiClient();
  const [gyrData, setGyrData] = useState<GYRScoresResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isReady || !userId) return; // ✅ Wait for auth setup

    const fetchGYRScores = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await apiClient.get('/api/gyr-metrics/scores', {
          params: { weeks: 8 }
        });

        console.log('🎯 GYR Scores loaded:', response.data);
        setGyrData(response.data);
      } catch (err) {
        console.error('❌ Error fetching GYR scores:', err);
        setError(err instanceof Error ? err.message : 'Failed to load GYR scores');
      } finally {
        setLoading(false);
      }
    };

    fetchGYRScores();
  }, [isReady, userId, apiClient]); // ✅ Depend on auth setup

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 py-8 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading GYR metrics...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 py-8 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 text-xl mb-2">⚠️</div>
          <p className="text-gray-900 font-semibold mb-2">Failed to load GYR metrics</p>
          <p className="text-gray-600">{error}</p>
        </div>
      </div>
    );
  }

  // No data state
  if (!gyrData) {
    return (
      <div className="min-h-screen bg-gray-50 py-8 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">No GYR data available</p>
        </div>
      </div>
    );
  }

  return (
    <AuthGuard>
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">GYR Metrics</h1>
          <p className="text-gray-600">Real-time training performance indicators</p>
        </div>

        {/* Three Cards with Real Data */}
        <div className="flex gap-6 justify-center">
          <GYRMetricCard
            title="Total Runs"
            historicalScores={gyrData.totalRuns.historicalScores}
            greenCriteria={gyrData.totalRuns.criteria.green}
            yellowCriteria={gyrData.totalRuns.criteria.yellow}
            redCriteria={gyrData.totalRuns.criteria.red}
            metricType="totalRuns"
          />
          <GYRMetricCard
            title="Weekly Pace"
            historicalScores={gyrData.weeklyPace.historicalScores}
            greenCriteria={gyrData.weeklyPace.criteria.green}
            yellowCriteria={gyrData.weeklyPace.criteria.yellow}
            redCriteria={gyrData.weeklyPace.criteria.red}
            metricType="weeklyPace"
          />
          <GYRMetricCard
            title="Weekly HR Zones"
            historicalScores={gyrData.weeklyHRZones.historicalScores}
            greenCriteria={gyrData.weeklyHRZones.criteria.green}
            yellowCriteria={gyrData.weeklyHRZones.criteria.yellow}
            redCriteria={gyrData.weeklyHRZones.criteria.red}
            metricType="weeklyHRZones"
          />
        </div>
      </div>
    </div>
    </AuthGuard>
  );
}
