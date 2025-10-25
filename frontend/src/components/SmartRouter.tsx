/**
 * @file SmartRouter.tsx
 * @component SmartRouter
 * @description Smart routing component that redirects users based on their completion status
 *
 * @features:
 * - Checks user authentication status
 * - Checks user onboarding completion
 * - Routes to appropriate page based on user state
 * - Loading states during checks
 */

import React, { useState, useEffect } from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { useNavigate } from 'react-router-dom';
import { useApiClient } from '../utils/apiClient';
import { useAuthSetup } from '../hooks/useAuthSetup';

const SmartRouter: React.FC = () => {
  const { isAuthenticated, isLoading: authLoading } = useAuth0();
  const navigate = useNavigate();
  const api = useApiClient();
  const [isCheckingUser, setIsCheckingUser] = useState(true);

  useEffect(() => {
    if (authLoading) return; // Wait for auth to load

    if (!isAuthenticated) {
      // Not authenticated - go to welcome page
      navigate('/welcome', { replace: true });
      return;
    }

    // Authenticated - check user state
    const checkUserState = async () => {
      try {
        setIsCheckingUser(true);
        const response = await api.get<{ hasOnboarded: boolean; hasStrava: boolean }>('/user');
        const { hasOnboarded, hasStrava } = response.data;

        console.log('🔍 User state check:', { hasOnboarded, hasStrava });

        if (hasOnboarded) {
          // Complete user - go to dashboard
          console.log('✅ User has onboarded, redirecting to /home');
          navigate('/home', { replace: true });
        } else if (hasStrava) {
          // Has Strava but not onboarded - go to onboarding
          console.log('⚙️ User has Strava but not onboarded, redirecting to /onboarding');
          navigate('/onboarding', { replace: true });
        } else {
          // New user - go to setup
          console.log('🆕 New user, redirecting to /setup');
          navigate('/setup', { replace: true });
        }
      } catch (error) {
        console.error('❌ Failed to check user state:', error);
        // Default to setup page on error
        navigate('/setup', { replace: true });
      } finally {
        setIsCheckingUser(false);
      }
    };

    checkUserState();
  }, [isAuthenticated, authLoading]); // Remove navigate and api to prevent infinite loop

  if (authLoading || isCheckingUser) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return null; // Will redirect before this renders
};

export default SmartRouter;
