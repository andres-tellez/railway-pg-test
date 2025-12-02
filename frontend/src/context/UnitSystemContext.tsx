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
  // Initialize from localStorage or default to imperial
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

  // Load preference on mount
  useEffect(() => {
    if (typeof window === 'undefined') {
      setIsLoading(false);
      return;
    }

    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved === 'metric' || saved === 'imperial') {
        setUnitSystemState(saved);
      }
    } catch (error) {
      console.warn('Failed to load unit system preference:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Save preference when changed
  const setUnitSystem = (system: UnitSystem) => {
    setUnitSystemState(system);

    if (typeof window !== 'undefined') {
      try {
        localStorage.setItem(STORAGE_KEY, system);
      } catch (error) {
        console.error('Failed to save unit system preference:', error);
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
