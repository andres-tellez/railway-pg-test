import React from 'react';
import { AuthGuard } from '@/components/AuthGuard';
import ActivityExport from '@/components/ActivityExport';

const Settings: React.FC = () => {
  return (
    <AuthGuard>
      <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold text-gray-900 mb-8">Settings</h1>

          {/* Activity Export */}
          <div className="bg-white rounded-lg shadow-md p-6 mb-6">
            <ActivityExport />
          </div>

          {/* Account & Data Management */}
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
                    href="/data-deletion"
                    className="text-sm text-red-600 hover:underline"
                  >
                    Learn more about account deletion →
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
    </AuthGuard>
  );
};

export default Settings;
