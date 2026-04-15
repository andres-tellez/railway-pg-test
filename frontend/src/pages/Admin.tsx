import React, { useState, useEffect, useMemo } from 'react';
import { useApiClient } from '../utils/apiClient';
import { useAuthSetup } from '../hooks/useAuthSetup';
import { AuthGuard } from '../components/AuthGuard';

interface Athlete {
  athlete_id: number;
  user_id: string;
  display_name: string;
  user_name?: string | null;
  email?: string | null;
}

interface SyncResult {
  status: string;
  result?: any;
  message?: string;
  athlete_id?: number;
  date_range?: string;
}

const Admin: React.FC = () => {
  const { isReady, userId } = useAuthSetup(); // ✅ Centralized auth
  const apiClient = useApiClient();
  const [athletes, setAthletes] = useState<Athlete[]>([]);
  const [selectedAthlete, setSelectedAthlete] = useState<number | ''>('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SyncResult | null>(null);
  const [refreshingMetrics, setRefreshingMetrics] = useState(false);
  const [refreshingWeeklyInsights, setRefreshingWeeklyInsights] = useState(false);
  const [migrating, setMigrating] = useState(false);
  const [migrationResult, setMigrationResult] = useState<any>(null);
  const [fullMigration, setFullMigration] = useState(false);
  const [testingPace, setTestingPace] = useState(false);
  const [paceResult, setPaceResult] = useState<any>(null);
  const [selectedUserId, setSelectedUserId] = useState<string>('');
  const [updatingPace, setUpdatingPace] = useState(false);
  const [updatePaceResult, setUpdatePaceResult] = useState<any>(null);
  const [selectedDeleteUserId, setSelectedDeleteUserId] = useState('');
  const [deleteUserAck, setDeleteUserAck] = useState(false);
  const [deletingUser, setDeletingUser] = useState(false);
  const [deleteUserResult, setDeleteUserResult] = useState<{
    success?: boolean;
    message?: string;
    deleted?: Record<string, number>;
    error?: string;
  } | null>(null);

  // Set default date range (last 7 days)
  useEffect(() => {
    const today = new Date();
    const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);

    setEndDate(today.toISOString().split('T')[0]);
    setStartDate(weekAgo.toISOString().split('T')[0]);
  }, []);

  // Load athletes on component mount
  useEffect(() => {
    if (!isReady || !userId) return; // ✅ Wait for auth setup

    const loadAthletes = async () => {
      try {
        const response = await apiClient.get('/admin/athletes');
        const athletesList = response.data.athletes || [];
        setAthletes(athletesList);
        // Set default selected user_id if available
        if (athletesList.length > 0 && !selectedUserId) {
          setSelectedUserId(athletesList[0].user_id);
        }
      } catch (error) {
        console.error('Failed to load athletes:', error);
        setResult({
          status: 'error',
          message: 'Failed to load athletes list'
        });
      }
    };

    loadAthletes();
  }, [isReady, userId, apiClient]); // ✅ Depend on auth setup

  const handleSync = async () => {
    if (!selectedAthlete || !startDate || !endDate) {
      setResult({
        status: 'error',
        message: 'Please select an athlete and date range'
      });
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const response = await apiClient.post('/admin/sync-activities', {
        athlete_id: selectedAthlete,
        start_date: startDate,
        end_date: endDate
      });

      setResult(response.data);
    } catch (error: any) {
      console.error('Sync failed:', error);
      setResult({
        status: 'error',
        message: error.response?.data?.message || 'Sync failed'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshMetrics = async () => {
    console.log('🔴 [BROWSER] Refresh Metrics button clicked!');
    setRefreshingMetrics(true);
    setResult(null);

    try {
      console.log('🔴 [BROWSER] Making POST request to /admin/refresh-metrics');
      const response = await apiClient.post('/admin/refresh-metrics');
      console.log('🔴 [BROWSER] Response received:', response.data);
      setResult(response.data);
    } catch (error: any) {
      console.error('Refresh metrics failed:', error);
      setResult({
        status: 'error',
        message: error.response?.data?.message || 'Metrics refresh failed'
      });
    } finally {
      setRefreshingMetrics(false);
    }
  };

  const handleRefreshWeeklyTrainingInsights = async () => {
    setRefreshingWeeklyInsights(true);
    setResult(null);

    try {
      const response = await apiClient.post('/admin/refresh-weekly-training-insights');
      setResult(response.data);
    } catch (error: any) {
      console.error('Weekly training insights refresh failed:', error);
      setResult({
        status: 'error',
        message:
          error.response?.data?.message || 'Weekly training insights refresh failed',
      });
    } finally {
      setRefreshingWeeklyInsights(false);
    }
  };

  const handleMigrateProdToLocal = async () => {
    setMigrating(true);
    setMigrationResult(null);

    try {
      const response = await apiClient.post('/admin/migrate-prod-to-local', {
        full: fullMigration
      });
      setMigrationResult(response.data);
    } catch (error: any) {
      console.error('Migration failed:', error);
      setMigrationResult({
        status: 'error',
        message: error.response?.data?.message || 'Migration failed',
        error: error.response?.data
      });
    } finally {
      setMigrating(false);
    }
  };

  const handleTestPaceCalculation = async () => {
    if (!selectedUserId) {
      setPaceResult({
        status: 'error',
        message: 'Please select a user'
      });
      return;
    }

    setTestingPace(true);
    setPaceResult(null);

    try {
      const response = await apiClient.post('/admin/test-pace-calculation', {
        user_id: selectedUserId,
        lookback_weeks: 6,
        week1_long: 8.0
      });
      setPaceResult(response.data);
    } catch (error: any) {
      console.error('Pace calculation test failed:', error);
      setPaceResult({
        status: 'error',
        message: error.response?.data?.message || 'Pace calculation test failed',
        error: error.response?.data
      });
    } finally {
      setTestingPace(false);
    }
  };

  const athleteOptionLabel = (a: Athlete) =>
    `${a.display_name} — athlete ${a.athlete_id}`;

  const athletesUniqueByUserId = useMemo(() => {
    const seen = new Set<string>();
    const out: Athlete[] = [];
    for (const a of athletes) {
      if (seen.has(a.user_id)) continue;
      seen.add(a.user_id);
      out.push(a);
    }
    return out;
  }, [athletes]);

  const handleAdminDeleteUser = async () => {
    if (!selectedDeleteUserId) {
      setDeleteUserResult({
        success: false,
        error: 'Select a user to delete',
      });
      return;
    }
    if (!deleteUserAck) {
      setDeleteUserResult({
        success: false,
        error: 'Confirm that you understand this action is permanent.',
      });
      return;
    }

    setDeletingUser(true);
    setDeleteUserResult(null);

    try {
      const response = await apiClient.post('/admin/delete-user', {
        user_id: selectedDeleteUserId,
        confirm: true,
      });
      setDeleteUserResult({
        success: true,
        message: response.data.message,
        deleted: response.data.deleted,
      });
      setSelectedDeleteUserId('');
      setDeleteUserAck(false);
      const reload = await apiClient.get('/admin/athletes');
      setAthletes(reload.data.athletes || []);
    } catch (error: any) {
      const msg =
        error.response?.data?.error ||
        error.response?.data?.message ||
        'Delete failed';
      setDeleteUserResult({
        success: false,
        error: msg,
      });
    } finally {
      setDeletingUser(false);
    }
  };

  const handleUpdateCurrentWeekPace = async () => {
    if (!selectedUserId) {
      setUpdatePaceResult({
        status: 'error',
        message: 'Please select a user'
      });
      return;
    }

    setUpdatingPace(true);
    setUpdatePaceResult(null);

    try {
      const response = await apiClient.post('/admin/update-current-week-pace', {
        user_id: selectedUserId,
        lookback_weeks: 6
      });
      setUpdatePaceResult(response.data);
    } catch (error: any) {
      console.error('Update current week pace failed:', error);
      setUpdatePaceResult({
        status: 'error',
        message: error.response?.data?.message || 'Update current week pace failed',
        error: error.response?.data
      });
    } finally {
      setUpdatingPace(false);
    }
  };

  return (
    <AuthGuard>
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-2xl mx-auto px-4">
        <div className="bg-white rounded-lg shadow p-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-6">Admin Tools</h1>

          {/* Delete user account (admin) */}
          <div className="mb-8 p-4 bg-red-50 rounded-lg border border-red-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Delete user account</h2>
            <p className="text-sm text-gray-600 mb-3">
              Permanently removes the selected user&apos;s identity, profile, Strava link, tokens,
              activities, plans, and related rows. Only the account linked to Strava athlete{' '}
              <code className="text-xs bg-red-100 px-1 rounded">347085</code> may use this tool. You
              cannot delete your own account here; use the GDPR / account deletion flow instead.
            </p>
            <div className="mb-3">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select user
              </label>
              <select
                value={selectedDeleteUserId}
                onChange={(e) => setSelectedDeleteUserId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-red-500"
              >
                <option value="">Choose a user...</option>
                {athletesUniqueByUserId.map((athlete) => (
                  <option key={athlete.user_id} value={athlete.user_id}>
                    {athleteOptionLabel(athlete)}
                  </option>
                ))}
              </select>
            </div>
            <label className="flex items-start gap-2 mb-3 text-sm text-gray-800">
              <input
                type="checkbox"
                checked={deleteUserAck}
                onChange={(e) => setDeleteUserAck(e.target.checked)}
                className="mt-1 rounded border-gray-300"
                disabled={deletingUser}
              />
              <span>I understand this permanently deletes the user and cannot be undone.</span>
            </label>
            <button
              type="button"
              onClick={handleAdminDeleteUser}
              disabled={deletingUser || !selectedDeleteUserId || !deleteUserAck}
              className="bg-red-700 text-white py-2 px-4 rounded-md hover:bg-red-800 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {deletingUser ? 'Deleting…' : 'Delete user permanently'}
            </button>
            {deleteUserResult && (
              <div
                className={`mt-4 p-3 rounded-md text-sm ${
                  deleteUserResult.success
                    ? 'bg-green-50 border border-green-200 text-green-900'
                    : 'bg-red-50 border border-red-200 text-red-900'
                }`}
              >
                {deleteUserResult.success ? (
                  <>
                    <p className="font-medium">User deleted</p>
                    {deleteUserResult.message && <p className="mt-1">{deleteUserResult.message}</p>}
                    {deleteUserResult.deleted && (
                      <pre className="mt-2 text-xs bg-white/80 p-2 rounded overflow-auto max-h-40">
                        {JSON.stringify(deleteUserResult.deleted, null, 2)}
                      </pre>
                    )}
                  </>
                ) : (
                  <p>{deleteUserResult.error}</p>
                )}
              </div>
            )}
          </div>

          {/* Database Migration Section */}
          <div className="mb-8 p-4 bg-purple-50 rounded-lg border border-purple-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Database Migration</h2>
            <p className="text-sm text-gray-600 mb-3">
              <strong>What this does:</strong> This tool copies data from your production database (main Strava account)
              to your local development database (test Strava account). It automatically maps all user IDs, athlete IDs,
              and other identifiers to work with your local test account.
            </p>
            <div className="mb-3 p-3 bg-purple-100 rounded border border-purple-300">
              <p className="text-xs text-gray-700 mb-2">
                <strong>Data copied:</strong>
              </p>
              <ul className="text-xs text-gray-600 list-disc list-inside space-y-1">
                <li>User profile, identity, and athlete links</li>
                <li>All Strava activities and splits</li>
                <li>Training plans and workouts</li>
                <li>Weekly metrics and decision logs</li>
                <li>Conversations and sync status</li>
              </ul>
            </div>
            <div className="mb-3 flex items-center gap-2">
              <input
                type="checkbox"
                id="fullMigration"
                checked={fullMigration}
                onChange={(e) => setFullMigration(e.target.checked)}
                className="rounded border-gray-300"
                disabled={migrating}
              />
              <label htmlFor="fullMigration" className="text-sm text-gray-700">
                Force full migration (ignore last migration timestamp)
              </label>
            </div>
            <button
              onClick={handleMigrateProdToLocal}
              disabled={migrating}
              className="bg-purple-600 text-white py-2 px-4 rounded-md hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {migrating ? 'Migrating...' : '🔄 Migrate Production → Local'}
            </button>

            {migrationResult && (
              <div className={`mt-4 p-3 rounded-md ${
                migrationResult.status === 'success'
                  ? 'bg-green-50 border border-green-200'
                  : migrationResult.status === 'partial'
                  ? 'bg-yellow-50 border border-yellow-200'
                  : 'bg-red-50 border border-red-200'
              }`}>
                <h3 className={`font-medium text-sm ${
                  migrationResult.status === 'success' ? 'text-green-800'
                  : migrationResult.status === 'partial' ? 'text-yellow-800'
                  : 'text-red-800'
                }`}>
                  {migrationResult.status === 'success' ? '✅ Migration Successful'
                   : migrationResult.status === 'partial' ? '⚠️ Migration Partially Successful'
                   : '❌ Migration Failed'}
                </h3>
                {migrationResult.message && (
                  <p className={`mt-1 text-xs ${
                    migrationResult.status === 'success' ? 'text-green-700'
                    : migrationResult.status === 'partial' ? 'text-yellow-700'
                    : 'text-red-700'
                  }`}>
                    {migrationResult.message}
                  </p>
                )}
                {migrationResult.results && (
                  <details className="mt-2">
                    <summary className="text-xs text-gray-600 cursor-pointer">Show details</summary>
                    <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto">
                      {JSON.stringify(migrationResult.results, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            )}
          </div>

          {/* Test Pace Calculation Section */}
          <div className="mb-8 p-4 bg-indigo-50 rounded-lg border border-indigo-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Test Pace Calculation</h2>
            <p className="text-sm text-gray-600 mb-3">
              Test the new performance-based pace calculation. Select a user to calculate their training pace zones.
            </p>
            <div className="mb-3">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select User
              </label>
              <select
                value={selectedUserId}
                onChange={(e) => setSelectedUserId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">Choose a user...</option>
                {athletes.map((athlete) => (
                  <option
                    key={`${athlete.user_id}-${athlete.athlete_id}`}
                    value={athlete.user_id}
                  >
                    {athleteOptionLabel(athlete)}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleTestPaceCalculation}
                disabled={testingPace || !selectedUserId}
                className="bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {testingPace ? 'Calculating...' : '🧪 Test Pace Calculation'}
              </button>
              <button
                onClick={handleUpdateCurrentWeekPace}
                disabled={updatingPace || !selectedUserId}
                className="bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {updatingPace ? 'Updating...' : '🔄 Update Current Week Pace'}
              </button>
            </div>

            {paceResult && (
              <div className={`mt-4 p-4 rounded-md ${
                paceResult.status === 'success'
                  ? 'bg-green-50 border border-green-200'
                  : 'bg-red-50 border border-red-200'
              }`}>
                <h3 className={`font-medium text-sm mb-2 ${
                  paceResult.status === 'success' ? 'text-green-800' : 'text-red-800'
                }`}>
                  {paceResult.status === 'success' ? '✅ Calculation Successful' : '❌ Calculation Failed'}
                </h3>
                {paceResult.status === 'success' && (
                  <div className="space-y-2 text-sm">
                    <div>
                      <span className="font-semibold text-gray-700">Method: </span>
                      <span className={`px-2 py-1 rounded text-xs ${
                        paceResult.calculation_method === 'Performance-Based'
                          ? 'bg-green-100 text-green-800'
                          : paceResult.calculation_method === 'Performance'
                          ? 'bg-green-100 text-green-800'
                          : 'bg-yellow-100 text-yellow-800'
                      }`}>
                        {paceResult.calculation_method}
                      </span>
                    </div>
                    {paceResult.lookback_weeks !== undefined && (
                      <div>
                        <span className="font-semibold text-gray-700">Lookback Weeks: </span>
                        <span className="text-gray-600">{paceResult.lookback_weeks}</span>
                      </div>
                    )}
                    <div className="mt-3 pt-3 border-t border-gray-200">
                      <h4 className="font-semibold text-gray-700 mb-2">Pace Zones:</h4>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="font-medium">Easy:</span>{' '}
                          {paceResult.pace_zones?.Easy?.min} - {paceResult.pace_zones?.Easy?.max}
                        </div>
                        <div>
                          <span className="font-medium">Steady:</span>{' '}
                          {paceResult.pace_zones?.Steady?.min} - {paceResult.pace_zones?.Steady?.max}
                        </div>
                        <div>
                          <span className="font-medium">Marathon:</span>{' '}
                          {paceResult.pace_zones?.Marathon?.pace}
                        </div>
                        <div>
                          <span className="font-medium">Threshold:</span>{' '}
                          {paceResult.pace_zones?.Threshold?.min} - {paceResult.pace_zones?.Threshold?.max}
                        </div>
                      </div>
                    </div>
                    <div className="mt-2">
                      <span className="font-semibold text-gray-700">Week 1 Long Cap: </span>
                      <span className="text-gray-600">{paceResult.week1_long_cap} miles</span>
                    </div>
                  </div>
                )}
                {paceResult.status === 'error' && (
                  <p className="text-sm text-red-700">{paceResult.message}</p>
                )}
                <details className="mt-2">
                  <summary className="text-xs text-gray-600 cursor-pointer">Show raw data</summary>
                  <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto max-h-64">
                    {JSON.stringify(paceResult, null, 2)}
                  </pre>
                </details>
              </div>
            )}
          </div>

          {/* Update Current Week Pace Result */}
          {updatePaceResult && (
            <div className={`mb-8 p-4 rounded-lg border ${
              updatePaceResult?.status === 'success'
                ? 'bg-green-50 border-green-200'
                : 'bg-red-50 border-red-200'
            }`}>
              <h3 className={`font-medium text-lg mb-2 ${
                updatePaceResult?.status === 'success' ? 'text-green-800' : 'text-red-800'
              }`}>
                {updatePaceResult?.status === 'success' ? '✅ Week Updated Successfully' : '❌ Update Failed'}
              </h3>
              {updatePaceResult?.status === 'success' && (
                <div className="space-y-2 text-sm">
                  {updatePaceResult.plan_id !== undefined && (
                    <div>
                      <span className="font-semibold text-gray-700">Plan ID: </span>
                      <span className="text-gray-600">{updatePaceResult.plan_id}</span>
                    </div>
                  )}
                  {updatePaceResult.week_num !== undefined && (
                    <div>
                      <span className="font-semibold text-gray-700">Week Number: </span>
                      <span className="text-gray-600">{updatePaceResult.week_num}</span>
                    </div>
                  )}
                  {updatePaceResult.lookback_weeks !== undefined && (
                    <div>
                      <span className="font-semibold text-gray-700">Lookback Weeks: </span>
                      <span className="text-gray-600">{updatePaceResult.lookback_weeks}</span>
                    </div>
                  )}
                  {updatePaceResult.pace_zones && (
                    <div className="mt-3 pt-3 border-t border-gray-200">
                      <h4 className="font-semibold text-gray-700 mb-2">New Pace Zones:</h4>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        {updatePaceResult.pace_zones.Easy && (
                          <div>
                            <span className="font-medium">Easy:</span>{' '}
                            {updatePaceResult.pace_zones.Easy.min || 'N/A'} - {updatePaceResult.pace_zones.Easy.max || 'N/A'}
                          </div>
                        )}
                        {updatePaceResult.pace_zones.Steady && (
                          <div>
                            <span className="font-medium">Steady:</span>{' '}
                            {updatePaceResult.pace_zones.Steady.min || 'N/A'} - {updatePaceResult.pace_zones.Steady.max || 'N/A'}
                          </div>
                        )}
                        {updatePaceResult.pace_zones.Marathon && (
                          <div>
                            <span className="font-medium">Marathon:</span>{' '}
                            {updatePaceResult.pace_zones.Marathon.pace || 'N/A'}
                          </div>
                        )}
                        {updatePaceResult.pace_zones.Threshold && (
                          <div>
                            <span className="font-medium">Threshold:</span>{' '}
                            {updatePaceResult.pace_zones.Threshold.min || 'N/A'} - {updatePaceResult.pace_zones.Threshold.max || 'N/A'}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  {updatePaceResult.rebuild_result && (
                    <div className="mt-2">
                      <span className="font-semibold text-gray-700">Workouts Updated: </span>
                      <span className="text-gray-600">
                        {updatePaceResult.rebuild_result.updated_workouts ?? 0}
                      </span>
                    </div>
                  )}
                </div>
              )}
              {updatePaceResult?.status === 'error' && (
                <p className="text-sm text-red-700">{updatePaceResult?.message || 'An error occurred'}</p>
              )}
              <details className="mt-2">
                <summary className="text-xs text-gray-600 cursor-pointer">Show raw data</summary>
                <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto max-h-64">
                  {JSON.stringify(updatePaceResult, null, 2)}
                </pre>
              </details>
            </div>
          )}

          {/* Refresh Metrics Section */}
          <div className="mb-8 p-4 bg-blue-50 rounded-lg border border-blue-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Metrics Refresh</h2>
            <p className="text-sm text-gray-600 mb-3">
              Manually trigger the metrics refresh to update bar graphs with the latest week's data.
            </p>
            <button
              onClick={handleRefreshMetrics}
              disabled={refreshingMetrics}
              className="bg-green-600 text-white py-2 px-4 rounded-md hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {refreshingMetrics ? 'Refreshing Metrics...' : '🔄 Refresh Metrics'}
            </button>
          </div>

          <div className="mb-8 p-4 bg-indigo-50 rounded-lg border border-indigo-200">
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Weekly training insights</h2>
            <p className="text-sm text-gray-600 mb-3">
              Recomputes rows in <code className="text-xs bg-indigo-100 px-1 rounded">weekly_training_insights</code>{' '}
              so the mobile app&apos;s <strong>Insights</strong> tab (and{' '}
              <code className="text-xs bg-indigo-100 px-1 rounded">/api/training-insights/weekly</code>) show up-to-date
              scores. Runs <strong>six completed</strong> Mon–Sun weeks (oldest → newest, same span as post–Strava
              ingestion backfill), then the <strong>current calendar week</strong> as an in-progress snapshot (Mon
              through today). Only users with easy runs in each window are processed.
            </p>
            <p className="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-3">
              <strong>Runtime:</strong> each (week × user) pair runs a full insight recomputation against the database.
              Active users can trigger <em>many</em> sequential jobs in one request (six historical passes plus current
              week), so this can take tens of seconds or longer. Keep the browser tab open until it finishes. If you
              see a gateway timeout (502/504), raise the reverse-proxy or app server HTTP timeout, or run the same logic
              from a shell / scheduled job instead of this button.
            </p>
            <button
              onClick={handleRefreshWeeklyTrainingInsights}
              disabled={refreshingWeeklyInsights}
              className="bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {refreshingWeeklyInsights ? 'Refreshing insights…' : '📊 Refresh weekly training insights'}
            </button>
          </div>

          <h2 className="text-xl font-semibold text-gray-900 mb-4">Activity Sync Admin</h2>

          <div className="space-y-4">
            {/* Athlete Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Athlete
              </label>
              <select
                value={selectedAthlete}
                onChange={(e) => setSelectedAthlete(e.target.value ? Number(e.target.value) : '')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Choose an athlete...</option>
                {athletes.map((athlete) => (
                  <option key={athlete.athlete_id} value={athlete.athlete_id}>
                    {athleteOptionLabel(athlete)}
                  </option>
                ))}
              </select>
            </div>

            {/* Date Range */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Start Date
                </label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  End Date
                </label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            {/* Sync Button */}
            <button
              onClick={handleSync}
              disabled={loading || !selectedAthlete || !startDate || !endDate}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
            >
              {loading ? 'Syncing...' : 'Download & Enrich Activities'}
            </button>

            {/* Results */}
            {result && (() => {
              const st = (result as { status?: string }).status;
              const ok = st === 'success' || st === 'partial';
              const partial = st === 'partial';
              const weeklyPayload =
                'six_completed_weeks' in (result as object) ||
                'current_week_in_progress' in (result as object);
              return (
              <div className={`p-4 rounded-md ${
                ok
                  ? partial
                    ? 'bg-amber-50 border border-amber-200'
                    : 'bg-green-50 border border-green-200'
                  : 'bg-red-50 border border-red-200'
              }`}>
                <h3 className={`font-medium ${
                  ok ? (partial ? 'text-amber-900' : 'text-green-800') : 'text-red-800'
                }`}>
                  {ok
                    ? partial
                      ? 'Completed with warnings'
                      : 'Sync Successful'
                    : 'Sync Failed'}
                </h3>
                {result.message && (
                  <p className={`mt-1 text-sm ${
                    ok ? (partial ? 'text-amber-800' : 'text-green-700') : 'text-red-700'
                  }`}>
                    {result.message}
                  </p>
                )}
                {weeklyPayload && (
                  <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto max-h-96">
                    {JSON.stringify(result, null, 2)}
                  </pre>
                )}
                {result.result && (
                  <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-auto">
                    {JSON.stringify(result.result, null, 2)}
                  </pre>
                )}
              </div>
              );
            })()}
          </div>
        </div>
      </div>
    </div>
    </AuthGuard>
  );
};

export default Admin;
