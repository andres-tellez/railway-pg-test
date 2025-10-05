/**
 * @file Layout.tsx
 * @component Layout
 * @description Main layout wrapper that provides consistent navigation and structure across all pages
 * 
 * @features:
 * - Top navigation bar with user state-based navigation
 * - Breadcrumb navigation for page context
 * - User profile dropdown with logout
 * - Responsive design for mobile and desktop
 * 
 * @integration-points:
 * - Auth0 for user authentication and logout
 * - React Router for navigation links
 * - User state management for smart navigation
 */

import React from 'react';
import { useAuth0 } from '@auth0/auth0-react';
import { useLocation, useNavigate } from 'react-router-dom';
import Navigation from './Navigation';
import Breadcrumbs from './Breadcrumbs';

interface LayoutProps {
  children: React.ReactNode;
  showBreadcrumbs?: boolean;
  customBreadcrumbs?: Array<{ label: string; path?: string }>;
}

const Layout: React.FC<LayoutProps> = ({ 
  children, 
  showBreadcrumbs = true,
  customBreadcrumbs 
}) => {
  const { user, isAuthenticated } = useAuth0();
  const location = useLocation();

  // Don't show navigation on login page
  if (location.pathname === '/login') {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top Navigation */}
      <Navigation />
      
      {/* Breadcrumbs */}
      {showBreadcrumbs && (
        <Breadcrumbs customBreadcrumbs={customBreadcrumbs} />
      )}
      
      {/* Main Content */}
      <main className="flex-1">
        {children}
      </main>
    </div>
  );
};

export default Layout;
