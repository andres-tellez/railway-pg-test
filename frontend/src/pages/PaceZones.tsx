import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { AuthGuard } from '@/components/AuthGuard';
import { useUnitSystem } from '@/context/UnitSystemContext';
import { useApiClient } from '@/utils/apiClient';
import PaceSpectrum from '@/components/pace-zones/PaceSpectrum';
import PaceZoneCard from '@/components/pace-zones/PaceZoneCard';
import { getFormattedPaceForZone } from '@/utils/paceFormatters';
import type { PaceZonesResponse, PaceZoneInfo } from '@/types/paceZones';

const PaceZones: React.FC = () => {
  const api = useApiClient();
  const { unitSystem } = useUnitSystem();
  const [paceZones, setPaceZones] = useState<PaceZonesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());

  // Fetch pace zones from API
  useEffect(() => {
    const fetchPaceZones = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await api.get<PaceZonesResponse>('/api/pace-zones');
        const data = response.data.data || response.data;
        setPaceZones(data);
      } catch (err: any) {
        console.error('Failed to fetch pace zones:', err);
        setError(
          err.response?.data?.message ||
            'Failed to load pace zones. Please try again later.'
        );
      } finally {
        setLoading(false);
      }
    };

    fetchPaceZones();
  }, [api]);

  const toggleCard = (zoneName: string) => {
    setExpandedCards((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(zoneName)) {
        newSet.delete(zoneName);
      } else {
        newSet.add(zoneName);
      }
      return newSet;
    });
  };

  // Pace zone information
  const zoneInfos: Record<string, PaceZoneInfo> = {
    threshold: {
      name: 'Threshold',
      icon: '🔥',
      color: 'red',
      rpe: '8-9',
      tag: 'Hard',
      tagIcon: '⚡',
      description:
        'Threshold pace is your "comfortably hard" effort—the fastest pace you can sustain for about 20-30 minutes. This is where your body is working at its lactate threshold, the point where lactate begins to accumulate faster than your body can clear it.',
      whenToUse:
        'Use threshold pace for tempo runs, cruise intervals, and sustained efforts. These workouts improve your body\'s ability to clear lactate and run faster for longer periods.',
      typicalDuration: '10-30 minutes',
      percentage: '5-10%',
    },
    marathon: {
      name: 'Marathon',
      icon: '🏃',
      color: 'orange',
      rpe: '7-8',
      tag: 'Goal',
      tagIcon: '🎯',
      description:
        'Marathon pace is your target race pace for the full marathon distance. It\'s faster than your easy pace but sustainable for the entire 26.2 miles. This pace should feel controlled and sustainable.',
      whenToUse:
        'Use marathon pace for race-specific training, long runs with marathon pace segments, and building confidence at your goal pace. Practice this pace regularly to develop the muscle memory and mental fortitude needed on race day.',
      typicalDuration: '2-4 hours',
      percentage: '10-15%',
    },
    steady: {
      name: 'Steady',
      icon: '⚖️',
      color: 'yellow',
      rpe: '6-7',
      tag: 'Moderate',
      tagIcon: '📊',
      description:
        'Steady pace sits between your marathon pace and easy pace. It\'s a moderate effort that feels comfortably challenging—not too easy, not too hard. This pace helps build aerobic capacity while maintaining good form.',
      whenToUse:
        'Use steady pace for moderate long runs, progression runs, and when you want a bit more intensity than easy pace without going into threshold territory. Great for building endurance with controlled effort.',
      typicalDuration: '30-90 minutes',
      percentage: '10-20%',
    },
    easy: {
      name: 'Easy',
      icon: '🌱',
      color: 'green',
      rpe: '3-5',
      tag: 'Recovery',
      tagIcon: '💚',
      description:
        'Easy pace is your foundation—the pace where you can comfortably hold a conversation. This is where most of your training should happen. Easy runs build aerobic capacity, improve running economy, and promote recovery.',
      whenToUse:
        'Use easy pace for most of your runs, especially recovery days, long runs, and base building. The majority of your training (70-80%) should be at easy pace. If you\'re not sure what pace to run, go easy.',
      typicalDuration: '30 minutes - 3+ hours',
      percentage: '70-80%',
    },
  };

  if (loading) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-gray-50 py-8">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
              <p className="mt-4 text-gray-600">Loading your pace zones...</p>
            </div>
          </div>
        </div>
      </AuthGuard>
    );
  }

  if (error) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-gray-50 py-8">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
              <div className="text-4xl mb-4">⚠️</div>
              <h2 className="text-2xl font-bold text-red-900 mb-2">Error</h2>
              <p className="text-red-700 mb-4">{error}</p>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        </div>
      </AuthGuard>
    );
  }

  if (!paceZones) {
    return null;
  }

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Hero Section */}
          <div className="text-center mb-12">
            <div className="text-6xl mb-4">🏃‍♂️</div>
            <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              Your Pace Zones
            </h1>
            <p className="text-lg md:text-xl text-gray-700 max-w-3xl mx-auto leading-relaxed">
              Your personalized pace zones are calculated from your recent running performance.
              Each zone serves a specific purpose in your training.
            </p>
            {paceZones.source && (
              <div className="mt-4 inline-block bg-blue-50 border border-blue-200 rounded-lg px-4 py-2">
                <p className="text-sm text-blue-900">
                  <strong>Source:</strong> {paceZones.source}
                </p>
              </div>
            )}
          </div>

          {/* Interactive Pace Spectrum */}
          <div className="mb-12">
            <PaceSpectrum paceZones={paceZones} unitSystem={unitSystem} />
          </div>

          {/* Pace Zone Cards */}
          <div className="space-y-6 mb-12">
            <h2 className="text-3xl font-bold text-gray-900 mb-6">
              Understanding Your Zones
            </h2>
            {(['threshold', 'marathon', 'steady', 'easy'] as const).map((zoneType) => {
              const info = zoneInfos[zoneType];
              const paceRange = getFormattedPaceForZone(paceZones, zoneType, unitSystem);
              return (
                <PaceZoneCard
                  key={zoneType}
                  info={info}
                  paceRange={paceRange}
                  isExpanded={expandedCards.has(zoneType)}
                  onToggle={() => toggleCard(zoneType)}
                />
              );
            })}
          </div>

          {/* Science Behind This Section */}
          <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl shadow-md p-6 md:p-8 mb-8 border border-indigo-200">
            <div className="flex items-start space-x-4">
              <div className="text-4xl flex-shrink-0">🔬</div>
              <div>
                <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-4">
                  The Science Behind This
                </h2>
                <div className="space-y-4 text-gray-700 leading-relaxed">
                  <p>
                    <strong>Performance-Based Calculation:</strong> Your pace zones are
                    calculated from the median easy pace of your last 6 weeks of runs (2+ miles).
                    This ensures your zones are personalized to your current fitness level.
                  </p>
                  <p>
                    <strong>Why Different Zones Matter:</strong> Each pace zone targets
                    different physiological adaptations. Easy pace builds aerobic capacity,
                    threshold pace improves lactate clearance, and marathon pace builds
                    race-specific endurance.
                  </p>
                  <p>
                    <strong>Adaptive Training:</strong> As your fitness improves, your pace
                    zones will automatically adjust. Faster paces at the same effort level
                    indicate improved fitness.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Takeaway Section */}
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl shadow-md p-6 md:p-8 mb-8 border border-blue-200">
            <div className="text-center">
              <div className="text-4xl mb-4">💡</div>
              <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-4">
                Key Takeaway
              </h2>
              <p className="text-lg md:text-xl text-gray-700 leading-relaxed max-w-2xl mx-auto">
                Most of your training (70-80%) should be at easy pace. The remaining 20-30%
                should be split between steady, marathon, and threshold paces. This balance
                optimizes fitness gains while minimizing injury risk.
              </p>
            </div>
          </div>

          {/* Related Links */}
          <div className="text-center space-y-4">
            <Link
              to="/heart-rate-zones"
              className="inline-flex items-center px-6 py-3 bg-red-600 text-white font-semibold rounded-lg hover:bg-red-700 transition-colors shadow-md hover:shadow-lg"
            >
              Learn About Heart Rate Zones
              <svg
                className="ml-2 w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 7l5 5m0 0l-5 5m5-5H6"
                />
              </svg>
            </Link>
            <div>
              <Link
                to="/my-plan"
                className="inline-flex items-center px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors shadow-md hover:shadow-lg"
              >
                View Your Training Plan
                <svg
                  className="ml-2 w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 7l5 5m0 0l-5 5m5-5H6"
                  />
                </svg>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </AuthGuard>
  );
};

export default PaceZones;
