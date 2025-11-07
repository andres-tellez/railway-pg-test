import React from 'react';

const PrivacyPolicy: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-md p-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Privacy Policy</h1>
        <p className="text-sm text-gray-600 mb-8">Last Updated: October 15, 2025</p>

        <div className="space-y-6 text-gray-700">
          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">1. Introduction</h2>
            <p>
              Welcome to SmartCoach ("we," "our," or "us"). We are committed to protecting your privacy and personal data.
              This Privacy Policy explains how we collect, use, disclose, and safeguard your information when you use our
              running training application that integrates with Strava.
            </p>
            <p className="mt-2">
              By using SmartCoach, you agree to the collection and use of information in accordance with this policy.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">2. Information We Collect</h2>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">2.1 Information from Strava</h3>
            <p>When you connect your Strava account to SmartCoach, we collect:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Activity Data:</strong> Running activities including distance, pace, heart rate zones, elevation, and timestamps</li>
              <li><strong>Profile Information:</strong> Your Strava athlete ID, name, and profile picture</li>
              <li><strong>Performance Metrics:</strong> Heart rate data, pace information, and workout splits</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">2.2 Information You Provide</h3>
            <p>We also collect information you voluntarily provide:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Training Profile:</strong> Age, fitness level, training preferences, and race goals</li>
              <li><strong>Account Information:</strong> Email address and authentication credentials via Auth0</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">2.3 Automatically Collected Information</h3>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Usage Data:</strong> How you interact with SmartCoach features</li>
              <li><strong>Device Information:</strong> Browser type, IP address, and access times</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">3. How We Use Your Information</h2>
            <p>We use the collected information for the following purposes:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Performance Analysis:</strong> Analyzing your running metrics to provide insights and recommendations</li>
              <li><strong>Progress Tracking:</strong> Monitoring your training progress and performance</li>
              <li><strong>Service Improvement:</strong> Improving SmartCoach features and user experience</li>
              <li><strong>Authentication:</strong> Maintaining your account security</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">4. How We Share Your Information</h2>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">4.1 We Do NOT Share Your Data</h3>
            <p className="font-semibold">
              We do NOT sell, rent, or trade your personal data or Strava activity data to third parties.
            </p>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">4.2 Limited Sharing</h3>
            <p>We only share your information in the following limited circumstances:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Service Providers:</strong> We use OpenAI's GPT API for analysis and insights. Your data is used only as input and is not used to train AI models.</li>
              <li><strong>Authentication:</strong> Auth0 for secure account management</li>
              <li><strong>Legal Requirements:</strong> When required by law or to protect our rights</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">4.3 Powered by Strava</h3>
            <p>
              SmartCoach is powered by Strava. Your Strava data is accessed through the Strava API in accordance with
              <a href="https://www.strava.com/legal/privacy" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline"> Strava's Privacy Policy</a>.
              We do not display or share your Strava data with other SmartCoach users.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">5. Data Security</h2>
            <p>We implement appropriate technical and organizational security measures to protect your data:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Encryption:</strong> All data is transmitted over HTTPS with TLS encryption</li>
              <li><strong>Secure Storage:</strong> Data is stored in secure, encrypted databases</li>
              <li><strong>Access Controls:</strong> Strict authentication and authorization mechanisms</li>
              <li><strong>Regular Monitoring:</strong> Continuous security monitoring and updates</li>
            </ul>
            <p className="mt-2">
              However, no method of transmission over the internet is 100% secure. While we strive to use commercially
              acceptable means to protect your personal data, we cannot guarantee absolute security.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">6. Your Rights and Choices</h2>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">6.1 Access Your Data</h3>
            <p>You can access all your data stored in SmartCoach through your account dashboard.</p>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">6.2 Export Your Data</h3>
            <p>You can request an export of all your SmartCoach data by contacting us at <a href="mailto:support@smartcoach.app" className="text-blue-600 hover:underline">support@smartcoach.app</a>.</p>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">6.3 Disconnect Strava</h3>
            <p>You can disconnect your Strava account at any time by:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Visiting your Strava Settings → My Apps</li>
              <li>Revoking access to SmartCoach</li>
              <li>Or contacting us to disconnect your account</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">6.4 Delete Your Data</h3>
            <p className="font-semibold">You have the right to request deletion of all your data.</p>
            <p className="mt-2">To delete your account and all associated data:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Go to Account Settings → Delete Account</li>
              <li>Or email us at <a href="mailto:support@smartcoach.app" className="text-blue-600 hover:underline">support@smartcoach.app</a></li>
            </ul>
            <p className="mt-2">
              We will delete all your data within 48 hours of your request, including:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Strava activity data</li>
              <li>Training preferences</li>
              <li>Profile information</li>
              <li>Account credentials</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">7. Data Retention</h2>
            <p>
              We retain your data only as long as necessary to provide SmartCoach services:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Active Accounts:</strong> Data is retained while your account is active</li>
              <li><strong>Deleted Accounts:</strong> All data is permanently deleted within 48 hours of account deletion</li>
              <li><strong>Inactive Accounts:</strong> Accounts inactive for more than 2 years may be automatically deleted</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">8. Children's Privacy</h2>
            <p>
              SmartCoach is not intended for users under the age of 18. We do not knowingly collect personal information
              from children. If you believe we have inadvertently collected such information, please contact us immediately.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">9. GDPR Compliance (European Users)</h2>
            <p>
              If you are located in the European Economic Area (EEA) or United Kingdom, you have additional rights under
              the General Data Protection Regulation (GDPR):
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Right to Access:</strong> You can request a copy of your personal data</li>
              <li><strong>Right to Rectification:</strong> You can correct inaccurate data</li>
              <li><strong>Right to Erasure:</strong> You can request deletion of your data</li>
              <li><strong>Right to Restrict Processing:</strong> You can limit how we use your data</li>
              <li><strong>Right to Data Portability:</strong> You can receive your data in a machine-readable format</li>
              <li><strong>Right to Object:</strong> You can object to certain data processing</li>
              <li><strong>Right to Withdraw Consent:</strong> You can withdraw consent at any time</li>
            </ul>
            <p className="mt-2">
              To exercise these rights, contact us at <a href="mailto:support@smartcoach.app" className="text-blue-600 hover:underline">support@smartcoach.app</a>.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">10. Data Breach Notification</h2>
            <p>
              In the event of a data breach that affects your personal information, we will notify you and relevant
              authorities within 72 hours as required by GDPR and other applicable laws.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">11. Changes to This Privacy Policy</h2>
            <p>
              We may update this Privacy Policy from time to time. We will notify you of any changes by:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Posting the new Privacy Policy on this page</li>
              <li>Updating the "Last Updated" date</li>
              <li>Sending you an email notification for material changes</li>
            </ul>
            <p className="mt-2">
              Your continued use of SmartCoach after changes constitutes acceptance of the updated policy.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">12. Third-Party Services</h2>
            <p>SmartCoach integrates with the following third-party services:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><strong>Strava:</strong> <a href="https://www.strava.com/legal/privacy" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Strava Privacy Policy</a></li>
              <li><strong>Auth0:</strong> <a href="https://auth0.com/privacy" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Auth0 Privacy Policy</a></li>
              <li><strong>OpenAI:</strong> <a href="https://openai.com/privacy" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">OpenAI Privacy Policy</a></li>
            </ul>
            <p className="mt-2">
              We are not responsible for the privacy practices of these third-party services. We encourage you to review
              their privacy policies.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">13. Contact Us</h2>
            <p>If you have any questions about this Privacy Policy or our data practices, please contact us:</p>
            <div className="mt-3 bg-gray-50 p-4 rounded-md">
              <p><strong>Email:</strong> <a href="mailto:support@smartcoach.app" className="text-blue-600 hover:underline">support@smartcoach.app</a></p>
              <p className="mt-1"><strong>Response Time:</strong> We aim to respond within 48 hours</p>
            </div>
          </section>

          <section className="border-t pt-6 mt-8">
            <p className="text-sm text-gray-600">
              <strong>Powered by Strava:</strong> SmartCoach uses the Strava API to access your activity data.
              By using SmartCoach, you also agree to <a href="https://www.strava.com/legal/terms" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Strava's Terms of Service</a> and <a href="https://www.strava.com/legal/privacy" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Privacy Policy</a>.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default PrivacyPolicy;
