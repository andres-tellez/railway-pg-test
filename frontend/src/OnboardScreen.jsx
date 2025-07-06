import React, { useState } from 'react';

export default function OnboardingScreen() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [hasStrava, setHasStrava] = useState(null);

  const handleContinue = () => {
    if (!email) {
      alert("Please enter your email address to continue.");
      return;
    }
    localStorage.setItem("user_name", name);
    localStorage.setItem("user_email", email);
    window.location.href = "http://localhost:5000/auth/login";

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
          <label className="block mb-2 text-left font-medium">Your Name</label>
          <input
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            className="w-full p-2 mb-4 border rounded-xl"
            placeholder="Optional"
          />

          <label className="block mb-2 text-left font-medium">Email Address</label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full p-2 mb-4 border rounded-xl"
            placeholder="Required"
          />

          <div className="bg-yellow-50 border border-yellow-200 p-4 mb-4 rounded-xl text-sm text-left">
            <p className="mb-2 font-semibold">By continuing, you authorize SmartCoach to:</p>
            <ul className="list-disc list-inside text-gray-800">
              <li>Import your last 10 Strava runs</li>
              <li>Use your data to generate a training plan</li>
              <li>Never post or share your Strava info</li>
            </ul>
          </div>

          <button onClick={handleContinue} className="bg-green-600 text-white px-6 py-2 rounded-xl shadow-md w-full">
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
