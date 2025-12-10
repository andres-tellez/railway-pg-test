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

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth0 } from '@auth0/auth0-react';
import { useApiClient } from '../utils/apiClient';

const DEFAULT_NAV_ITEMS = [
  { label: 'Training Plan', path: '/plan/overview', icon: '📊' },
  { label: 'Metrics', path: '/metrics', icon: '📊' },
  { label: 'Ask Coach', path: '/ask', icon: '💬' },
];

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

  // Close menus on Escape
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setShowMobileMenu(false);
        setShowProfileDropdown(false);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

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

  // Add navigation items based on user state
  const isOnSetupOrOnboarding = location.pathname === '/setup' || location.pathname === '/profile';

  const navItems = useMemo(() => {
    if (!userState) {
      return DEFAULT_NAV_ITEMS;
    }

    if (userState.hasOnboarded) {
      return DEFAULT_NAV_ITEMS;
    }

    if (userState.hasStrava && !isOnSetupOrOnboarding) {
      return [{ label: 'Complete Profile', path: '/profile', icon: '⚙️' }];
    }

    return DEFAULT_NAV_ITEMS;
  }, [userState, isOnSetupOrOnboarding]);

  if (!isAuthenticated) {
    return null; // Don't show navigation if not authenticated
  }

  return (
    <nav className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center h-16">
          {/* Mobile hamburger (hidden on desktop) */}
          <div className="w-10 flex items-center justify-start">
            <button
              onClick={() => setShowMobileMenu(!showMobileMenu)}
              aria-label="Toggle navigation"
              className="p-2 rounded-md text-gray-600 hover:text-gray-900 hover:bg-gray-50 md:hidden"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>

          {/* Brand (centered on mobile, left on desktop) */}
          <div className="flex-1 flex items-center justify-center md:flex-none md:justify-start">
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

          {/* Desktop Navigation - centered in remaining space */}
          <div className="hidden md:flex flex-1 items-center justify-center space-x-8">
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
          <div className="w-10 md:w-auto flex items-center justify-end relative" ref={profileDropdownRef}>
            <button
              onClick={() => setShowProfileDropdown(!showProfileDropdown)}
              className="flex items-center space-x-2 p-2 rounded-md hover:bg-gray-50 transition-colors min-w-0"
            >
              {user?.picture ? (
                <img
                  src={user.picture}
                  alt={user.name || 'User'}
                  className="w-8 h-8 aspect-square rounded-full border border-gray-300 object-cover"
                />
              ) : (
                <div className="w-8 h-8 aspect-square rounded-full bg-gray-300 flex items-center justify-center">
                  <span className="text-gray-600 text-sm font-medium">
                    {user?.name?.charAt(0) || 'U'}
                  </span>
                </div>
              )}
              {/* Hide text on mobile; show display name on desktop with truncation */}
              <span
                className="hidden md:block text-sm font-medium text-gray-700 truncate max-w-[160px]"
                title={user?.name || user?.email || 'User'}
              >
                {user?.name || user?.email || 'User'}
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

      {/* Mobile Navigation Menu (mobile only) */}
      {showMobileMenu && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/20 md:hidden"
            onClick={() => setShowMobileMenu(false)}
          />
          <div className="fixed z-50 top-16 left-4 right-4 md:hidden bg-white border border-gray-200 rounded-lg shadow-lg">
            <div className="py-2">
              {navItems.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setShowMobileMenu(false)}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive(item.path)
                      ? 'text-blue-600 bg-blue-50'
                      : 'text-gray-700 hover:text-gray-900 hover:bg-gray-50'
                  }`}
                >
                  <span>{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              ))}
              <button
                onClick={handleLogout}
                className="w-full text-left flex items-center space-x-2 px-4 py-2 rounded-md text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-50"
              >
                <span>🚪</span>
                <span>Sign out</span>
              </button>
            </div>
          </div>
        </>
      )}
    </nav>
  );
};

export default Navigation;
