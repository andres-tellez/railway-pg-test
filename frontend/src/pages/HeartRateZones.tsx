import React from 'react';
import { Link } from 'react-router-dom';
import { AuthGuard } from '@/components/AuthGuard';
import { useUnitSystem } from '@/context/UnitSystemContext';
import { parseAndConvertPaceString } from '@/utils/unitFormatters';

const HeartRateZones: React.FC = () => {
  const { unitSystem } = useUnitSystem();

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* Hero Section */}
          <div className="text-center mb-12">
            <div className="text-6xl mb-4">💓</div>
            <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              Heart Rate Zones
            </h1>
            <p className="text-lg md:text-xl text-gray-700 max-w-3xl mx-auto leading-relaxed">
              Strava uses your heart rate (HR) to help you understand how hard your body is working to train smarter, recover better, and see real progress over time.
            </p>
            <div className="mt-4 inline-block bg-blue-50 border border-blue-200 rounded-lg px-4 py-2">
              <p className="text-sm text-blue-900">
                <strong>Note:</strong> Heart Rate Zones are a paid feature in Strava. SmartCoach automatically calculates your HR Zones for non-Strava paid subscribers so you can get the same insights.
              </p>
            </div>
          </div>

          {/* Max Heart Rate Section */}
          <div className="bg-white rounded-xl shadow-md p-6 md:p-8 mb-8 border border-gray-200">
            <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-4">
              Max Heart Rate (MHR)
            </h2>
            <p className="text-gray-700 mb-4 leading-relaxed">
              Your Max Heart Rate is the highest number of beats per minute your heart can safely reach during exercise. Strava automatically estimates it based on your age and activity data.
            </p>
            <div className="bg-gray-50 rounded-lg p-4 mb-4 border border-gray-200">
              <p className="text-lg font-semibold text-gray-900 mb-2">Formula:</p>
              <p className="text-2xl font-bold text-blue-600">MHR = 220 – your age</p>
            </div>
            <p className="text-gray-700 mb-2 leading-relaxed">
              Heart rate zones are personalized as percentages of this number.
            </p>
            <div className="bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded">
              <p className="text-sm text-yellow-900">
                <strong>NOTE:</strong> You can update your Max Heart Rate anytime in your Strava profile if you know your tested value.
              </p>
            </div>
          </div>

          {/* Heart Rate Zones Table */}
          <div className="bg-white rounded-xl shadow-md p-6 md:p-8 mb-8 border border-gray-200">
            <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-6">
              Your Heart Rate Zones
            </h2>
            <p className="text-gray-700 mb-6 leading-relaxed">
              Each zone represents a different intensity level. As your fitness improves, you'll be able to run faster while staying in the same zone.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-gray-50 border-b-2 border-gray-300">
                    <th className="text-left py-3 px-4 font-semibold text-gray-900">Zone</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-900">% of MHR</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-900">Effort</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-900">How It Feels</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-gray-200 hover:bg-blue-50 transition-colors">
                    <td className="py-4 px-4">
                      <span className="text-2xl">🩵</span>
                      <span className="ml-2 font-semibold text-gray-900">Z1 – Recovery</span>
                    </td>
                    <td className="py-4 px-4 text-gray-700 font-medium">50–60%</td>
                    <td className="py-4 px-4 text-gray-700">Very Easy</td>
                    <td className="py-4 px-4 text-gray-600">Gentle pace • you can talk easily</td>
                  </tr>
                  <tr className="border-b border-gray-200 hover:bg-green-50 transition-colors">
                    <td className="py-4 px-4">
                      <span className="text-2xl">💚</span>
                      <span className="ml-2 font-semibold text-gray-900">Z2 – Endurance</span>
                    </td>
                    <td className="py-4 px-4 text-gray-700 font-medium">60–70%</td>
                    <td className="py-4 px-4 text-gray-700">Easy</td>
                    <td className="py-4 px-4 text-gray-600">Steady pace • light breathing</td>
                  </tr>
                  <tr className="border-b border-gray-200 hover:bg-yellow-50 transition-colors">
                    <td className="py-4 px-4">
                      <span className="text-2xl">💛</span>
                      <span className="ml-2 font-semibold text-gray-900">Z3 – Tempo</span>
                    </td>
                    <td className="py-4 px-4 text-gray-700 font-medium">70–80%</td>
                    <td className="py-4 px-4 text-gray-700">Moderate</td>
                    <td className="py-4 px-4 text-gray-600">Breathing deeper • short phrases</td>
                  </tr>
                  <tr className="border-b border-gray-200 hover:bg-orange-50 transition-colors">
                    <td className="py-4 px-4">
                      <span className="text-2xl">🧡</span>
                      <span className="ml-2 font-semibold text-gray-900">Z4 – Threshold</span>
                    </td>
                    <td className="py-4 px-4 text-gray-700 font-medium">80–90%</td>
                    <td className="py-4 px-4 text-gray-700">Hard</td>
                    <td className="py-4 px-4 text-gray-600">Sustained push • few words only</td>
                  </tr>
                  <tr className="border-b border-gray-200 hover:bg-red-50 transition-colors">
                    <td className="py-4 px-4">
                      <span className="text-2xl">❤️</span>
                      <span className="ml-2 font-semibold text-gray-900">Z5 – Max Effort</span>
                    </td>
                    <td className="py-4 px-4 text-gray-700 font-medium">90–100%</td>
                    <td className="py-4 px-4 text-gray-700">Very Hard</td>
                    <td className="py-4 px-4 text-gray-600">All-out • can't talk</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* How Pace Fits In Section */}
          <div className="bg-white rounded-xl shadow-md p-6 md:p-8 mb-8 border border-gray-200">
            <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-4">
              How Pace Fits In
            </h2>
            <p className="text-gray-700 mb-6 leading-relaxed">
              Your pace and HR work together. HR shows effort, pace shows results. Over time, Strava learns how your body responds to different levels of effort. As your fitness improves, your HR stays lower at faster paces.
            </p>

            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-gray-50 border-b-2 border-gray-300">
                    <th className="text-left py-3 px-4 font-semibold text-gray-900">HR Zone</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-900">Typical Pace Range</th>
                    <th className="text-left py-3 px-4 font-semibold text-gray-900">Training Type</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-gray-200 hover:bg-blue-50 transition-colors">
                    <td className="py-4 px-4">
                      <span className="text-2xl">🩵</span>
                      <span className="ml-2 font-semibold text-gray-900">Z1</span>
                    </td>
                    <td className="py-4 px-4 text-gray-700 font-medium">
                      {parseAndConvertPaceString('10:30–12:00/mi', unitSystem)}
                    </td>
                    <td className="py-4 px-4 text-gray-600">Recovery runs, warm-ups</td>
                  </tr>
                  <tr className="border-b border-gray-200 hover:bg-green-50 transition-colors">
                    <td className="py-4 px-4">
                      <span className="text-2xl">💚</span>
                      <span className="ml-2 font-semibold text-gray-900">Z2</span>
                    </td>
                    <td className="py-4 px-4 text-gray-700 font-medium">
                      {parseAndConvertPaceString('9:10–10:30/mi', unitSystem)}
                    </td>
                    <td className="py-4 px-4 text-gray-600">Long runs, easy aerobic training</td>
                  </tr>
                  <tr className="border-b border-gray-200 hover:bg-yellow-50 transition-colors">
                    <td className="py-4 px-4">
                      <span className="text-2xl">💛</span>
                      <span className="ml-2 font-semibold text-gray-900">Z3</span>
                    </td>
                    <td className="py-4 px-4 text-gray-700 font-medium">
                      {parseAndConvertPaceString('8:00–9:10/mi', unitSystem)}
                    </td>
                    <td className="py-4 px-4 text-gray-600">Tempo runs, steady efforts</td>
                  </tr>
                  <tr className="border-b border-gray-200 hover:bg-orange-50 transition-colors">
                    <td className="py-4 px-4">
                      <span className="text-2xl">🧡</span>
                      <span className="ml-2 font-semibold text-gray-900">Z4</span>
                    </td>
                    <td className="py-4 px-4 text-gray-700 font-medium">
                      {parseAndConvertPaceString('7:35–8:00/mi', unitSystem)}
                    </td>
                    <td className="py-4 px-4 text-gray-600">Intervals, hill repeats</td>
                  </tr>
                  <tr className="border-b border-gray-200 hover:bg-red-50 transition-colors">
                    <td className="py-4 px-4">
                      <span className="text-2xl">❤️</span>
                      <span className="ml-2 font-semibold text-gray-900">Z5</span>
                    </td>
                    <td className="py-4 px-4 text-gray-700 font-medium">
                      &lt;{parseAndConvertPaceString('7:35/mi', unitSystem)}
                    </td>
                    <td className="py-4 px-4 text-gray-600">Sprints, all-out efforts</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* Takeaway Section */}
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl shadow-md p-6 md:p-8 mb-8 border border-blue-200">
            <div className="text-center">
              <div className="text-4xl mb-4">💡</div>
              <h2 className="text-2xl md:text-3xl font-bold text-gray-900 mb-4">
                Takeaway
              </h2>
              <p className="text-lg md:text-xl text-gray-700 leading-relaxed max-w-2xl mx-auto">
                Heart rate zones aren't about working harder… they're about working smarter and understanding your body.
              </p>
            </div>
          </div>

          {/* Related Links */}
          <div className="text-center space-y-4">
            <Link
              to="/pace-zones"
              className="inline-flex items-center px-6 py-3 bg-green-600 text-white font-semibold rounded-lg hover:bg-green-700 transition-colors shadow-md hover:shadow-lg"
            >
              Learn About Pace Zones
              <svg className="ml-2 w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </Link>
            <div>
              <Link
                to="/profile"
                className="inline-flex items-center px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 transition-colors shadow-md hover:shadow-lg"
              >
                Set Your Max Heart Rate
                <svg className="ml-2 w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </Link>
            </div>
          </div>
        </div>
      </div>
    </AuthGuard>
  );
};

export default HeartRateZones;
