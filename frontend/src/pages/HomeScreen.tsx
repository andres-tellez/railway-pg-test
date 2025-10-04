// @file HomeScreen.tsx
// @component HomeScreen
// @description: Main dashboard showing 3 core training cards as entry points
// @features: Weekly overview, training quality summary, GPT-based coaching
// @integration-points: React Router (routes: /my-plan, /progress, /ask)
// @usage: Displayed after login as the main landing page
// @prerequisites: Pages must exist for /my-plan, /progress, and /ask

import React from 'react';
import { Link } from 'react-router-dom';

const HomeScreen: React.FC = () => {
  return (
    <div className="px-4 py-6 max-w-xl mx-auto space-y-6">
      {/* Weekly Overview */}
      <div className="bg-white p-5 rounded-lg shadow">
        <h2 className="text-lg font-semibold mb-2">📆 Weekly Overview</h2>
        <Link to="/plan/overview" className="text-blue-600 hover:underline">
        View My Plan →
        </Link>
      </div>

      {/* Training Quality Summary */}
      <div className="bg-white p-5 rounded-lg shadow">
        <h2 className="text-lg font-semibold mb-2">📈 Training Quality Summary</h2>
        <Link to="/progress" className="text-blue-600 hover:underline">
          See Full Progress →
        </Link>
      </div>

      {/* Ask Coach */}
      <div className="bg-white p-5 rounded-lg shadow">
        <h2 className="text-lg font-semibold mb-2">💬 Ask Coach</h2>
        <Link to="/ask" className="text-blue-600 hover:underline">
          Ask a Question →
        </Link>
      </div>
    </div>
  );
};

export default HomeScreen;
