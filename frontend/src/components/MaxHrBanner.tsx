// frontend/src/components/MaxHrBanner.tsx
import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useApiClient } from '../utils/apiClient';
import { useAuthSetup } from '../hooks/useAuthSetup';

const MaxHrBanner: React.FC = () => {
  const { isReady, userId } = useAuthSetup();
  const api = useApiClient();
  const [showBanner, setShowBanner] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isReady || !userId) {
      console.log('🔍 MaxHrBanner: Waiting for auth - isReady:', isReady, 'userId:', userId);
      return;
    }

    const checkMaxHr = async () => {
      try {
        console.log('🔍 MaxHrBanner: Checking max_hr...');
        const response = await api.get('/api/onboarding');
        console.log('🔍 MaxHrBanner: Full response:', response);
        console.log('🔍 MaxHrBanner: response.data:', response.data);

        const profileData = response.data?.data;
        console.log('🔍 MaxHrBanner: profileData:', profileData);
        console.log('🔍 MaxHrBanner: max_hr value:', profileData?.max_hr);
        console.log('🔍 MaxHrBanner: max_hr type:', typeof profileData?.max_hr);
        console.log('🔍 MaxHrBanner: max_hr is null?', profileData?.max_hr === null);
        console.log('🔍 MaxHrBanner: max_hr is undefined?', profileData?.max_hr === undefined);

        // Show banner if max_hr is null or undefined
        const shouldShow = !profileData?.max_hr;
        console.log('🔍 MaxHrBanner: Should show banner?', shouldShow);
        setShowBanner(shouldShow);
      } catch (e: any) {
        // If we can't fetch profile, don't show banner
        console.error('❌ MaxHrBanner: Error checking max_hr:', e);
        console.error('❌ MaxHrBanner: Error response:', e.response);
        setShowBanner(false);
      } finally {
        setLoading(false);
        console.log('🔍 MaxHrBanner: Loading complete, showBanner:', showBanner);
      }
    };

    checkMaxHr();
  }, [isReady, userId, api]);

  if (loading || !showBanner) {
    return null;
  }

  return (
    <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6 rounded-r-lg">
      <div className="flex items-start">
        <div className="flex-shrink-0">
          <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
        </div>
        <div className="ml-3 flex-1">
          <h3 className="text-sm font-medium text-yellow-800">
            Complete your profile for accurate HR zones
          </h3>
          <p className="mt-1 text-sm text-yellow-700">
            Your max heart rate is missing. Add it to get personalized HR zone targets in your training plan.
          </p>
          <div className="mt-2 flex gap-4">
            <Link
              to="/profile"
              className="text-sm font-medium text-yellow-800 underline hover:text-yellow-900"
            >
              Add Max Heart Rate in Profile →
            </Link>
            <Link
              to="/heart-rate-zones"
              className="text-sm font-medium text-yellow-800 underline hover:text-yellow-900"
            >
              Learn about HR zones →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MaxHrBanner;
