import React from 'react';

const DataUsage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-md p-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Data Usage & Retention</h1>
        <p className="text-sm text-gray-600 mb-8">Last Updated: November 3, 2025</p>

        <div className="space-y-6 text-gray-700">
          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">1. What Data We Collect</h2>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">1.1 Strava Activity Data</h3>
            <p>
              When you connect your Strava account, we collect and store your running activity data:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Activity Details:</strong> Distance, pace, elapsed time, moving time, elevation gain, start date and time</li>
              <li><strong>Performance Metrics:</strong> Average and maximum heart rate, heart rate zones, average and maximum speed, calories burned</li>
              <li><strong>Workout Data:</strong> Per-mile splits, heart rate zones per mile, GPS streams (when available)</li>
              <li><strong>Activity Metadata:</strong> Activity name, type, timezone, and external identifiers</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">1.2 Profile Information</h3>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Strava Profile:</strong> Your Strava athlete ID, name, and profile picture URL</li>
              <li><strong>Account Information:</strong> Email address (via Auth0 authentication)</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">1.3 Training Profile Data</h3>
            <p>Information you provide during onboarding:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Demographics:</strong> Age group, fitness level</li>
              <li><strong>Training Preferences:</strong> Available training days, preferred workout types</li>
              <li><strong>Goals:</strong> Race dates, target distances, performance goals</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">1.4 Generated Training Plans</h3>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Training Plans:</strong> Weekly workout schedules with distances, paces, and target heart rate zones</li>
              <li><strong>Workout Details:</strong> Detailed segment breakdowns (warm-up, intervals, rest periods, cooldown) for each workout</li>
              <li><strong>Adaptive Adjustments:</strong> Historical records of how your plan was adjusted based on performance</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">2. Why We Collect This Data</h2>
            <p>We use your data exclusively to provide personalized training plan services:</p>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">2.1 Training Plan Generation</h3>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Analyze your historical running performance to establish baseline fitness levels</li>
              <li>Calculate appropriate training paces based on your actual performance data</li>
              <li>Generate personalized weekly training schedules that match your goals and availability</li>
              <li>Create detailed workout structures with specific distances, paces, and heart rate targets</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">2.2 Adaptive Training Adjustments</h3>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Compare your actual workout performance to planned workouts</li>
              <li>Adjust future training plans based on your performance trends</li>
              <li>Adapt training intensity and volume to match your current fitness level</li>
              <li>Ensure training plans remain challenging but realistic</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">2.3 Progress Tracking & Analytics</h3>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Display your training metrics and progress over time</li>
              <li>Show weekly mileage, pace trends, and heart rate zone distribution</li>
              <li>Provide insights into your training consistency and performance improvements</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">2.4 Service Improvement</h3>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Improve our training plan algorithms based on usage patterns (anonymized)</li>
              <li>Fix bugs and enhance user experience</li>
              <li>Ensure system reliability and performance</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">3. Data Retention</h2>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">3.1 How Long We Keep Your Data</h3>
            <p>
              We retain your data as long as your account is active. This is necessary for:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Historical Analysis:</strong> We analyze up to 12 weeks of your running history to generate accurate training plans</li>
              <li><strong>Progress Tracking:</strong> Maintaining your training history allows you to see long-term progress and trends</li>
              <li><strong>Plan Adaptation:</strong> We compare your current week's performance to previous weeks to adjust future training</li>
              <li><strong>User Experience:</strong> Your data is stored as your primary training record, not as a temporary cache</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">3.2 Data Deletion</h3>
            <p>
              You can request deletion of your data at any time:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Delete your account and all associated data via our <a href="/data-deletion" className="text-blue-600 hover:underline">Data Deletion page</a></li>
              <li>All data is permanently deleted within 48 hours of your request</li>
              <li>Deletion is immediate and irreversible</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">3.3 Account Inactivity</h3>
            <p>
              If your account remains inactive for an extended period, we may archive or delete your data.
              We will notify you via email before taking any action.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">4. Data Storage & Security</h2>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">4.1 Where Your Data is Stored</h3>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Primary Database:</strong> Your data is stored in a secure PostgreSQL database hosted on Railway</li>
              <li><strong>Encryption:</strong> All data is transmitted over HTTPS with TLS encryption</li>
              <li><strong>Access Control:</strong> Data is only accessible to you and our system administrators for service maintenance</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">4.2 Data Sharing</h3>
            <p className="font-semibold mb-2">
              We do NOT sell, rent, or trade your personal data or Strava activity data to third parties.
            </p>
            <p>We only share data in limited circumstances:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Service Providers:</strong> We use OpenAI's GPT API for analysis. Your data is used only as input and is not used to train AI models.</li>
              <li><strong>Authentication:</strong> Auth0 for secure account management</li>
              <li><strong>Legal Requirements:</strong> When required by law or to protect our rights</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">5. Your Rights</h2>
            <p>You have full control over your data:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Access:</strong> View all your data via our application or request a data export</li>
              <li><strong>Export:</strong> Request a copy of all your data at any time via our <a href="/api/user/export-data" className="text-blue-600 hover:underline">Data Export endpoint</a></li>
              <li><strong>Delete:</strong> Permanently delete your account and all data via our <a href="/data-deletion" className="text-blue-600 hover:underline">Data Deletion page</a></li>
              <li><strong>Disconnect Strava:</strong> Disconnect your Strava account at any time (we will stop syncing new data, but existing data remains unless you delete your account)</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">6. Contact Us</h2>
            <p>
              If you have questions about how we use your data or wish to exercise your rights, please contact us:
            </p>
            <p className="mt-2">
              Email: <a href="mailto:support@smartcoach.app" className="text-blue-600 hover:underline">support@smartcoach.app</a>
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">7. Related Policies</h2>
            <p>
              For more information, please review our:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><a href="/privacy-policy" className="text-blue-600 hover:underline">Privacy Policy</a></li>
              <li><a href="/terms-of-service" className="text-blue-600 hover:underline">Terms of Service</a></li>
              <li><a href="/data-deletion" className="text-blue-600 hover:underline">Data Deletion Instructions</a></li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
};

export default DataUsage;
