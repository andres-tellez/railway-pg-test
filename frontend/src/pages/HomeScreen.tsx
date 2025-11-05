// @file HomeScreen.tsx
// @component HomeScreen
// @description: Main dashboard showing 3 core training cards as entry points
// @features: Weekly overview, training quality summary, GPT-based coaching
// @integration-points: React Router (routes: /my-plan, /progress, /ask)
// @usage: Displayed after login as the main landing page
// @prerequisites: Pages must exist for /my-plan, /progress, and /ask

import React, { useState, useEffect } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import WelcomeModal from '../components/WelcomeModal';

const HomeScreen: React.FC = () => {
  const [showWelcome, setShowWelcome] = useState(false);
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    // Check if we should show welcome modal
    const welcomeShown = localStorage.getItem('smartcoach_welcome_shown');
    const fromOnboarding = searchParams.get('welcome') === 'true';

    // Show welcome if:
    // 1. Coming from onboarding (welcome=true param)
    // 2. First time visiting (welcomeShown not set)
    if (fromOnboarding || !welcomeShown) {
      setShowWelcome(true);
      // Mark as shown after a short delay to prevent immediate re-show
      if (!welcomeShown) {
        localStorage.setItem('smartcoach_welcome_shown', 'true');
      }
      // Clean up URL param if present
      if (fromOnboarding) {
        navigate('/home', { replace: true });
      }
    }
  }, [searchParams, navigate]);

  const handleCloseWelcome = () => {
    setShowWelcome(false);
  };

  return (
    <>
      <div className="px-4 py-6 max-w-xl mx-auto space-y-6">
        {/* Weekly Activity Progress */}
        <div className="bg-white p-5 rounded-lg shadow">
          <h2 className="text-lg font-semibold mb-2">📈 Weekly Activity Progress</h2>
          <Link to="/metrics" className="text-blue-600 hover:underline">
            See Full Progress →
          </Link>
        </div>

        {/* Training Plan */}
        <div className="bg-white p-5 rounded-lg shadow">
          <h2 className="text-lg font-semibold mb-2">📆 Training Plan</h2>
          <Link to="/plan/overview" className="text-blue-600 hover:underline">
            View My Plan →
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

      {showWelcome && <WelcomeModal onClose={handleCloseWelcome} />}
    </>
  );
};

export default HomeScreen;
