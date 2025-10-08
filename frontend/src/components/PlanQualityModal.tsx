import React from 'react';

interface PlanQualityModalProps {
  quality: any;
  isOpen: boolean;
  onClose: () => void;
}

export default function PlanQualityModal({ quality, isOpen, onClose }: PlanQualityModalProps) {
  if (!isOpen || !quality) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-bold">Training Plan Quality Assessment</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl"
          >
            ×
          </button>
        </div>

        {/* Overall Assessment */}
        <div className="bg-gray-50 rounded-lg p-4 mb-6">
          <div className="flex items-center space-x-4 mb-3">
            <span className="text-4xl">{quality.grade_icon}</span>
            <div>
              <h3 className="text-xl font-semibold">Overall Grade: {quality.overall_grade}</h3>
              <p className="text-lg">Score: {quality.score}/100</p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="bg-white rounded p-3">
              <div className="text-2xl mb-1">{quality.safety_icon}</div>
              <div className="font-medium">Safety</div>
              <div className="text-sm text-gray-600">{quality.safety_rating}</div>
            </div>
            <div className="bg-white rounded p-3">
              <div className="text-2xl mb-1">{quality.readiness_icon}</div>
              <div className="font-medium">Race Ready</div>
              <div className="text-sm text-gray-600">{quality.race_readiness}</div>
            </div>
            <div className="bg-white rounded p-3">
              <div className="text-2xl mb-1">{quality.is_b_plus_passing ? '🏆' : '⚠️'}</div>
              <div className="font-medium">B+ Status</div>
              <div className="text-sm text-gray-600">{quality.is_b_plus_passing ? 'PASSED' : 'FAILED'}</div>
            </div>
          </div>
        </div>

        {/* B+ Detailed Scores */}
        <div className="mb-6">
          <h4 className="text-lg font-semibold mb-3">B+ Validation Scores</h4>
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-blue-50 rounded p-3">
              <div className="text-sm text-blue-600">Safety (40%)</div>
              <div className="text-lg font-bold">{quality.b_plus_detailed_scores.safety_score}/40</div>
            </div>
            <div className="bg-green-50 rounded p-3">
              <div className="text-sm text-green-600">Grade (30%)</div>
              <div className="text-lg font-bold">{quality.b_plus_detailed_scores.grade_score}/30</div>
            </div>
            <div className="bg-yellow-50 rounded p-3">
              <div className="text-sm text-yellow-600">Critical Issues (20%)</div>
              <div className="text-lg font-bold">{quality.b_plus_detailed_scores.critical_issues_score}/20</div>
            </div>
            <div className="bg-purple-50 rounded p-3">
              <div className="text-sm text-purple-600">Race Readiness (10%)</div>
              <div className="text-lg font-bold">{quality.b_plus_detailed_scores.race_readiness_score}/10</div>
            </div>
          </div>
          <div className="mt-3 p-3 bg-gray-100 rounded">
            <div className="text-center">
              <div className="text-2xl font-bold">{quality.b_plus_detailed_scores.total_score}/100</div>
              <div className="text-sm text-gray-600">Total B+ Score (Minimum: 80)</div>
            </div>
          </div>
        </div>

        {/* Violations */}
        {quality.violations && quality.violations.length > 0 && (
          <div className="mb-6">
            <h4 className="text-lg font-semibold mb-3">Issues Found</h4>
            <div className="space-y-2">
              {quality.violations.map((violation: any, index: number) => (
                <div key={index} className="flex items-start space-x-3 p-3 bg-red-50 rounded">
                  <span className="text-lg">{violation.icon}</span>
                  <div className="flex-1">
                    <div className="font-medium">{violation.type}</div>
                    <div className="text-sm text-gray-600">{violation.description}</div>
                    <div className="text-xs text-gray-500 mt-1">Fix: {violation.fix}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Strengths */}
        {quality.strengths && quality.strengths.length > 0 && (
          <div className="mb-6">
            <h4 className="text-lg font-semibold mb-3">Plan Strengths</h4>
            <div className="space-y-2">
              {quality.strengths.map((strength: string, index: number) => (
                <div key={index} className="flex items-center space-x-2 p-2 bg-green-50 rounded">
                  <span className="text-green-500">✅</span>
                  <span className="text-sm">{strength}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recommendations */}
        {quality.recommendations && quality.recommendations.length > 0 && (
          <div className="mb-6">
            <h4 className="text-lg font-semibold mb-3">Recommendations</h4>
            <div className="space-y-2">
              {quality.recommendations.map((rec: any, index: number) => (
                <div key={index} className="flex items-start space-x-3 p-3 bg-blue-50 rounded">
                  <span className="text-lg">{rec.icon}</span>
                  <div className="flex-1">
                    <div className="font-medium">{rec.category}</div>
                    <div className="text-sm text-gray-600">{rec.recommendation}</div>
                    <div className="text-xs text-gray-500 mt-1">Priority: {rec.priority}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="bg-blue-500 text-white px-6 py-2 rounded hover:bg-blue-600"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
