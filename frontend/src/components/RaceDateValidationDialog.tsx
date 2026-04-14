import React from 'react';

interface RaceDateValidation {
  status: 'approve' | 'reject' | 'warn' | 'error';
  message: string;
  available_weeks: number;
  required_weeks: number;
  ready_date?: string;
  can_proceed: boolean;
  recommendation: string;
  fitness_summary: {
    current_weekly_mileage: number;
    current_long_run: number;
  };
  timeline_gap_weeks?: number;
  race_date?: string;
  plan_start_date?: string;
}

interface RaceDateValidationDialogProps {
  validation: RaceDateValidation;
  onProceed: () => void;
  onCancel: () => void;
}

const RaceDateValidationDialog: React.FC<RaceDateValidationDialogProps> = ({
  validation,
  onProceed,
  onCancel,
}) => {
  const { status, message, ready_date, timeline_gap_weeks, can_proceed, available_weeks, required_weeks } = validation;

  // Check if message is positive (for dynamic styling)
  const isPositiveMessage = message.includes('✅') || message.includes('ready to proceed') || message.includes("You're ready");
  const effectiveStatus = (can_proceed && isPositiveMessage) ? 'approve' : status;

  const getStatusIcon = () => {
    switch (effectiveStatus) {
      case 'approve':
        return (
          <svg className="h-6 w-6 text-green-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
        );
      case 'reject':
        return (
          <svg className="h-6 w-6 text-red-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
        );
      case 'warn':
        return (
          <svg className="h-6 w-6 text-orange-500" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
        );
      default:
        return null;
    }
  };

  const getStatusColor = () => {
    switch (effectiveStatus) {
      case 'approve':
        return 'bg-green-50 border-green-200';
      case 'reject':
        return 'bg-red-50 border-red-200';
      case 'warn':
        return 'bg-yellow-50 border-yellow-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  const getStatusTextColor = () => {
    switch (effectiveStatus) {
      case 'approve':
        return 'text-green-800';
      case 'reject':
        return 'text-red-800';
      case 'warn':
        return 'text-yellow-800';
      default:
        return 'text-gray-800';
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '';
    try {
      // Parse ISO date string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
      // Extract just the date part to avoid timezone issues
      const dateOnly = dateStr.split('T')[0]; // Get YYYY-MM-DD
      const [year, month, day] = dateOnly.split('-').map(Number);
      // Create date in local timezone (no time component)
      const date = new Date(year, month - 1, day);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    } catch {
      return dateStr;
    }
  };

  // Convert markdown **bold** to HTML <strong> tags
  const formatMessage = (text: string): string => {
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Convert **text** to <strong>text</strong>
      .replace(/\n/g, '<br />'); // Convert newlines to <br />
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="mx-4 max-w-2xl w-full rounded-lg bg-white shadow-xl overflow-hidden">
        {/* Header */}
        <div className={`px-6 py-4 border-b ${getStatusColor()}`}>
          <div className="flex items-center gap-3">
            {getStatusIcon()}
            <h2 className={`text-xl font-semibold ${getStatusTextColor()}`}>
              {(() => {
                // Dynamic header based on message content and context
                // If message is positive (starts with ✅ or contains "ready to proceed"), show positive header
                const isPositiveMessage = message.includes('✅') || message.includes('ready to proceed') || message.includes("You're ready");

                if (status === 'approve' || (can_proceed && isPositiveMessage)) {
                  return 'Great News!';
                }
                if (status === 'reject') {
                  return 'Timeline Concern';
                }
                // For "warn" status with positive message, show encouraging header
                if (can_proceed && isPositiveMessage) {
                  return 'Ready to Train';
                }
                // Only show "Training Plan Alert" for actual concerns
                return 'Training Plan Alert';
              })()}
            </h2>
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-4">
          <div className="whitespace-pre-line text-gray-700 mb-4" dangerouslySetInnerHTML={{__html: formatMessage(message)}} />
        </div>

        {/* Actions */}
        <div className="px-6 py-4 bg-gray-50 border-t flex justify-end gap-3">
          {status === 'approve' && (
            <button
              onClick={onProceed}
              className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-500"
            >
              Continue to Plan
            </button>
          )}

          {(status === 'reject' || status === 'warn') && (
            <>
              {can_proceed && (
                <button
                  onClick={onProceed}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  Create Plan Anyway
                </button>
              )}
              <button
                onClick={onCancel}
                className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-500"
              >
                Cancel
              </button>
            </>
          )}

          {status === 'error' && (
            <button
              onClick={onCancel}
              className="px-4 py-2 bg-gray-300 text-gray-700 rounded-md hover:bg-gray-400 focus:outline-none focus:ring-2 focus:ring-gray-500"
            >
              Close
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default RaceDateValidationDialog;
