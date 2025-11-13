/**
 * Date Test Page
 * 
 * Test page to verify date matching logic before deployment.
 * Access at /date-test (add route if needed)
 */

import React, { useState } from 'react';
import { runAllDateTests, testDateMatching, testWeekRange, testProcessWeekData } from '../utils/dateTestUtils';

const DateTestPage: React.FC = () => {
  const [testDate, setTestDate] = useState('2024-11-12');
  const [results, setResults] = useState<any>(null);

  const handleRunTests = () => {
    console.clear();
    console.log('🧪 Running date tests with test date:', testDate);
    runAllDateTests(testDate);
    
    // Capture results for display
    const matchingResults = testDateMatching();
    const weekRangeResult = testWeekRange(testDate);
    const processResult = testProcessWeekData(testDate);
    
    setResults({
      matching: matchingResults,
      weekRange: weekRangeResult,
      process: processResult,
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Date Matching Test Suite</h1>
          <p className="text-gray-600 mb-4">
            Test the date matching logic to verify workouts appear on the correct days.
            Check the browser console for detailed logs.
          </p>
          
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Test Date (YYYY-MM-DD):
            </label>
            <input
              type="date"
              value={testDate}
              onChange={(e) => setTestDate(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <button
            onClick={handleRunTests}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            Run All Tests
          </button>
        </div>

        {results && (
          <div className="space-y-4">
            {/* Date Matching Results */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Date Matching Tests
              </h2>
              <div className="mb-2">
                <span className="text-sm text-gray-600">
                  Passed: <span className="font-semibold text-green-600">{results.matching.passed}</span> / 
                  Failed: <span className="font-semibold text-red-600">{results.matching.failed}</span>
                </span>
              </div>
              <div className="space-y-2">
                {results.matching.results.map((result: any, idx: number) => (
                  <div
                    key={idx}
                    className={`p-3 rounded border ${
                      result.passed
                        ? 'bg-green-50 border-green-200'
                        : 'bg-red-50 border-red-200'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span>{result.passed ? '✅' : '❌'}</span>
                      <span className="font-medium">{result.test}</span>
                    </div>
                    <div className="text-sm text-gray-600 ml-7">{result.details}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Week Range Results */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Week Range Test
              </h2>
              <div className={`p-3 rounded border ${
                results.weekRange.passed
                  ? 'bg-green-50 border-green-200'
                  : 'bg-red-50 border-red-200'
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  <span>{results.weekRange.passed ? '✅' : '❌'}</span>
                  <span className="font-medium">
                    {results.weekRange.passed ? 'PASSED' : 'FAILED'}
                  </span>
                </div>
                <div className="text-sm text-gray-600 space-y-1 ml-7">
                  <div>Test Date: {results.weekRange.details.testDate}</div>
                  <div>Week Start: {results.weekRange.details.weekStart} (Day: {results.weekRange.details.weekStartDay}, should be 1=Monday)</div>
                  <div>Week End: {results.weekRange.details.weekEnd} (Day: {results.weekRange.details.weekEndDay}, should be 0=Sunday)</div>
                </div>
              </div>
            </div>

            {/* Process Week Data Results */}
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">
                Process Week Data Test
              </h2>
              <div className={`p-3 rounded border mb-4 ${
                results.process.passed
                  ? 'bg-green-50 border-green-200'
                  : 'bg-red-50 border-red-200'
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  <span>{results.process.passed ? '✅' : '❌'}</span>
                  <span className="font-medium">
                    {results.process.passed ? 'PASSED' : 'FAILED'}
                  </span>
                </div>
                <div className="text-sm text-gray-600 space-y-1 ml-7">
                  <div>Test Date: {results.process.details.testDate}</div>
                  <div>Workouts Matched: {results.process.details.workoutsMatched} / {results.process.details.expectedWorkouts}</div>
                </div>
              </div>
              <div className="space-y-1">
                <div className="text-sm font-medium text-gray-700 mb-2">Week Days:</div>
                {results.process.details.weekDays.map((day: any, idx: number) => (
                  <div key={idx} className="text-sm text-gray-600 p-2 bg-gray-50 rounded">
                    <span className="font-medium">{day.dateStr}:</span>{' '}
                    {day.hasWorkout ? (
                      <>
                        Workout on {day.workoutDate} {day.isCompleted ? '✓ Completed' : ''}
                      </>
                    ) : (
                      'No workout'
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mt-6">
          <h3 className="font-semibold text-blue-900 mb-2">💡 Testing Tips</h3>
          <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
            <li>Open browser console (F12) to see detailed logs</li>
            <li>Test with today's date to verify real-world behavior</li>
            <li>Test with dates near week boundaries (Sunday/Monday)</li>
            <li>Check that workouts match the correct days</li>
            <li>Verify week range starts on Monday and ends on Sunday</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default DateTestPage;

