/**
 * Unit System Context - React Context for Unit Preferences
 *
 * Provides unit system throughout the app without prop drilling.
 * Defaults to imperial (US) for backward compatibility.
 * Persists preference to localStorage.
 *
 * @usage
 * ```tsx
 * import { useUnitSystem } from '../context/UnitSystemContext';
 *
 * const MyComponent = () => {
 *   const { unitSystem, setUnitSystem } = useUnitSystem();
 *   // ...
 * };
 * ```
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useApiClient } from '../utils/apiClient';
import { useAuthSetup } from '../hooks/useAuthSetup';

export type UnitSystem = 'imperial' | 'metric';

interface UnitSystemContextType {
  unitSystem: UnitSystem;
  setUnitSystem: (system: UnitSystem) => void;
  isLoading: boolean;
}

const UnitSystemContext = createContext<UnitSystemContextType | undefined>(undefined);

const STORAGE_KEY = 'smartcoach_unit_system';
const DEFAULT_UNIT_SYSTEM: UnitSystem = 'imperial'; // US default for backward compatibility

export const UnitSystemProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const api = useApiClient();
  const { isReady, userId } = useAuthSetup();

  // Initialize from localStorage or default to imperial (for immediate render)
  const [unitSystem, setUnitSystemState] = useState<UnitSystem>(() => {
    if (typeof window === 'undefined') {
      return DEFAULT_UNIT_SYSTEM;
    }

    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === 'metric' || saved === 'imperial') {
        return saved;
      }
    } catch (error) {
      console.warn('Failed to read unit system from localStorage:', error);
    }

    return DEFAULT_UNIT_SYSTEM;
  });

  const [isLoading, setIsLoading] = useState(true);

  // Load from database on mount (after auth is ready)
  useEffect(() => {
    if (!isReady || !userId) {
      // Fallback to localStorage if auth not ready
      if (typeof window !== 'undefined') {
        try {
          const saved = localStorage.getItem(STORAGE_KEY);
          if (saved === 'metric' || saved === 'imperial') {
            setUnitSystemState(saved);
          }
        } catch (error) {
          console.warn('Failed to load unit system from localStorage:', error);
        }
      }
      setIsLoading(false);
      return;
    }

    const loadFromDatabase = async () => {
      try {
        const response = await api.get('/api/onboarding');
        const profile = response.data?.data;
        if (profile?.unit_system && (profile.unit_system === 'metric' || profile.unit_system === 'imperial')) {
          setUnitSystemState(profile.unit_system);
          // Also update localStorage as backup
          if (typeof window !== 'undefined') {
            localStorage.setItem(STORAGE_KEY, profile.unit_system);
          }
        } else {
          // No database value, use localStorage if available
          if (typeof window !== 'undefined') {
            try {
              const saved = localStorage.getItem(STORAGE_KEY);
              if (saved === 'metric' || saved === 'imperial') {
                setUnitSystemState(saved);
              }
            } catch (error) {
              // Ignore localStorage errors
            }
          }
        }
      } catch (error) {
        console.warn('Failed to load unit system from database, using localStorage:', error);
        // Fallback to localStorage
        if (typeof window !== 'undefined') {
          try {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved === 'metric' || saved === 'imperial') {
              setUnitSystemState(saved);
            }
          } catch (e) {
            // Ignore localStorage errors
          }
        }
      } finally {
        setIsLoading(false);
      }
    };

    loadFromDatabase();
  }, [isReady, userId, api]);

  // Save preference when changed (to both database and localStorage)
  const setUnitSystem = async (system: UnitSystem) => {
    setUnitSystemState(system);

    // Save to localStorage immediately (for fast access)
    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem(STORAGE_KEY, system);
      } catch (error) {
        console.error('Failed to save unit system to localStorage:', error);
      }
    }

    // Save to database (async, don't block)
    if (isReady && userId) {
      try {
        await api.post('/api/onboarding', { unitSystem: system });
      } catch (error) {
        console.error('Failed to save unit system to database:', error);
        // Don't throw - localStorage is already saved
      }
    }
  };

  return (
    <UnitSystemContext.Provider value={{ unitSystem, setUnitSystem, isLoading }}>
      {children}
    </UnitSystemContext.Provider>
  );
};

/**
 * Hook to access unit system context
 *
 * @throws Error if used outside UnitSystemProvider
 * @returns Unit system context with current unit system and setter
 */
export const useUnitSystem = (): UnitSystemContextType => {
  const context = useContext(UnitSystemContext);
  if (!context) {
    throw new Error('useUnitSystem must be used within UnitSystemProvider');
  }
  return context;
};
