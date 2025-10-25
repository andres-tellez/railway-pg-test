// frontend/src/components/AuthGuard.tsx
import React from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { useAuthSetup } from '../hooks/useAuthSetup';

interface AuthGuardProps {
  children: React.ReactNode;
}

/**
 * Centralized auth guard that handles all authentication logic
 * Usage: Wrap any page component with <AuthGuard><MyPage /></AuthGuard>
 */
export const AuthGuard: React.FC<AuthGuardProps> = ({ children }) => {
  const { isLoading, isAuthenticated } = useAuth0();
  const { isReady, error: authError } = useAuthSetup();

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // Not authenticated
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 text-lg font-semibold">Not authenticated</p>
          <p className="text-gray-600 mt-2">Please log in to continue.</p>
        </div>
      </div>
    );
  }

  // Auth error
  if (authError) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center max-w-md mx-auto p-6 border border-red-200 rounded-lg bg-red-50">
          <p className="text-red-600 font-semibold mb-2">Authentication Error</p>
          <p className="text-gray-700 text-sm">{authError}</p>
        </div>
      </div>
    );
  }

  // Not ready (waiting for identity setup)
  if (!isReady) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Setting up your account...</p>
        </div>
      </div>
    );
  }

  // ✅ Authenticated and ready - render children
  return <>{children}</>;
};
