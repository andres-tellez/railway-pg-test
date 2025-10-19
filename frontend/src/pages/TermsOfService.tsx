import React from 'react';

const TermsOfService: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto bg-white rounded-lg shadow-md p-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">Terms of Service</h1>
        <p className="text-sm text-gray-600 mb-8">Last Updated: October 15, 2025</p>

        <div className="space-y-6 text-gray-700">
          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">1. Acceptance of Terms</h2>
            <p>
              Welcome to SmartCoach! By accessing or using our running training application ("Service"), you agree to be
              bound by these Terms of Service ("Terms"). If you do not agree to these Terms, please do not use SmartCoach.
            </p>
            <p className="mt-2">
              These Terms apply to all users of the Service, including those who connect their Strava accounts.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">2. Description of Service</h2>
            <p>
              SmartCoach is a personalized running training application that:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Integrates with Strava to analyze your running activities</li>
              <li>Provides performance metrics and training insights</li>
              <li>Tracks your progress toward race goals</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">3. User Accounts and Registration</h2>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">3.1 Account Creation</h3>
            <p>
              To use SmartCoach, you must:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Be at least 18 years of age</li>
              <li>Create an account via Auth0 authentication</li>
              <li>Connect your Strava account</li>
              <li>Provide accurate and complete information</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">3.2 Account Security</h3>
            <p>
              You are responsible for maintaining the confidentiality of your account credentials and for all activities
              that occur under your account. You agree to immediately notify us of any unauthorized use of your account.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">4. Strava Integration</h2>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">4.1 Powered by Strava</h3>
            <p>
              SmartCoach is powered by Strava and accesses your Strava data through the Strava API. By using SmartCoach,
              you also agree to:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li><a href="https://www.strava.com/legal/terms" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Strava's Terms of Service</a></li>
              <li><a href="https://www.strava.com/legal/privacy" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Strava's Privacy Policy</a></li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">4.2 Data Authorization</h3>
            <p>
              When you connect your Strava account, you authorize SmartCoach to:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Access your running activity data (distance, pace, heart rate, elevation)</li>
              <li>Read your profile information</li>
              <li>Analyze your performance metrics</li>
            </ul>
            <p className="mt-2">
              You can revoke this authorization at any time through your Strava account settings or by contacting us.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">5. Use of the Service</h2>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">5.1 Permitted Use</h3>
            <p>You agree to use SmartCoach only for lawful purposes and in accordance with these Terms.</p>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">5.2 Prohibited Conduct</h3>
            <p>You agree NOT to:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Use the Service for any illegal or unauthorized purpose</li>
              <li>Attempt to gain unauthorized access to the Service or related systems</li>
              <li>Reverse engineer, decompile, or disassemble any part of the Service</li>
              <li>Use automated systems (bots, scrapers) to access the Service</li>
              <li>Interfere with or disrupt the Service or servers</li>
              <li>Impersonate another person or misrepresent your affiliation</li>
              <li>Upload viruses or malicious code</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">6. Training Plans and Medical Disclaimer</h2>

            <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-4">
              <p className="font-semibold text-yellow-800">⚠️ IMPORTANT MEDICAL DISCLAIMER</p>
            </div>

            <p className="font-semibold">
              SmartCoach is NOT a substitute for professional medical or coaching advice.
            </p>

            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Training plans are generated based on algorithmic analysis and AI, not by certified coaches</li>
              <li>Always consult with a healthcare provider before starting any new training program</li>
              <li>Stop exercising immediately if you experience pain, dizziness, or discomfort</li>
              <li>You assume all risks associated with following SmartCoach training recommendations</li>
              <li>We are not liable for any injuries, health issues, or damages resulting from your use of the Service</li>
            </ul>

            <p className="mt-3 font-semibold">
              Use SmartCoach at your own risk. Listen to your body and seek professional guidance when needed.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">7. Intellectual Property</h2>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">7.1 SmartCoach Content</h3>
            <p>
              All content, features, and functionality of SmartCoach (including but not limited to text, graphics, logos,
              software, and design) are owned by SmartCoach or its licensors and are protected by copyright, trademark,
              and other intellectual property laws.
            </p>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">7.2 Your Data</h3>
            <p>
              You retain all rights to your personal data and Strava activity data. By using SmartCoach, you grant us a
              limited license to use your data solely to provide and improve the Service.
            </p>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">7.3 Strava Marks</h3>
            <p>
              Strava trademarks, logos, and service marks displayed in SmartCoach are the property of Strava, Inc.
              These marks may not be used without prior written permission from Strava.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">8. Privacy and Data Protection</h2>
            <p>
              Your privacy is important to us. Please review our <a href="/privacy-policy" className="text-blue-600 hover:underline">Privacy Policy</a> to
              understand how we collect, use, and protect your personal data.
            </p>
            <p className="mt-2">Key points:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>We do NOT sell your data to third parties</li>
              <li>Your Strava data is only visible to you</li>
              <li>You can export or delete your data at any time</li>
              <li>We comply with GDPR and other privacy regulations</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">9. Service Availability and Modifications</h2>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">9.1 Service Availability</h3>
            <p>
              We strive to provide reliable service, but we do not guarantee that SmartCoach will be:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Always available or uninterrupted</li>
              <li>Free of errors or bugs</li>
              <li>Secure from unauthorized access</li>
              <li>Compatible with all devices or browsers</li>
            </ul>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">9.2 Modifications</h3>
            <p>
              We reserve the right to modify, suspend, or discontinue SmartCoach (or any part thereof) at any time with
              or without notice. We will not be liable for any modification, suspension, or discontinuation.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">10. Fees and Payment</h2>
            <p>
              SmartCoach is currently provided free of charge. We reserve the right to introduce fees in the future.
              If we do, we will provide advance notice and you will have the option to continue or discontinue use.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">11. Termination</h2>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">11.1 Termination by You</h3>
            <p>
              You may terminate your account at any time by:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Using the "Delete Account" feature in your account settings</li>
              <li>Emailing us at support@smartcoach.app</li>
            </ul>
            <p className="mt-2">
              Upon termination, all your data will be permanently deleted within 48 hours.
            </p>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">11.2 Termination by Us</h3>
            <p>
              We may suspend or terminate your access to SmartCoach immediately, without notice, if:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>You violate these Terms</li>
              <li>Your use poses a security risk</li>
              <li>Required by law or Strava</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">12. Disclaimers and Warranties</h2>

            <div className="bg-gray-100 p-4 rounded-md uppercase font-semibold text-sm">
              <p>SMARTCOACH IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EXPRESS OR IMPLIED.</p>
            </div>

            <p className="mt-3">We disclaim all warranties, including but not limited to:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Implied warranties of merchantability, fitness for a particular purpose, and non-infringement</li>
              <li>Warranties that the Service will be error-free, secure, or uninterrupted</li>
              <li>Warranties regarding the accuracy, reliability, or completeness of data or recommendations</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">13. Limitation of Liability</h2>

            <div className="bg-gray-100 p-4 rounded-md uppercase font-semibold text-sm">
              <p>
                TO THE MAXIMUM EXTENT PERMITTED BY LAW, SMARTCOACH SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL,
                SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS OR REVENUES, WHETHER INCURRED
                DIRECTLY OR INDIRECTLY, OR ANY LOSS OF DATA, USE, GOODWILL, OR OTHER INTANGIBLE LOSSES.
              </p>
            </div>

            <p className="mt-3">This includes, but is not limited to, damages arising from:</p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Your use or inability to use the Service</li>
              <li>Training injuries or health issues</li>
              <li>Unauthorized access to your data</li>
              <li>Errors or omissions in recommendations</li>
              <li>Third-party services (Strava, Auth0, OpenAI)</li>
            </ul>

            <p className="mt-3">
              OUR TOTAL LIABILITY SHALL NOT EXCEED $100 USD OR THE AMOUNT YOU PAID US IN THE PAST 12 MONTHS,
              WHICHEVER IS GREATER.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">14. Indemnification</h2>
            <p>
              You agree to indemnify, defend, and hold harmless SmartCoach, its officers, directors, employees, and agents
              from any claims, liabilities, damages, losses, and expenses (including reasonable attorneys' fees) arising
              from:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>Your use or misuse of the Service</li>
              <li>Your violation of these Terms</li>
              <li>Your violation of any third-party rights</li>
              <li>Any injuries or damages resulting from following recommendations</li>
            </ul>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">15. Governing Law and Disputes</h2>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">15.1 Governing Law</h3>
            <p>
              These Terms shall be governed by and construed in accordance with the laws of the State of California,
              United States, without regard to its conflict of law provisions.
            </p>

            <h3 className="text-xl font-semibold text-gray-800 mb-2 mt-4">15.2 Dispute Resolution</h3>
            <p>
              Any disputes arising from these Terms or your use of SmartCoach shall be resolved through binding arbitration,
              except that you may assert claims in small claims court if they qualify.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">16. Changes to Terms</h2>
            <p>
              We may update these Terms from time to time. When we do:
            </p>
            <ul className="list-disc pl-6 mt-2 space-y-1">
              <li>We will post the updated Terms with a new "Last Updated" date</li>
              <li>We will notify you via email for material changes</li>
              <li>Your continued use constitutes acceptance of the updated Terms</li>
            </ul>
            <p className="mt-2">
              If you do not agree to the updated Terms, you must stop using SmartCoach and may delete your account.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-semibold text-gray-900 mb-3">17. Contact Information</h2>
            <p>If you have questions about these Terms, please contact us:</p>
            <div className="mt-3 bg-gray-50 p-4 rounded-md">
              <p><strong>Email:</strong> <a href="mailto:support@smartcoach.app" className="text-blue-600 hover:underline">support@smartcoach.app</a></p>
              <p className="mt-1"><strong>Response Time:</strong> We aim to respond within 48 hours</p>
            </div>
          </section>

          <section className="border-t pt-6 mt-8">
            <p className="text-sm text-gray-600">
              <strong>Powered by Strava:</strong> SmartCoach uses the Strava API. By using SmartCoach, you also agree to
              <a href="https://www.strava.com/legal/terms" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline"> Strava's Terms of Service</a> and
              <a href="https://www.strava.com/legal/privacy" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline"> Privacy Policy</a>.
            </p>
          </section>

          <section className="mt-6 bg-blue-50 p-4 rounded-md">
            <p className="text-sm font-semibold text-blue-900">
              By using SmartCoach, you acknowledge that you have read, understood, and agree to be bound by these Terms of Service.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default TermsOfService;
