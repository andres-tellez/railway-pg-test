import React from 'react';

export default function MarathonGoalStep() {
  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-gray-800 mb-4">Your Marathon Goal</h2>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <div className="flex items-center justify-center mb-4">
            <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
              <span className="text-2xl">🏃‍♂️</span>
            </div>
          </div>
          <h3 className="text-lg font-semibold text-blue-800 mb-2">
            Complete the Marathon Safely
          </h3>
          <p className="text-blue-700">
            We'll create a safe training plan to help you complete your marathon.
            Our focus is on building your endurance gradually and safely to get you
            across the finish line.
          </p>
        </div>

        <div className="mt-6 text-sm text-gray-600">
          <p>
            <strong>What this means:</strong> Conservative training approach, 3-5 days per week,
            progressive mileage buildup, and a 20-mile peak long run.
          </p>
        </div>
      </div>
    </div>
  );
}
