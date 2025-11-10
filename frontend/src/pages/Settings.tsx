import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApiClient } from '@/utils/apiClient';
import { useAuthSetup } from '@/hooks/useAuthSetup';
import { AuthGuard } from '@/components/AuthGuard';
import Layout from '@/components/Layout';

interface StravaStatus {
  connected: boolean;
  athlete_id?: number;
  connected_at?: string;
  activity_count?: number;
  message?: string;
}

const Settings: React.FC = () => {
  const { isReady, userId } = useAuthSetup();
  const api = useApiClient();
  const navigate = useNavigate();

  const [stravaStatus, setStravaStatus] = useState<StravaStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [disconnecting, setDisconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!isReady || !userId) return;

    fetchStravaStatus();
  }, [isReady, userId]);

  const fetchStravaStatus = async () => {
    try {
      setLoading(true);
      const response = await api.get<StravaStatus>('/strava/status');
      setStravaStatus(response.data);
    } catch (err: any) {
      console.error('Failed to fetch Strava status:', err);
      // If 404, user is not connected (not an error)
      if (err.response?.status !== 404) {
        setError('Failed to load Strava connection status');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm(
      'Are you sure you want to disconnect your Strava account?\n\n' +
      'This will:\n' +
      '• Revoke SmartCoach access to your Strava data\n' +
      '• Delete your Strava API tokens\n\n' +
      'This will NOT:\n' +
      '• Delete your synced activities\n' +
      '• Delete your training plans\n\n' +
      'You can reconnect anytime.'
    )) {
      return;
    }

    try {
      setDisconnecting(true);
      setError(null);
      setSuccess(null);

      const response = await api.delete('/strava/disconnect');

      setSuccess(response.data.message || 'Strava account disconnected successfully');

      // Refresh status
      await fetchStravaStatus();

      // Redirect to setup page after 2 seconds
      setTimeout(() => {
        navigate('/setup');
      }, 2000);
    } catch (err: any) {
      console.error('Failed to disconnect Strava:', err);
      setError(err.response?.data?.error || 'Failed to disconnect Strava account');
    } finally {
      setDisconnecting(false);
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    } catch {
      return dateString;
    }
  };

  return (
    <AuthGuard>
      <Layout>
        <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
          <div className="max-w-4xl mx-auto">
            <h1 className="text-3xl font-bold text-gray-900 mb-8">Settings</h1>

            {/* Strava Connection Section */}
            <div className="bg-white rounded-lg shadow-md p-6 mb-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-semibold text-gray-900">
                  Strava Connection
                </h2>
                {stravaStatus?.connected && (
                  <span className="px-3 py-1 bg-green-100 text-green-800 rounded-full text-sm font-medium">
                    Connected
                  </span>
                )}
              </div>

              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                </div>
              ) : stravaStatus?.connected ? (
                <div className="space-y-4">
                  <div className="bg-gray-50 rounded-lg p-4">
                    <dl className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Connection Status</dt>
                        <dd className="mt-1 text-sm text-gray-900">Connected</dd>
                      </div>
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Connected On</dt>
                        <dd className="mt-1 text-sm text-gray-900">
                          {formatDate(stravaStatus.connected_at)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Activities Synced</dt>
                        <dd className="mt-1 text-sm text-gray-900">
                          {stravaStatus.activity_count || 0}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Athlete ID</dt>
                        <dd className="mt-1 text-sm text-gray-900">
                          {stravaStatus.athlete_id}
                        </dd>
                      </div>
                    </dl>
                  </div>

                  <div className="border-t border-gray-200 pt-4">
                    <h3 className="text-lg font-medium text-gray-900 mb-3">
                      Disconnect Strava
                    </h3>
                    <p className="text-sm text-gray-600 mb-4">
                      Disconnecting your Strava account will revoke SmartCoach's access to your
                      Strava data. You can reconnect anytime through the setup page.
                    </p>

                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
                      <h4 className="text-sm font-semibold text-yellow-900 mb-2">
                        What happens when you disconnect:
                      </h4>
                      <ul className="text-sm text-yellow-800 space-y-1 list-disc list-inside">
                        <li>Your Strava API tokens will be deleted (access revoked)</li>
                        <li>SmartCoach will no longer sync new activities from Strava</li>
                        <li>SmartCoach will no longer access your Strava profile</li>
                      </ul>
                    </div>

                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                      <h4 className="text-sm font-semibold text-blue-900 mb-2">
                        What will be retained:
                      </h4>
                      <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
                        <li>All your synced activities remain in SmartCoach</li>
                        <li>All your training plans remain accessible</li>
                        <li>All your metrics and progress data remain intact</li>
                        <li>You can reconnect anytime to resume syncing</li>
                      </ul>
                    </div>

                    {error && (
                      <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
                        <p className="text-sm text-red-800">{error}</p>
                      </div>
                    )}

                    {success && (
                      <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg">
                        <p className="text-sm text-green-800">{success}</p>
                      </div>
                    )}

                    <button
                      onClick={handleDisconnect}
                      disabled={disconnecting}
                      className="px-4 py-2 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {disconnecting ? 'Disconnecting...' : 'Disconnect Strava Account'}
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8">
                  <p className="text-gray-600 mb-4">
                    You don't have a Strava account connected.
                  </p>
                  <button
                    onClick={() => navigate('/setup')}
                    className="px-4 py-2 bg-[#FC5200] text-white rounded-lg font-medium hover:bg-[#E64700] transition-colors"
                  >
                    Connect Strava
                  </button>
                </div>
              )}
            </div>

            {/* Additional Settings Sections */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h2 className="text-2xl font-semibold text-gray-900 mb-4">
                Account Management
              </h2>
              <div className="space-y-4">
                <div className="border-t border-gray-200 pt-4">
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    Export Your Data
                  </h3>
                  <p className="text-sm text-gray-600 mb-3">
                    Download all your SmartCoach data in JSON format.
                  </p>
                  <a
                    href="/data-usage"
                    className="text-sm text-blue-600 hover:underline"
                  >
                    Learn more about data export →
                  </a>
                </div>

                <div className="border-t border-gray-200 pt-4">
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    Delete Your Account
                  </h3>
                  <p className="text-sm text-gray-600 mb-3">
                    Permanently delete all your data from SmartCoach.
                  </p>
                  <a
                    href="mailto:support@smartcoach.app?subject=Data%20Deletion%20Request"
                    className="text-sm text-red-600 hover:underline"
                  >
                    Request account deletion →
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Layout>
    </AuthGuard>
  );
};

export default Settings;
