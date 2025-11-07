import React, { useState, useRef, useEffect } from "react";
import { Control, Controller } from "react-hook-form";
import { searchRaces, Race } from "@/data/popularRaces";

interface RaceNameAutocompleteProps {
  control: Control<any>;
  name: string;
  className?: string;
  placeholder?: string;
  onRaceSelect?: (race: Race) => void;
}

export const RaceNameAutocomplete: React.FC<RaceNameAutocompleteProps> = ({
  control,
  name,
  className = "",
  placeholder = "e.g., Chicago Marathon",
  onRaceSelect,
}) => {
  const suggestionsRef = useRef<HTMLDivElement>(null);


  return (
    <Controller
      name={name}
      control={control}
      render={({ field }) => {
        const [suggestions, setSuggestions] = useState<Race[]>([]);
        const [showSuggestions, setShowSuggestions] = useState(false);
        const [selectedIndex, setSelectedIndex] = useState(-1);
        const inputRef = useRef<HTMLInputElement>(null);

        // Update suggestions as user types
        useEffect(() => {
          if (field.value && field.value.trim()) {
            const results = searchRaces(field.value, 10);
            setSuggestions(results);
            setShowSuggestions(results.length > 0);
            setSelectedIndex(-1);
          } else {
            setSuggestions([]);
            setShowSuggestions(false);
          }
        }, [field.value]);

        // Close suggestions when clicking outside
        useEffect(() => {
          const handleClickOutside = (event: MouseEvent) => {
            if (
              suggestionsRef.current &&
              !suggestionsRef.current.contains(event.target as Node) &&
              inputRef.current &&
              !inputRef.current.contains(event.target as Node)
            ) {
              setShowSuggestions(false);
            }
          };

          document.addEventListener("mousedown", handleClickOutside);
          return () => document.removeEventListener("mousedown", handleClickOutside);
        }, []);

        const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
          field.onChange(e.target.value);
        };

        const handleSuggestionClick = (race: Race) => {
          field.onChange(race.name);
          setShowSuggestions(false);
          if (onRaceSelect) {
            onRaceSelect(race);
          }
        };

        const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
          if (!showSuggestions || suggestions.length === 0) return;

          switch (e.key) {
            case "ArrowDown":
              e.preventDefault();
              setSelectedIndex((prev) =>
                prev < suggestions.length - 1 ? prev + 1 : prev
              );
              break;
            case "ArrowUp":
              e.preventDefault();
              setSelectedIndex((prev) => (prev > 0 ? prev - 1 : -1));
              break;
            case "Enter":
              e.preventDefault();
              if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
                handleSuggestionClick(suggestions[selectedIndex]);
              }
              break;
            case "Escape":
              setShowSuggestions(false);
              setSelectedIndex(-1);
              break;
          }
        };

        return (
          <div className="relative">
            <input
              {...field}
              ref={(e) => {
                field.ref(e);
                (inputRef as any).current = e;
              }}
              type="text"
              value={field.value || ""}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              onFocus={() => {
                if (suggestions.length > 0) setShowSuggestions(true);
              }}
              placeholder={placeholder}
              className={className}
              autoComplete="off"
            />
            {showSuggestions && suggestions.length > 0 && (
              <div
                ref={suggestionsRef}
                className="absolute z-50 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-auto"
              >
                {suggestions.map((race, index) => (
                  <div
                    key={`${race.name}-${race.location}`}
                    onClick={() => handleSuggestionClick(race)}
                    className={`px-4 py-3 cursor-pointer hover:bg-blue-50 transition-colors ${
                      index === selectedIndex ? "bg-blue-100" : ""
                    } ${
                      index !== suggestions.length - 1 ? "border-b border-gray-100" : ""
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        <div className="font-medium text-gray-900">{race.name}</div>
                        <div className="text-sm text-gray-500">{race.location}</div>
                        {race.terrain && (
                          <div className="flex items-center gap-2 mt-1">
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                              {race.terrain}
                            </span>
                            {race.elevation_gain && (
                              <span className="text-xs text-gray-500">
                                {race.elevation_gain.toLocaleString()} ft gain
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      }}
    />
  );
};
