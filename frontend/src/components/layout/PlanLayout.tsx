import React from 'react';
import { Link, useLocation } from 'react-router-dom';

interface PlanLayoutProps {
  children: React.ReactNode;
}

const PlanLayout: React.FC<PlanLayoutProps> = ({ children }) => {
  const location = useLocation();

  const tabs = [
    { label: 'Calendar', path: '/plan/overview', icon: '📅' },
    { label: 'Manage Plans', path: '/plan/manage', icon: '⚙️' },
    { label: 'Create New Plan', path: '/plan/new', icon: '➕' },
  ];

  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(path);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Sub Navigation */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex overflow-x-auto scrollbar-hide md:hidden">
            {tabs.map((tab) => (
              <Link
                key={tab.path}
                to={tab.path}
                className={`flex items-center gap-2 px-4 py-3 min-w-fit whitespace-nowrap border-b-2 transition-colors ${
                  isActive(tab.path)
                    ? 'border-blue-500 text-blue-600 bg-blue-50'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span className="text-sm">{tab.icon}</span>
                <span className="text-sm font-medium">{tab.label}</span>
              </Link>
            ))}
          </div>

          <div className="hidden md:flex">
            {tabs.map((tab) => (
              <Link
                key={tab.path}
                to={tab.path}
                className={`flex items-center gap-2 px-6 py-4 border-b-2 transition-colors ${
                  isActive(tab.path)
                    ? 'border-blue-500 text-blue-600 bg-blue-50'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span className="text-base">{tab.icon}</span>
                <span className="text-base font-medium">{tab.label}</span>
              </Link>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">{children}</div>
    </div>
  );
};

export default PlanLayout;
