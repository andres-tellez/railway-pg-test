import React, { useState, useEffect, useRef } from "react";
import { Control, Controller, FieldValues } from "react-hook-form";

interface LocationAutocompleteProps {
  control: Control<any>;
  name: string;
  className?: string;
  placeholder?: string;
  apiKey?: string;
  onLocationSelect?: (location: string) => void;
}

declare global {
  interface Window {
    google: any;
    initGooglePlaces: () => void;
  }
}

interface LocationInputProps {
  field: FieldValues & { onChange: (value: string) => void; value: string; ref: (e: HTMLInputElement | null) => void };
  isGoogleLoaded: boolean;
  apiKey?: string;
  className?: string;
  placeholder?: string;
  onLocationSelect?: (location: string) => void;
}

const LocationInput: React.FC<LocationInputProps> = ({
  field,
  isGoogleLoaded,
  apiKey,
  className = "",
  placeholder = "e.g., Chicago, IL",
  onLocationSelect,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const autocompleteRef = useRef<any>(null);

  // Initialize autocomplete when Google is loaded and input is available
  useEffect(() => {
    if (!isGoogleLoaded || !inputRef.current || !apiKey) return;

    // Clean up existing autocomplete if any
    if (autocompleteRef.current) {
      window.google.maps.event.clearInstanceListeners(autocompleteRef.current);
    }

    const autocomplete = new window.google.maps.places.Autocomplete(
      inputRef.current,
      {
        types: ["(cities)"], // Restrict to cities
        componentRestrictions: { country: "us" }, // Optional: restrict to US cities
      }
    );

    autocomplete.addListener("place_changed", () => {
      const place = autocomplete.getPlace();
      if (place.formatted_address || place.name) {
        const location = place.formatted_address || place.name;
        field.onChange(location);
        if (onLocationSelect) {
          onLocationSelect(location);
        }
      }
    });

    autocompleteRef.current = autocomplete;

    return () => {
      if (autocompleteRef.current) {
        window.google.maps.event.clearInstanceListeners(autocompleteRef.current);
        autocompleteRef.current = null;
      }
    };
  }, [isGoogleLoaded, apiKey, field, onLocationSelect]);

  return (
    <div className="relative">
      <input
        {...field}
        ref={(e) => {
          field.ref(e);
          (inputRef as any).current = e;
        }}
        type="text"
        placeholder={placeholder}
        className={className}
        autoComplete="off"
      />
      {!apiKey && (
        <p className="text-xs text-gray-500 mt-1">
          Note: Location autocomplete requires Google Places API key
        </p>
      )}
    </div>
  );
};

export const LocationAutocomplete: React.FC<LocationAutocompleteProps> = ({
  control,
  name,
  className = "",
  placeholder = "e.g., Chicago, IL",
  apiKey,
  onLocationSelect,
}) => {
  const [isGoogleLoaded, setIsGoogleLoaded] = useState(false);

  // Load Google Places API script
  useEffect(() => {
    if (!apiKey) {
      console.warn("Google Places API key not provided. Autocomplete will not work.");
      return;
    }

    // Check if already loaded
    if (window.google && window.google.maps && window.google.maps.places) {
      setIsGoogleLoaded(true);
      return;
    }

    // Check if script is already being loaded
    if (document.querySelector(`script[src*="maps.googleapis.com"]`)) {
      // Wait for it to load
      const checkInterval = setInterval(() => {
        if (window.google && window.google.maps && window.google.maps.places) {
          setIsGoogleLoaded(true);
          clearInterval(checkInterval);
        }
      }, 100);
      return () => clearInterval(checkInterval);
    }

    // Load the script
    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${apiKey}&libraries=places`;
    script.async = true;
    script.defer = true;
    script.onload = () => {
      setIsGoogleLoaded(true);
    };
    document.head.appendChild(script);
  }, [apiKey]);

  return (
    <Controller
      name={name}
      control={control}
      render={({ field }) => (
        <LocationInput
          field={field as any}
          isGoogleLoaded={isGoogleLoaded}
          apiKey={apiKey}
          className={className}
          placeholder={placeholder}
          onLocationSelect={onLocationSelect}
        />
      )}
    />
  );
};
