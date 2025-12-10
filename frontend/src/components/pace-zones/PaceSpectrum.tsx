import React, { useEffect, useRef, useState } from 'react';
import type { PaceZonesResponse } from '@/types/paceZones';
import { getFullPaceRange, paceToPercentage, formatMarathonPace } from '@/utils/paceFormatters';
import { formatPace, formatPaceRange, UnitSystem } from '@/utils/unitFormatters';

interface PaceSpectrumProps {
  paceZones: PaceZonesResponse;
  unitSystem: UnitSystem;
}

const PaceSpectrum: React.FC<PaceSpectrumProps> = ({ paceZones, unitSystem }) => {
  const [hoveredZone, setHoveredZone] = useState<string | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const spectrumRef = useRef<HTMLDivElement>(null);

  const fullRange = getFullPaceRange(paceZones);

  // Intersection Observer for scroll animation
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setIsVisible(true);
          }
        });
      },
      { threshold: 0.1 }
    );

    if (spectrumRef.current) {
      observer.observe(spectrumRef.current);
    }

    return () => {
      if (spectrumRef.current) {
        observer.unobserve(spectrumRef.current);
      }
    };
  }, []);

  // Color mapping for gradients (using Tailwind color values)
  const gradientColors: Record<string, { from: string; to: string }> = {
    threshold: { from: '#ef4444', to: '#f97316' }, // red-500 to orange-500
    marathon: { from: '#f97316', to: '#eab308' }, // orange-500 to yellow-500
    steady: { from: '#eab308', to: '#22c55e' }, // yellow-500 to green-500
    easy: { from: '#22c55e', to: '#3b82f6' }, // green-500 to blue-500
  };

  // Calculate positions for each zone
  const zones = [
    {
      name: 'Threshold',
      key: 'threshold',
      min: paceZones.threshold.min,
      max: paceZones.threshold.max,
      label: formatPaceRange(paceZones.threshold.min, paceZones.threshold.max, unitSystem),
    },
    {
      name: 'Marathon',
      key: 'marathon',
      min: paceZones.marathon.pace,
      max: paceZones.marathon.pace,
      label: formatMarathonPace(paceZones.marathon.pace, unitSystem),
    },
    {
      name: 'Steady',
      key: 'steady',
      min: paceZones.steady.min,
      max: paceZones.steady.max,
      label: formatPaceRange(paceZones.steady.min, paceZones.steady.max, unitSystem),
    },
    {
      name: 'Easy',
      key: 'easy',
      min: paceZones.easy.min,
      max: paceZones.easy.max,
      label: formatPaceRange(paceZones.easy.min, paceZones.easy.max, unitSystem),
    },
  ];

  return (
    <div
      ref={spectrumRef}
      className="w-full bg-white rounded-xl shadow-md p-6 md:p-8 border border-gray-200"
    >
      <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-6">
        Your Pace Spectrum
      </h2>
      <p className="text-gray-700 mb-6 leading-relaxed">
        Visual representation of your personalized pace zones. Faster paces are on the left,
        slower paces on the right.
      </p>

      {/* Spectrum Bar Container */}
      <div className="relative mb-8">
        <div className="relative h-16 rounded-lg overflow-hidden shadow-inner bg-gray-100">
          {/* Gradient Background */}
          <div
            className={`absolute inset-0 bg-gradient-to-r from-red-500 via-orange-500 via-yellow-500 via-green-500 to-blue-500 transition-opacity duration-500 ${
              isVisible ? 'opacity-100' : 'opacity-0'
            }`}
            style={{
              transition: 'opacity 0.5s ease-in-out',
            }}
          />

          {/* Zone Markers */}
          {zones.map((zone, index) => {
            const leftPercent = paceToPercentage(zone.max, fullRange.min, fullRange.max);
            const rightPercent = paceToPercentage(zone.min, fullRange.min, fullRange.max);
            const width = rightPercent - leftPercent;

            return (
              <div
                key={zone.name}
                className="absolute top-0 bottom-0 border-x-2 border-white/50"
                style={{
                  left: `${leftPercent}%`,
                  width: `${width}%`,
                  transition: isVisible
                    ? 'opacity 0.3s ease-in-out, transform 0.3s ease-in-out'
                    : 'none',
                  opacity: isVisible ? 1 : 0,
                  transform: isVisible ? 'translateY(0)' : 'translateY(10px)',
                  transitionDelay: `${index * 100}ms`,
                }}
                onMouseEnter={() => setHoveredZone(zone.name)}
                onMouseLeave={() => setHoveredZone(null)}
              >
                {/* Zone Label on Hover */}
                {hoveredZone === zone.name && (
                  <div className="absolute -top-12 left-1/2 transform -translate-x-1/2 bg-gray-900 text-white px-3 py-1 rounded-lg text-sm font-semibold whitespace-nowrap shadow-lg z-10">
                    {zone.name}: {zone.label}
                    <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 translate-y-full">
                      <div className="border-4 border-transparent border-t-gray-900"></div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Pace Labels at Ends */}
        <div className="flex justify-between mt-2 text-sm text-gray-600">
          <span className="font-semibold">
            Fastest: {formatPace(fullRange.min, unitSystem)}
          </span>
          <span className="font-semibold">
            Slowest: {formatPace(fullRange.max, unitSystem)}
          </span>
        </div>
      </div>

      {/* Zone Legend */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {zones.map((zone, index) => (
          <div
            key={zone.name}
            className={`p-4 rounded-lg border-2 transition-all duration-200 ${
              hoveredZone === zone.name
                ? 'border-gray-400 shadow-md scale-105'
                : 'border-gray-200'
            }`}
            style={{
              transitionDelay: isVisible ? `${(index + zones.length) * 50}ms` : '0ms',
              opacity: isVisible ? 1 : 0,
              transform: isVisible ? 'translateY(0)' : 'translateY(10px)',
            }}
            onMouseEnter={() => setHoveredZone(zone.name)}
            onMouseLeave={() => setHoveredZone(null)}
          >
            <div className="flex items-center space-x-2 mb-2">
              <div
                className="w-4 h-4 rounded-full"
                style={{
                  background: `linear-gradient(to right, ${gradientColors[zone.key]?.from || '#ef4444'}, ${gradientColors[zone.key]?.to || '#f97316'})`,
                }}
              />
              <h3 className="font-semibold text-gray-900">{zone.name}</h3>
            </div>
            <p className="text-sm text-gray-700">{zone.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default PaceSpectrum;
