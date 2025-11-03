import React, { useState } from 'react';
import { useApiClient } from '../utils/apiClient';
import { useAuthSetup } from '../hooks/useAuthSetup';

const DataDeletion: React.FC = () => {
  const { isReady, userId } = useAuthSetup();
  const api = useApiClient();
  const [isDeleting, setIsDeleting] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [deletionResult, setDeletionResult] = useState<{
    success: boolean;
    message: string;
    deleted?: any;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDeleteAccount = async () => {
    if (!isReady || !userId) {
      setError('Please log in to delete your account');
      return;
    }

    setIsDeleting(true);
    setError(null);
    setDeletionResult(null);

    try {
      const response = await api.delete('/api/user/delete-account');
      setDeletionResult({
        success: true,
        message: response.data.message || 'Your account has been deleted',
        deleted: response.data.deleted,
      });
      // Redirect to logout or home after successful deletion
      setTimeout(() => {
        window.location.href = '/login';
      }, 3000);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to delete account. Please try again or contact support.');
      setDeletionResult(null);
    } finally {
      setIsDeleting(false);
      setShowConfirm(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-md p-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Data Deletion Instructions</h1>
        <p className="text-sm text-gray-600 mb-8">Last Updated: November 3, 2025</p>

        <div className="space-y-6 text-gray-700">
          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">Your Right to Delete Your Data</h2>
            <p>
              Under GDPR Article 17 (Right to Erasure) and other privacy regulations, you have the right to request
              deletion of all personal data we hold about you. SmartCoach provides a simple, self-service way to
              permanently delete your account and all associated data.
            </p>
            <p className="mt-2">
              <strong>Important:</strong> Account deletion is immediate and irreversible. Once deleted, we cannot
              recover your data.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">What Gets Deleted</h2>
            <p>When you delete your account, we permanently remove:</p>
            <ul className="list-disc pl-6 mt-2 space-y-2">
              <li><strong>User Account:</strong> Your user identity and authentication data</li>
              <li><strong>Profile Information:</strong> Your onboarding data and preferences</li>
              <li><strong>Strava Connection:</strong> Your linked Strava athlete account and access tokens</li>
              <li><strong>Activity Data:</strong> All running activities imported from Strava</li>
              <li><strong>Training Plans:</strong> All your training plans and workout data</li>
              <li><strong>Conversations:</strong> All chat conversations and coaching interactions</li>
              <li><strong>Metrics & Analytics:</strong> All performance metrics and historical data</li>
            </ul>
            <p className="mt-4">
              <strong>Note:</strong> Deleting your SmartCoach account does not affect your Strava account. Your
              activities and data remain in Strava. We only delete the copy of your data stored in SmartCoach.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">How to Delete Your Account</h2>

            {!isReady ? (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p className="text-blue-800">
                  Please <a href="/login" className="underline font-semibold">log in</a> to access the account deletion tool.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="bg-red-50 border-2 border-red-200 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-red-900 mb-3">⚠️ Permanent Account Deletion</h3>
                  <p className="text-red-800 mb-4">
                    This action cannot be undone. All your data will be permanently deleted immediately.
                  </p>

                  {!showConfirm && !deletionResult && (
                    <button
                      onClick={() => setShowConfirm(true)}
                      className="px-6 py-3 bg-red-600 text-white rounded-lg font-semibold hover:bg-red-700 transition-colors"
                    >
                      Delete My Account
                    </button>
                  )}

                  {showConfirm && !deletionResult && (
                    <div className="space-y-4">
                      <div className="bg-white border-2 border-red-300 rounded-lg p-4">
                        <p className="font-semibold text-red-900 mb-2">Are you absolutely sure?</p>
                        <p className="text-sm text-red-800">
                          This will permanently delete:
                        </p>
                        <ul className="text-sm text-red-800 list-disc pl-6 mt-2 space-y-1">
                          <li>All your training plans</li>
                          <li>All your activity history</li>
                          <li>All your conversations and data</li>
                          <li>Your SmartCoach account</li>
                        </ul>
                        <p className="text-sm text-red-800 mt-2 font-semibold">
                          This action cannot be reversed.
                        </p>
                      </div>
                      <div className="flex gap-3">
                        <button
                          onClick={handleDeleteAccount}
                          disabled={isDeleting}
                          className="px-6 py-3 bg-red-600 text-white rounded-lg font-semibold hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {isDeleting ? 'Deleting...' : 'Yes, Delete My Account'}
                        </button>
                        <button
                          onClick={() => setShowConfirm(false)}
                          disabled={isDeleting}
                          className="px-6 py-3 bg-gray-200 text-gray-800 rounded-lg font-semibold hover:bg-gray-300 transition-colors disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}

                  {deletionResult && deletionResult.success && (
                    <div className="bg-green-50 border-2 border-green-200 rounded-lg p-4">
                      <p className="text-green-800 font-semibold mb-2">✅ Account Deleted Successfully</p>
                      <p className="text-sm text-green-700">
                        Your account and all data have been permanently deleted. You will be redirected to the login page shortly.
                      </p>
                      {deletionResult.deleted && (
                        <details className="mt-3">
                          <summary className="text-sm text-green-700 cursor-pointer">Deletion Summary</summary>
                          <pre className="mt-2 text-xs bg-white p-2 rounded overflow-auto">
                            {JSON.stringify(deletionResult.deleted, null, 2)}
                          </pre>
                        </details>
                      )}
                    </div>
                  )}

                  {error && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mt-4">
                      <p className="text-red-800 font-semibold">Error</p>
                      <p className="text-sm text-red-700 mt-1">{error}</p>
                    </div>
                  )}
                </div>
              </div>
            )}
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">Alternative: API Endpoint</h2>
            <p>
              If you prefer to delete your account programmatically, you can use our API endpoint:
            </p>
            <div className="bg-gray-100 rounded-lg p-4 mt-3 font-mono text-sm">
              <p className="text-gray-800 mb-2">
                <strong>DELETE</strong> <code className="bg-gray-200 px-2 py-1 rounded">/api/user/delete-account</code>
              </p>
              <p className="text-xs text-gray-600 mt-2">
                Requires authentication. Returns deletion summary upon successful completion.
              </p>
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">Need Help?</h2>
            <p>
              If you have questions about data deletion or need assistance, please contact us:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>
                <strong>Email:</strong>{' '}
                <a href="mailto:support@smartcoach.app" className="text-blue-600 hover:underline">
                  support@smartcoach.app
                </a>
              </li>
              <li>
                <strong>Response Time:</strong> We typically respond within 24-48 hours
              </li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">Related Information</h2>
            <ul className="list-disc pl-6 space-y-1">
              <li>
                <a href="/privacy-policy" className="text-blue-600 hover:underline">
                  Privacy Policy
                </a>
                {' - Learn more about how we handle your data'}
              </li>
              <li>
                <a href="/terms-of-service" className="text-blue-600 hover:underline">
                  Terms of Service
                </a>
                {' - Our terms and conditions'}
              </li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
};

export default DataDeletion;
