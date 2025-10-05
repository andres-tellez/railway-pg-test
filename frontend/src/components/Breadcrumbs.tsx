/**
 * @file Breadcrumbs.tsx
 * @component Breadcrumbs
 * @description Breadcrumb navigation for showing page context and allowing easy navigation
 * 
 * @features:
 * - Automatic breadcrumb generation based on current route
 * - Custom breadcrumb support for complex pages
 * - Clickable breadcrumb items for navigation
 * - Responsive design that hides on small screens
 */

import React from 'react';
import { Link, useLocation } from 'react-router-dom';

interface BreadcrumbItem {
  label: string;
  path?: string;
}

interface BreadcrumbsProps {
  customBreadcrumbs?: BreadcrumbItem[];
}

const Breadcrumbs: React.FC<BreadcrumbsProps> = ({ customBreadcrumbs }) => {
  const location = useLocation();

  // Generate breadcrumbs from current path if no custom ones provided
  const generateBreadcrumbs = (): BreadcrumbItem[] => {
    const pathSegments = location.pathname.split('/').filter(Boolean);
    const breadcrumbs: BreadcrumbItem[] = [
      { label: 'Home', path: '/' }
    ];

    let currentPath = '';
    pathSegments.forEach((segment, index) => {
      currentPath += `/${segment}`;
      
      // Skip certain segments that don't need breadcrumbs
      if (segment === 'overview' || segment === 'plan' && index === 0) {
        return;
      }

      // Generate readable labels
      let label = segment;
      switch (segment) {
        case 'home':
          label = 'Dashboard';
          break;
        case 'onboarding':
          label = 'Setup';
          break;
        case 'ask':
          label = 'Ask Coach';
          break;
        case 'plan':
          label = 'My Plan';
          break;
        default:
          // Capitalize and replace hyphens with spaces
          label = segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, ' ');
      }

      breadcrumbs.push({
        label,
        path: index === pathSegments.length - 1 ? undefined : currentPath
      });
    });

    return breadcrumbs;
  };

  const breadcrumbs = customBreadcrumbs || generateBreadcrumbs();

  // Don't show breadcrumbs if we're on the home page or have only one item
  if (breadcrumbs.length <= 1) {
    return null;
  }

  return (
    <nav className="bg-white border-b border-gray-200 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        <ol className="flex items-center space-x-2 py-3 text-sm text-gray-600">
          {breadcrumbs.map((breadcrumb, index) => (
            <li key={index} className="flex items-center">
              {index > 0 && (
                <svg 
                  className="w-4 h-4 text-gray-400 mx-2" 
                  fill="none" 
                  stroke="currentColor" 
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              )}
              
              {breadcrumb.path ? (
                <Link
                  to={breadcrumb.path}
                  className="hover:text-gray-900 transition-colors"
                >
                  {breadcrumb.label}
                </Link>
              ) : (
                <span className="text-gray-900 font-medium">
                  {breadcrumb.label}
                </span>
              )}
            </li>
          ))}
        </ol>
      </div>
    </nav>
  );
};

export default Breadcrumbs;
