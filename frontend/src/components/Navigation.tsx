/**
 * @file Navigation.tsx
 * @component Navigation
 * @description Top navigation bar with smart navigation based on user state
 *
 * @features:
 * - Logo and app name
 * - Smart navigation links based on user completion status
 * - User profile dropdown with logout
 * - Mobile-responsive hamburger menu
 * - Active page highlighting
 */

import React, { useState, useEffect, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { useApiClient } from '../utils/apiClient';

const Navigation: React.FC = () => {
  const { user, logout, isAuthenticated } = useAuth0();
  const location = useLocation();
  const navigate = useNavigate();
  const api = useApiClient();

  const [userState, setUserState] = useState<{
    hasOnboarded: boolean;
    hasStrava: boolean;
  } | null>(null);
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [showProfileDropdown, setShowProfileDropdown] = useState(false);
  const profileDropdownRef = useRef<HTMLDivElement>(null);

  // Fetch user state for smart navigation
  // Refresh when authenticated, when location changes (to catch onboarding completion), or when userState is null
  useEffect(() => {
    if (isAuthenticated) {
      api.get<{ hasOnboarded: boolean; hasStrava: boolean }>('/api/user')
        .then((res) => {
          // Backend wraps response in { data: {...}, status: 200 }
          const userData = res.data.data || res.data;
          setUserState(userData);
        })
        .catch((err) => {
          console.error('Failed to fetch user state:', err);
        });
    }
  }, [isAuthenticated, location.pathname]); // Refresh when route changes to catch onboarding completion

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        profileDropdownRef.current &&
        !profileDropdownRef.current.contains(event.target as Node)
      ) {
        setShowProfileDropdown(false);
      }
    };

    if (showProfileDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showProfileDropdown]);

  const handleLogout = () => {
    logout({
      logoutParams: {
        returnTo: window.location.origin
      }
    });
  };

  const isActive = (path: string) => {
    return location.pathname === path || location.pathname.startsWith(path);
  };

  const navItems = [];

  // Add navigation items based on user state
  // Don't show "Complete Profile" on setup or onboarding pages - they handle profile completion themselves
  const isOnSetupOrOnboarding = location.pathname === '/setup' || location.pathname === '/profile';

  if (userState) {
    if (userState.hasOnboarded) {
      // Complete user - show full navigation
      navItems.push(
        { label: 'Training Plan', path: '/plan/overview', icon: '📊' },
        { label: 'Metrics', path: '/metrics', icon: '📊' },
        { label: 'Ask Coach', path: '/ask', icon: '💬' }
      );
    } else if (userState.hasStrava && !isOnSetupOrOnboarding) {
      // Has Strava but not onboarded - only show "Complete Profile" if not already on setup/profile pages
      navItems.push(
        { label: 'Complete Profile', path: '/profile', icon: '⚙️' }
      );
    }
    // New users without Strava - no navigation items (they're on setup page)
  }

  if (!isAuthenticated) {
    return null; // Don't show navigation if not authenticated
  }

  return (
    <nav className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center h-16">
          {/* Left spacer (optional menu placeholder on mobile) */}
          <div className="w-10 flex items-center justify-start md:hidden" />

          {/* Center: Brand (centered on mobile, left on desktop) */}
          <div className="flex-1 flex items-center justify-center md:justify-start">
            <Link
              to={userState?.hasOnboarded ? '/home' : '/'}
              className="flex items-center space-x-2"
            >
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">SC</span>
              </div>
              <span className="text-lg md:text-xl font-semibold text-gray-900">
                SmartCoach
              </span>
            </Link>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-8">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center space-x-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive(item.path)
                    ? 'text-blue-600 bg-blue-50'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            ))}
          </div>

          {/* Right: Profile/avatar */}
          <div className="w-10 flex items-center justify-end relative" ref={profileDropdownRef}>
            <button
              onClick={() => setShowProfileDropdown(!showProfileDropdown)}
              className="flex items-center space-x-2 p-2 rounded-md hover:bg-gray-50 transition-colors"
            >
              {user?.picture ? (
                <img
                  src={user.picture}
                  alt={user.name || 'User'}
                  className="w-8 h-8 rounded-full border border-gray-300"
                />
              ) : (
                <div className="w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center">
                  <span className="text-gray-600 text-sm font-medium">
                    {user?.name?.charAt(0) || 'U'}
                  </span>
                </div>
              )}
              {/* Hide email/name on mobile for cleanliness */}
              <span className="hidden md:block text-sm font-medium text-gray-700 truncate max-w-[140px]">
                {user?.email || user?.name || 'User'}
              </span>
              <svg
                className="w-4 h-4 text-gray-400 hidden md:block"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Profile Dropdown */}
            {showProfileDropdown && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-md shadow-lg border border-gray-200 py-1 z-50">
                <div className="px-4 py-2 border-b border-gray-100">
                  <p className="text-sm font-medium text-gray-900">{user?.name}</p>
                  <p className="text-sm text-gray-500">{user?.email}</p>
                </div>

                {/* Profile Link */}
                <Link
                  to="/profile"
                  className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                  onClick={() => setShowProfileDropdown(false)}
                >
                  👤 Profile
                </Link>

                {/* Settings Link */}
                <Link
                  to="/settings"
                  className="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                  onClick={() => setShowProfileDropdown(false)}
                >
                  ⚙️ Settings
                </Link>

                {/* Sign out */}
                <button
                  onClick={handleLogout}
                  className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Mobile Navigation Menu */}
      {showMobileMenu && (
        <div className="md:hidden border-t border-gray-200 py-4">
          <div className="space-y-2">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setShowMobileMenu(false)}
                className={`flex items-center space-x-2 px-3 py-2 rounded-md text-base font-medium transition-colors ${
                  isActive(item.path)
                    ? 'text-blue-600 bg-blue-50'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            ))}
            <button
              onClick={handleLogout}
              className="flex items-center space-x-2 px-3 py-2 rounded-md text-base font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-50 w-full text-left"
            >
              <span>🚪</span>
              <span>Sign out</span>
            </button>
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navigation;
