/**
 * @file Layout.tsx
 * @component Layout
 * @description Main layout wrapper that provides consistent navigation and structure across all pages
 *
 * @features:
 * - Top navigation bar with user state-based navigation
 * - User profile dropdown with logout
 * - Responsive design for mobile and desktop
 * - Clean, modern interface without breadcrumbs
 *
 * @integration-points:
 * - Auth0 for user authentication and logout
 * - React Router for navigation links
 * - User state management for smart navigation
 */

import React from 'react';
import { useLocation } from 'react-router-dom';
import Navigation from './Navigation';
import StravaAttribution from './StravaAttribution';

interface LayoutProps {
  children: React.ReactNode;
}

const Layout: React.FC<LayoutProps> = ({
  children
}) => {
  const location = useLocation();

  // Don't show navigation on login page
  if (location.pathname === '/login') {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top Navigation */}
      <Navigation />

      {/* Main Content */}
      <main className="flex-1">
        {children}
      </main>

      {/* Footer with Strava Attribution */}
      <footer className="bg-white border-t border-gray-200 py-4">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex flex-col md:flex-row justify-between items-center gap-3">
            {/* Legal Links */}
            <div className="flex gap-4 text-xs text-gray-600">
              <a href="/privacy-policy" className="hover:text-gray-900 hover:underline">
                Privacy Policy
              </a>
              <span className="text-gray-300">|</span>
              <a href="/terms-of-service" className="hover:text-gray-900 hover:underline">
                Terms of Service
              </a>
              <span className="text-gray-300">|</span>
              <a href="/data-deletion" className="hover:text-gray-900 hover:underline">
                Delete My Data
              </a>
              <span className="text-gray-300">|</span>
              <a href="/data-usage" className="hover:text-gray-900 hover:underline">
                Data Usage
              </a>
              <span className="text-gray-300">|</span>
              <a href="mailto:support@smartcoach.app" className="hover:text-gray-900 hover:underline">
                Contact Support
              </a>
            </div>

            {/* Strava Attribution */}
            <StravaAttribution variant="powered" className="text-xs text-gray-500" />
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
