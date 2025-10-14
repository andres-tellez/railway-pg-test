import React from 'react';

interface HeartRateZoneData {
  zone_1: number;
  zone_2: number;
  zone_3: number;
  zone_4: number;
  zone_5: number;
}

interface HeartRateZoneChartProps {
  hrZones: HeartRateZoneData;
  title?: string;
}

export default function HeartRateZoneChart({ hrZones, title = "Heart Rate Zone Distribution" }: HeartRateZoneChartProps) {
  // Convert zone data to array format for easier rendering
  const zoneData = [
    { zone: 'Zone 1', percentage: hrZones.zone_1, color: '#3B82F6', description: 'Recovery' },
    { zone: 'Zone 2', percentage: hrZones.zone_2, color: '#10B981', description: 'Aerobic Base' },
    { zone: 'Zone 3', percentage: hrZones.zone_3, color: '#F59E0B', description: 'Tempo' },
    { zone: 'Zone 4', percentage: hrZones.zone_4, color: '#DC2626', description: 'Threshold' },
    { zone: 'Zone 5', percentage: hrZones.zone_5, color: '#8B5CF6', description: 'VO2 Max' }
  ];

  const totalPercentage = Object.values(hrZones).reduce((sum, val) => sum + val, 0);
  const hasData = totalPercentage > 0;

  return (
    <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">{title}</h3>

      {!hasData ? (
        <div className="text-center py-8 text-gray-500">
          <div className="text-4xl mb-2">💓</div>
          <p>No heart rate data available</p>
          <p className="text-sm">Connect a heart rate monitor to see zone distribution</p>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Zone Bars */}
          <div className="space-y-3">
            {zoneData.map((zone) => (
              <div key={zone.zone} className="flex items-center space-x-3">
                <div className="w-16 text-sm font-medium text-gray-700">{zone.zone}</div>
                <div className="flex-1">
                  <div className="bg-gray-200 rounded-full h-4 relative overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-300"
                      style={{
                        width: `${Math.max(zone.percentage, 2)}%`,
                        backgroundColor: zone.color
                      }}
                    />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <span className="text-xs font-medium text-white mix-blend-difference">
                        {zone.percentage > 5 ? `${zone.percentage.toFixed(1)}%` : ''}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="w-20 text-sm text-gray-600">{zone.description}</div>
              </div>
            ))}
          </div>

          {/* Summary Stats */}
          <div className="mt-6 pt-4 border-t border-gray-200">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-600">Total Time:</span>
                <span className="ml-2 font-medium">{totalPercentage.toFixed(1)}%</span>
              </div>
              <div>
                <span className="text-gray-600">Primary Zone:</span>
                <span className="ml-2 font-medium">
                  {zoneData.reduce((max, zone) => zone.percentage > max.percentage ? zone : max).zone}
                </span>
              </div>
            </div>
          </div>

          {/* Training Zone Legend */}
          <div className="mt-4 p-3 bg-blue-50 rounded-lg">
            <h4 className="text-sm font-medium text-blue-900 mb-2">Training Zone Guide</h4>
            <div className="text-xs text-blue-800 space-y-1">
              <div><strong>Zone 1-2:</strong> Build aerobic base, easy pace</div>
              <div><strong>Zone 3:</strong> Moderate effort, tempo pace</div>
              <div><strong>Zone 4-5:</strong> High intensity, threshold/VO2 max</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
