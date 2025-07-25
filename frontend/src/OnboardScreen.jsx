import React, { useState } from 'react';

export default function OnboardingScreen() {
  const [hasStrava, setHasStrava] = useState(null);

  const clientId = import.meta.env.VITE_STRAVA_CLIENT_ID;
  const redirectUri = import.meta.env.VITE_STRAVA_REDIRECT_URI;

  const handleAuthorize = () => {
    const authUrl = `https://www.strava.com/oauth/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=code&scope=read,activity:read_all`;
    window.location.href = authUrl;
  };

  return (
    <div className="max-w-xl mx-auto p-6 rounded-2xl shadow-md bg-white mt-10 text-center">
      <h1 className="text-3xl font-bold mb-4">Get Started with SmartCoach</h1>
      <p className="mb-4 text-gray-700">
        SmartCoach uses your Strava activity data to build your personal training plan.
      </p>

      {hasStrava === null ? (
        <div>
          <p className="mb-4">Do you use Strava to track your runs?</p>
          <div className="flex justify-center gap-4">
            <button onClick={() => setHasStrava(true)} className="bg-blue-600 text-white px-4 py-2 rounded-xl shadow">
              Yes
            </button>
            <button onClick={() => setHasStrava(false)} className="bg-gray-300 text-black px-4 py-2 rounded-xl shadow">
              No
            </button>
          </div>
        </div>
      ) : hasStrava ? (
        <div className="mt-6">
          <div className="bg-yellow-50 border border-yellow-200 p-4 mb-4 rounded-xl text-sm text-left">
            <p className="mb-2 font-semibold">By continuing, you authorize SmartCoach to:</p>
            <ul className="list-disc list-inside text-gray-800">
              <li>Import your last 10 Strava runs</li>
              <li>Use your data to generate a training plan</li>
              <li>Never post or share your Strava info</li>
            </ul>
          </div>

          <button onClick={handleAuthorize} className="bg-green-600 text-white px-6 py-2 rounded-xl shadow-md w-full">
            Authorize with Strava
          </button>
        </div>
      ) : (
        <div className="mt-6 text-gray-700">
          <p>SmartCoach requires a Strava account to personalize your training.</p>
          <p className="mt-2">Please create a Strava account and come back to get started.</p>
        </div>
      )}
    </div>
  );
}

