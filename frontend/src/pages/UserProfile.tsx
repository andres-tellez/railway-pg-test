// src/pages/UserProfile.tsx
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApiClient } from "@/utils/apiClient";
import { useAuthSetup } from "@/hooks/useAuthSetup";
import { AuthGuard } from "@/components/AuthGuard";
import { AgeGroupLabels, DayLabels, Days, Motivations, MotivationLabels, AgeGroups } from "@/schemas/onboardingSchema";

const UserProfile: React.FC = () => {
  const { isReady, userId } = useAuthSetup();
  const api = useApiClient();
  const navigate = useNavigate();

  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isReady || !userId) return;

    const fetchProfile = async () => {
      try {
        console.log("Fetching profile for /profile page...");
        const response = await api.get("/api/onboarding");
        console.log("Profile response received:", response);
        // Backend returns {status: "success", data: profile_dict}
        const profileData = response.data?.data;
        console.log("Profile data:", profileData);
        if (!profileData) {
          console.log("No profile found - redirecting to /onboarding");
          // No profile exists - redirect to create profile
          navigate("/onboarding", { replace: true });
          return;
        }
        setProfile(profileData);
      } catch (e: any) {
        console.error("Error fetching profile:", e);
        // Check if it's a 404 (no profile exists) vs other error
        if (e.response?.status === 404) {
          console.log("404 - No profile found - redirecting to /onboarding");
          navigate("/onboarding", { replace: true });
        } else {
          // Other error - don't redirect, just set profile to null
          console.log("Error fetching profile, but not redirecting");
          setProfile(null);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchProfile();
  }, [isReady, userId]); // Removed api and navigate from dependencies

  if (loading) {
    return (
      <AuthGuard>
        <div className="p-8 text-center text-gray-600">⏳ Loading profile…</div>
      </AuthGuard>
    );
  }

  if (!profile) {
    return null; // Will redirect
  }

  const handleEditField = (field: string) => {
    setEditingField(field);
  };

  const handleSaveField = async (field: string, value: any) => {
    setError(null);
    try {
      // Prepare the payload to send to backend - send full profile with updated field
      const payload: any = {};

      // Copy all existing profile fields with proper field name mapping
      payload.ageGroup = profile.age_group;
      payload.trainingDays = profile.training_days;
      payload.weight = profile.weight;
      payload.max_hr = profile.max_hr;
      payload.motivation = profile.motivation;
      payload.height = {
        feet: profile.height_feet || 5,
        inches: profile.height_inches || 0,
      };

      // Update the specific field being changed
      if (field === "height") {
        payload.height = {
          feet: value.height_feet,
          inches: value.height_inches,
        };
      } else if (field === "age_group") {
        payload.ageGroup = value;
      } else if (field === "training_days") {
        payload.trainingDays = value;
      } else if (field === "weight") {
        payload.weight = value;
      } else if (field === "motivation") {
        payload.motivation = value;
      } else if (field === "max_hr") {
        payload.max_hr = value;
      }

      console.log("Sending payload:", payload);

      // Send update to backend
      await api.post("/api/onboarding", payload);

      // Refresh profile from server to ensure we have the latest data
      const response = await api.get("/api/onboarding");
      if (response.data?.data) {
        setProfile(response.data.data);
      } else {
        // Fallback: update local state if server response is unexpected
        if (field === "height") {
          setProfile({ ...profile, height_feet: value.height_feet, height_inches: value.height_inches });
        } else if (field === "height_feet") {
          setProfile({ ...profile, height_feet: value });
        } else if (field === "height_inches") {
          setProfile({ ...profile, height_inches: value });
        } else {
          setProfile({ ...profile, [field]: value });
        }
      }

      setEditingField(null);
    } catch (e: any) {
      console.error("Error saving field:", e);
      setError(e.response?.data?.message || e.message || "Failed to save changes");
      // Revert on error
      const response = await api.get("/api/onboarding");
      if (response.data?.data) {
        setProfile(response.data.data);
      }
    }
  };

  const handleCancelEdit = () => {
    setEditingField(null);
  };


  return (
    <AuthGuard>
      <div className="max-w-2xl mx-auto mt-10 bg-white shadow-xl rounded-xl p-8 space-y-6 border">
        <div className="space-y-1 text-center">
          <h1 className="text-3xl font-bold text-gray-800">My Profile</h1>
          <p className="text-gray-500 text-sm">View and edit your profile information</p>
        </div>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}

        <div className="space-y-6">
          {/* Physical Stats Section */}
          <div className="border border-gray-200 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">Physical Stats</h2>

            <InlineEditableField
              label="Age Group"
              field="age_group"
              value={profile.age_group}
              editing={editingField === "age_group"}
              onEdit={() => handleEditField("age_group")}
              onSave={(value) => handleSaveField("age_group", value)}
              onCancel={handleCancelEdit}
              type="select"
              options={AgeGroups.map(ag => ({
                value: ag,
                label: AgeGroupLabels[ag as keyof typeof AgeGroupLabels]
              }))}
            />

            <InlineEditableField
              label="Height"
              field="height"
              value={profile}
              editing={editingField === "height"}
              onEdit={() => handleEditField("height")}
              onSave={(value) => handleSaveField("height", value)}
              onCancel={handleCancelEdit}
              type="height"
            />

            <InlineEditableField
              label="Weight"
              field="weight"
              value={profile.weight}
              editing={editingField === "weight"}
              onEdit={() => handleEditField("weight")}
              onSave={(value) => handleSaveField("weight", value)}
              onCancel={handleCancelEdit}
              type="number"
              min={80}
              max={400}
              unit="lbs"
            />

            <InlineEditableField
              label="Max Heart Rate"
              field="max_hr"
              value={profile.max_hr}
              editing={editingField === "max_hr"}
              onEdit={() => handleEditField("max_hr")}
              onSave={(value) => handleSaveField("max_hr", value)}
              onCancel={handleCancelEdit}
              type="number"
              min={120}
              max={220}
              unit="bpm"
              isRequired={!profile.max_hr}
            />
            <div className="mb-4 pb-4 border-b last:border-b-0">
              <div className="flex items-start gap-4">
                <span className="font-medium text-gray-700 w-32 flex-shrink-0"></span>
                <div className="flex-1">
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-2">
                    <p className="text-sm text-blue-900 font-medium mb-1">
                      How to find your Max HR in Strava:
                    </p>
                    <ol className="text-xs text-blue-800 list-decimal list-inside space-y-1 ml-2">
                      <li>Go to <strong>Strava.com</strong> and log in</li>
                      <li>Click your profile picture → <strong>Settings</strong></li>
                      <li>Go to <strong>My Performance</strong> → <strong>Heart Rate Zones</strong></li>
                      <li>Look for <strong>"Based on Max Heart Rate"</strong> - that's your value</li>
                      <li>Enter that number (e.g., 185) in the field above</li>
                    </ol>
                  </div>
                  <p className="text-sm text-gray-600 mt-2">
                    <strong>Note:</strong> Strava API doesn't provide this value, so manual entry is required.
                  </p>
                  {profile.max_hr && (
                    <p className="text-xs text-gray-500 mt-2">
                      ✓ HR zones in your plan will use this max HR value ({profile.max_hr} bpm).
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AuthGuard>
  );
};

interface InlineEditableFieldProps {
  label: string;
  field: string;
  value: any;
  editing: boolean;
  onEdit: () => void;
  onSave: (value: any) => void;
  onCancel: () => void;
  type: "text" | "number" | "select" | "multiselect" | "height";
  options?: Array<{ value: string; label: string }>;
  min?: number;
  max?: number;
  unit?: string;
  isRequired?: boolean;
}

const InlineEditableField: React.FC<InlineEditableFieldProps> = ({
  label,
  field,
  value,
  editing,
  onEdit,
  onSave,
  onCancel,
  type,
  options = [],
  min,
  max,
  unit,
  isRequired = false,
}) => {
  const [tempValue, setTempValue] = useState<any>(value);

  React.useEffect(() => {
    if (editing) {
      setTempValue(value);
    }
  }, [editing, value]);

  const handleSave = () => {
    onSave(tempValue);
  };

  const renderDisplayValue = () => {
    if (type === "height" && value && (value.height_feet || value.height_inches)) {
      const feet = value.height_feet || 0;
      const inches = value.height_inches || 0;
      return `${feet}'${inches}"`;
    }
    if (type === "number" && value !== null && value !== undefined) {
      return unit ? `${value} ${unit}` : value;
    }
    if (type === "multiselect" && Array.isArray(value) && value.length > 0) {
      return value.join(", ");
    }
    if (type === "select" && value) {
      const option = options.find(opt => opt.value === value);
      return option ? option.label : value;
    }
    // For missing values, show placeholder-style text
    // Use subtle orange/red for required fields to indicate needs attention (not an error)
    if (!value && isRequired) {
      return <span className="text-orange-600 italic">Not specified</span>;
    }
    return value || <span className="text-gray-400 italic">Not set</span>;
  };

  const renderEditField = () => {
    if (type === "height") {
      return (
        <div className="flex gap-2 items-center">
          <input
            type="number"
            min={3}
            max={8}
            value={tempValue?.height_feet || ""}
            onChange={(e) => setTempValue({ ...tempValue, height_feet: parseInt(e.target.value) })}
            className="border p-1 rounded w-16"
            placeholder="Feet"
          />
          <span>ft</span>
          <input
            type="number"
            min={0}
            max={11}
            value={tempValue?.height_inches || ""}
            onChange={(e) => setTempValue({ ...tempValue, height_inches: parseInt(e.target.value) })}
            className="border p-1 rounded w-16"
            placeholder="Inches"
          />
          <span>in</span>
        </div>
      );
    }

    if (type === "number") {
      return (
        <div className="flex gap-2 items-center">
          <input
            type="number"
            min={min}
            max={max}
            value={tempValue || ""}
            onChange={(e) => setTempValue(parseInt(e.target.value))}
            className="border p-1 rounded w-32"
          />
          {unit && <span>{unit}</span>}
        </div>
      );
    }

    if (type === "select") {
      return (
        <select
          value={tempValue || ""}
          onChange={(e) => setTempValue(e.target.value)}
          className="border p-1 rounded"
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      );
    }

    if (type === "multiselect") {
      return (
        <div className="space-y-2 max-h-40 overflow-y-auto border p-2 rounded">
          {options.map((opt) => (
            <label key={opt.value} className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={Array.isArray(tempValue) && tempValue.includes(opt.value)}
                onChange={(e) => {
                  const arr = Array.isArray(tempValue) ? [...tempValue] : [];
                  if (e.target.checked) {
                    arr.push(opt.value);
                  } else {
                    const index = arr.indexOf(opt.value);
                    if (index > -1) arr.splice(index, 1);
                  }
                  setTempValue(arr);
                }}
              />
              <span>{opt.label}</span>
            </label>
          ))}
        </div>
      );
    }

    return (
      <input
        type="text"
        value={tempValue || ""}
        onChange={(e) => setTempValue(e.target.value)}
        className="border p-1 rounded"
      />
    );
  };

  return (
    <div className="mb-4 pb-4 border-b last:border-b-0">
      <div className="flex items-start gap-4">
        <div className="font-medium text-gray-700 w-32 flex-shrink-0">
          <span>{label}:</span>
        </div>

        {editing ? (
          <div className="flex-1">
            {renderEditField()}
            <div className="flex gap-2 mt-2">
              <button
                onClick={handleSave}
                className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 transition"
              >
                Save
              </button>
              <button
                onClick={onCancel}
                className="px-3 py-1 text-sm bg-gray-300 text-gray-700 rounded hover:bg-gray-400 transition"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-between">
            <span className="text-gray-900">
              {renderDisplayValue()}
            </span>
            <button
              onClick={onEdit}
              className="text-sm text-blue-600 hover:text-blue-800 ml-4"
            >
              Edit
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default UserProfile;
