import React from 'react';

interface WelcomeModalProps {
  onClose: () => void;
}

const WelcomeModal: React.FC<WelcomeModalProps> = ({ onClose }) => {
  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
      onClick={(e) => {
        // Close modal only if clicking the backdrop, not the modal content
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6 md:p-8">
          {/* Header */}
          <div className="flex items-center mb-6">
            <div className="w-12 h-12 bg-blue-600 rounded-lg flex items-center justify-center mr-4">
              <span className="text-white text-2xl font-bold">SC</span>
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Welcome to SmartCoach!</h2>
              <p className="text-sm text-gray-600">Your personalized running coach is ready</p>
            </div>
          </div>

          {/* Introduction */}
          <div className="mb-6">
            <p className="text-gray-700 leading-relaxed">
              You're all set! Here's what you can do to get the most out of SmartCoach:
            </p>
          </div>

          {/* Feature Cards */}
          <div className="space-y-4 mb-6">
            {/* Weekly Activity Progress */}
            <div className="bg-purple-50 border border-purple-100 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center flex-shrink-0">
                  <span className="text-xl">📈</span>
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-gray-900 mb-1">Weekly Activity Progress</h3>
                  <p className="text-sm text-gray-700 leading-relaxed">
                    Track your progress with detailed metrics, weekly trends, and performance insights.
                    See how your training is improving over time.
                  </p>
                </div>
              </div>
            </div>

            {/* Training Plan */}
            <div className="bg-blue-50 border border-blue-100 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                  <span className="text-xl">📆</span>
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-gray-900 mb-1">Training Plan</h3>
                  <p className="text-sm text-gray-700 leading-relaxed">
                    View your personalized training plan with daily workouts tailored to your goals.
                    When you're ready, you can create a training plan that adjusts automatically based on your progress.
                  </p>
                </div>
              </div>
            </div>

          </div>

          {/* Call to Action */}
          <div className="bg-gray-50 rounded-lg p-4 mb-6">
            <p className="text-sm text-gray-700 leading-relaxed">
              <strong>💡 Tip:</strong> Start by exploring your <strong>Weekly Activity Progress</strong>.
              When you are ready, you can create a training plan.
            </p>
          </div>

          {/* Action Button */}
          <div className="flex justify-end">
            <button
              onClick={onClose}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors duration-200 shadow-md hover:shadow-lg cursor-pointer"
            >
              Get Started
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WelcomeModal;
