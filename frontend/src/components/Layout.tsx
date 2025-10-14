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
    <div className="min-h-screen bg-gray-50">
      {/* Top Navigation */}
      <Navigation />

      {/* Main Content */}
      <main className="flex-1">
        {children}
      </main>
    </div>
  );
};

export default Layout;
