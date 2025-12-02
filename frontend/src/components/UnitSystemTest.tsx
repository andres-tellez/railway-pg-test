/**
 * Unit System Test Component
 *
 * Temporary component to test Phase 0 unit system integration.
 * This component demonstrates:
 * - Context is working
 * - Unit conversions are working
 * - Toggle functionality
 *
 * Remove this file after Phase 0 testing is complete.
 */

import React from 'react';
import { useUnitSystem } from '../context/UnitSystemContext';
import {
  formatDistance,
  formatPace,
  formatElevation,
  formatRaceDistance,
  getUnitLabels,
} from '../utils/unitFormatters';

export default function UnitSystemTest() {
  const { unitSystem, setUnitSystem } = useUnitSystem();

  // Test values (in imperial base units from backend)
  const testDistance = 5.0; // miles
  const testPace = 480; // seconds per mile (8:00 min/mi)
  const testElevation = 1000; // feet

  const unitLabels = getUnitLabels(unitSystem);

  return (
    <div className="max-w-4xl mx-auto p-8 bg-white rounded-lg shadow-lg">
      <h1 className="text-2xl font-bold mb-6">Unit System Test (Phase 0)</h1>

      {/* Current Unit System Display */}
      <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
        <h2 className="text-lg font-semibold mb-2">Current Unit System</h2>
        <p className="text-2xl font-bold text-blue-600">
          {unitSystem === 'imperial' ? '🇺🇸 Imperial' : '🌍 Metric'}
        </p>
        <p className="text-sm text-gray-600 mt-1">
          {unitSystem === 'imperial'
            ? 'Using: miles, min/mi, feet'
            : 'Using: km, min/km, meters'}
        </p>
      </div>

      {/* Toggle Buttons */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold mb-3">Toggle Unit System</h2>
        <div className="flex space-x-4">
          <button
            onClick={() => setUnitSystem('imperial')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              unitSystem === 'imperial'
                ? 'bg-blue-600 text-white shadow-md'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Imperial
          </button>
          <button
            onClick={() => setUnitSystem('metric')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              unitSystem === 'metric'
                ? 'bg-blue-600 text-white shadow-md'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Metric
          </button>
        </div>
      </div>

      {/* Conversion Tests */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Conversion Tests</h2>

        {/* Distance */}
        <div className="p-4 bg-gray-50 rounded-lg">
          <h3 className="font-medium mb-2">Distance</h3>
          <p className="text-sm text-gray-600 mb-1">
            Input: {testDistance} miles (from backend)
          </p>
          <p className="text-xl font-bold">
            Display: {formatDistance(testDistance, unitSystem)}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Unit Label: {unitLabels.distanceAbbrev}
          </p>
        </div>

        {/* Pace */}
        <div className="p-4 bg-gray-50 rounded-lg">
          <h3 className="font-medium mb-2">Pace</h3>
          <p className="text-sm text-gray-600 mb-1">
            Input: {testPace} seconds/mile (8:00 min/mi from backend)
          </p>
          <p className="text-xl font-bold">
            Display: {formatPace(testPace, unitSystem)}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Unit Label: {unitLabels.paceAbbrev}
          </p>
        </div>

        {/* Elevation */}
        <div className="p-4 bg-gray-50 rounded-lg">
          <h3 className="font-medium mb-2">Elevation</h3>
          <p className="text-sm text-gray-600 mb-1">
            Input: {testElevation} feet (from backend)
          </p>
          <p className="text-xl font-bold">
            Display: {formatElevation(testElevation, unitSystem)}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Unit Label: {unitLabels.elevationAbbrev}
          </p>
        </div>

        {/* Race Distances */}
        <div className="p-4 bg-gray-50 rounded-lg">
          <h3 className="font-medium mb-2">Race Distances</h3>
          <div className="space-y-2">
            <p>
              <span className="font-medium">Marathon:</span>{' '}
              {formatRaceDistance('marathon', unitSystem)}
            </p>
            <p>
              <span className="font-medium">Half Marathon:</span>{' '}
              {formatRaceDistance('half_marathon', unitSystem)}
            </p>
            <p>
              <span className="font-medium">10K:</span>{' '}
              {formatRaceDistance('10k', unitSystem)}
            </p>
            <p>
              <span className="font-medium">5K:</span>{' '}
              {formatRaceDistance('5k', unitSystem)}
            </p>
          </div>
        </div>
      </div>

      {/* localStorage Test */}
      <div className="mt-6 p-4 bg-yellow-50 rounded-lg border border-yellow-200">
        <h3 className="font-medium mb-2">localStorage Persistence</h3>
        <p className="text-sm text-gray-600">
          Current value in localStorage: <code className="bg-white px-2 py-1 rounded">{localStorage.getItem('smartcoach_unit_system') || 'not set'}</code>
        </p>
        <p className="text-xs text-gray-500 mt-2">
          Try refreshing the page - the unit system should persist!
        </p>
      </div>

      {/* Test Checklist */}
      <div className="mt-6 p-4 bg-green-50 rounded-lg border border-green-200">
        <h3 className="font-medium mb-2">✅ Test Checklist</h3>
        <ul className="text-sm space-y-1">
          <li>✓ Context loads without errors</li>
          <li>✓ Toggle buttons work</li>
          <li>✓ Conversions update immediately</li>
          <li>✓ localStorage persists preference</li>
          <li>✓ Page refresh maintains preference</li>
        </ul>
      </div>
    </div>
  );
}
