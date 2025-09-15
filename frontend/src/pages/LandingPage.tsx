// src/pages/LandingPage.tsx

import React from "react";
import { useAuth0 } from "@auth0/auth0-react";

const LandingPage: React.FC = () => {
  const { user } = useAuth0();

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-4 bg-gray-50">
      {/* User avatar + name */}
      <div className="flex items-center gap-4 mt-8 mb-6">
        {user?.picture ? (
          <img
            src={user.picture}
            alt={user.name || "User"}
            className="w-12 h-12 rounded-full border border-gray-300"
          />
        ) : (
          <div className="w-12 h-12 rounded-full bg-gray-300" />
        )}
        <h1 className="text-2xl font-semibold text-gray-900">
          {user?.name || "Runner"}
        </h1>
      </div>

      {/* Welcome message */}
      <h2 className="text-xl font-medium text-center text-gray-700 mb-4">
        Welcome to SmartCoach
      </h2>
      <p className="text-center text-gray-600 max-w-md mb-8">
        Your personalized running plan, generated just for you.
        Let’s get started!
      </p>

      {/* CTA button */}
      <button
        onClick={() => (window.location.href = "/onboarding")}
        className="bg-blue-600 text-white px-6 py-3 rounded-lg shadow hover:bg-blue-700 transition"
      >
        Create My Training Plan
      </button>
    </div>
  );
};

export default LandingPage;
