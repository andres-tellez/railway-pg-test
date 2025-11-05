import React, { useState } from 'react';

interface StravaConsentModalProps {
  onAccept: () => void;
  onDecline: () => void;
}

const StravaConsentModal: React.FC<StravaConsentModalProps> = ({ onAccept, onDecline }) => {
  const [hasReadPrivacy, setHasReadPrivacy] = useState(false);
  const [hasReadTerms, setHasReadTerms] = useState(false);
  const [consentGiven, setConsentGiven] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  const canProceed = hasReadPrivacy && hasReadTerms && consentGiven;

  const handleAccept = () => {
    if (canProceed && !isConnecting) {
      setIsConnecting(true);
      // Small delay to show spinner before redirect
      setTimeout(() => {
        onAccept();
      }, 100);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50"
      onClick={(e) => {
        // Close modal only if clicking the backdrop, not the modal content
        if (e.target === e.currentTarget) {
          onDecline();
        }
      }}
    >
      <div
        className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center mb-4">
            <div className="w-12 h-12 bg-[#FC5200] rounded-lg flex items-center justify-center mr-3">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="text-white">
                <path
                  d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.599h4.172L10.463 0l-7.02 13.828h4.169"
                  fill="currentColor"
                />
              </svg>
            </div>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Connect with Strava</h2>
              <p className="text-sm text-gray-600">Data Authorization & Consent</p>
            </div>
          </div>

          {/* Content */}
          <div className="space-y-4">
            <div className="bg-blue-50 border-l-4 border-blue-400 p-4 rounded">
              <p className="font-semibold text-blue-900 mb-2">📊 What Data We'll Access</p>
              <p className="text-sm text-blue-800">
                When you connect your Strava account, SmartCoach will access:
              </p>
              <ul className="list-disc pl-5 mt-2 text-sm text-blue-800 space-y-1">
                <li><strong>Your running activities:</strong> distance, pace, heart rate, elevation</li>
                <li><strong>Your profile:</strong> name, profile picture</li>
                <li><strong>Performance metrics:</strong> splits, zones, and workout details</li>
              </ul>
            </div>

            <div className="bg-green-50 border-l-4 border-green-400 p-4 rounded">
              <p className="font-semibold text-green-900 mb-2">✅ How We'll Use Your Data</p>
              <ul className="list-disc pl-5 text-sm text-green-800 space-y-1">
                <li><strong>Training plan generation:</strong> Create personalized marathon plans</li>
                <li><strong>Progress tracking:</strong> Monitor your fitness improvements</li>
                <li><strong>Performance analysis:</strong> Provide insights and recommendations</li>
              </ul>
              <p className="text-sm text-green-800 mt-2 font-semibold">
                ✅ We will NEVER sell your data or share it with other users
              </p>
            </div>

            <div className="bg-gray-50 border-l-4 border-gray-400 p-4 rounded">
              <p className="font-semibold text-gray-900 mb-2">🔐 Your Privacy Rights</p>
              <ul className="list-disc pl-5 text-sm text-gray-700 space-y-1">
                <li><strong>Disconnect anytime:</strong> Revoke access through Strava settings</li>
                <li><strong>Export your data:</strong> Request a copy of all your SmartCoach data</li>
                <li><strong>Delete everything:</strong> Permanently remove all your data within 48 hours</li>
                <li><strong>GDPR compliant:</strong> We follow all data protection regulations</li>
              </ul>
            </div>

            {/* Checkboxes */}
            <div className="space-y-3 pt-4 border-t">
              <label className="flex items-start cursor-pointer">
                <input
                  type="checkbox"
                  checked={hasReadPrivacy}
                  onChange={(e) => setHasReadPrivacy(e.target.checked)}
                  className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded flex-shrink-0"
                  style={{ minWidth: '16px', minHeight: '16px' }}
                />
                <span className="ml-3 text-sm text-gray-700">
                  I have read and agree to the{' '}
                  <a
                    href="/privacy-policy"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline font-medium"
                  >
                    Privacy Policy
                  </a>
                </span>
              </label>

              <label className="flex items-start cursor-pointer">
                <input
                  type="checkbox"
                  checked={hasReadTerms}
                  onChange={(e) => setHasReadTerms(e.target.checked)}
                  className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded flex-shrink-0"
                  style={{ minWidth: '16px', minHeight: '16px' }}
                />
                <span className="ml-3 text-sm text-gray-700">
                  I have read and agree to the{' '}
                  <a
                    href="/terms-of-service"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline font-medium"
                  >
                    Terms of Service
                  </a>
                </span>
              </label>

              <label className="flex items-start cursor-pointer">
                <input
                  type="checkbox"
                  checked={consentGiven}
                  onChange={(e) => setConsentGiven(e.target.checked)}
                  className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded flex-shrink-0"
                  style={{ minWidth: '16px', minHeight: '16px' }}
                />
                <span className="ml-3 text-sm text-gray-700">
                  <strong>I consent to SmartCoach accessing my Strava data</strong> as described above,
                  and I understand that I can revoke this authorization at any time
                </span>
              </label>
            </div>

            {/* Legal Notice */}
            <div className="bg-gray-100 p-3 rounded text-xs text-gray-600">
              <p className="font-semibold mb-1">Legal Notice:</p>
              <p>
                SmartCoach is powered by Strava. By connecting, you also agree to{' '}
                <a
                  href="https://www.strava.com/legal/terms"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  Strava's Terms
                </a>{' '}
                and{' '}
                <a
                  href="https://www.strava.com/legal/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  Privacy Policy
                </a>.
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 mt-6">
            <button
              onClick={onDecline}
              disabled={isConnecting}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg text-gray-700 font-medium hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              onClick={handleAccept}
              disabled={!canProceed || isConnecting}
              className={`flex-1 px-4 py-3 rounded-lg font-medium transition-colors flex items-center justify-center gap-2 ${
                canProceed && !isConnecting
                  ? 'bg-[#FC5200] text-white hover:bg-[#E64700]'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
            >
              {isConnecting ? (
                <>
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                  <span>Connecting...</span>
                </>
              ) : canProceed ? (
                'Connect to Strava'
              ) : (
                'Please accept all terms'
              )}
            </button>
          </div>

          {/* Timestamp Info */}
          <p className="text-xs text-gray-500 mt-4 text-center">
            By clicking "Connect to Strava", your consent will be recorded with a timestamp for compliance purposes.
          </p>
        </div>
      </div>
    </div>
  );
};

export default StravaConsentModal;
