// src/pages/UserProfile.tsx
import React, { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useApiClient } from "@/utils/apiClient";
import { useAuthSetup } from "@/hooks/useAuthSetup";
import { AuthGuard } from "@/components/AuthGuard";
import { AgeGroupLabels, DayLabels, Days, AgeGroups } from "@/schemas/onboardingSchema";
import { useUnitSystem } from "@/context/UnitSystemContext";

const UserProfile: React.FC = () => {
  const { isReady, userId } = useAuthSetup();
  const api = useApiClient();
  const navigate = useNavigate();
  const { setUnitSystem } = useUnitSystem();

  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshingAutoHr, setRefreshingAutoHr] = useState(false);
  const [autoHrRefreshInfo, setAutoHrRefreshInfo] = useState<string | null>(null);

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
          console.log("No profile found - showing empty form for new user");
          // No profile exists - show empty form (new user)
          setProfile({});
        } else {
          setProfile(profileData);
        }
      } catch (e: any) {
        console.error("Error fetching profile:", e);
        // Check if it's a 404 (no profile exists) vs other error
        if (e.response?.status === 404) {
          console.log("404 - No profile found - showing empty form for new user");
          setProfile({});
        } else {
          // Other error - show empty form
          console.log("Error fetching profile - showing empty form");
          setProfile({});
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
    return null; // Loading
  }

  const isNewUser = Object.keys(profile).length === 0 || !profile.age_group;

  const handleEditField = (field: string) => {
    setEditingField(field);
  };

  const buildProfilePayload = (overrides: Record<string, unknown> = {}) => {
    const manual =
      profile.max_hr_manual != null ? profile.max_hr_manual : profile.max_hr;
    const base: Record<string, unknown> = {
      ageGroup: profile.age_group,
      trainingDays: profile.training_days,
      weight: profile.weight,
      max_hr_manual: manual,
      max_hr: manual,
      max_hr_active: profile.max_hr_active,
      unitSystem: profile.unit_system || "imperial",
      height: {
        feet: profile.height_feet || 5,
        inches: profile.height_inches || 0,
      },
      ...overrides,
    };
    return base;
  };

  const handleSaveField = async (field: string, value: any) => {
    setError(null);
    try {
      const payload: Record<string, unknown> = buildProfilePayload();

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
      } else if (field === "max_hr_manual") {
        payload.max_hr_manual = value;
        payload.max_hr = value;
      } else if (field === "unit_system") {
        payload.unitSystem = value;
      }

      console.log("Sending payload:", payload);

      // Send update to backend
      await api.post("/api/onboarding", payload);

      // If unit system was changed, update the context immediately
      if (field === "unit_system") {
        setUnitSystem(value);
      }

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
    } catch (e: unknown) {
      console.error("Error saving field:", e);
      const err = e as { response?: { data?: { message?: string } }; message?: string };
      setError(err.response?.data?.message || err.message || "Failed to save changes");
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

  const refreshAutoHrmax = async () => {
    setError(null);
    setAutoHrRefreshInfo(null);
    setRefreshingAutoHr(true);
    try {
      const postRes = await api.post("/api/heart-rate/hrmax/refresh-auto?force=true");
      const d = postRes.data?.data as
        | { updated?: boolean; reason?: string }
        | undefined;
      if (d?.updated) {
        setAutoHrRefreshInfo(null);
      } else if (d?.reason === "low_confidence") {
        setAutoHrRefreshInfo(
          "Not enough high-quality run data to estimate max HR from activities. Use your manual max HR from your watch or Strava."
        );
      } else if (d?.reason === "diverges_from_manual") {
        setAutoHrRefreshInfo(
          "The activity-based statistic doesn’t match your manual max HR, so it isn’t saved. Keep using manual for zones."
        );
      }
      const response = await api.get("/api/onboarding");
      if (response.data?.data) {
        setProfile(response.data.data);
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { error?: string } }; message?: string };
      setError(
        err.response?.data?.error ||
          err.message ||
          "Could not refresh activity-based max HR"
      );
    } finally {
      setRefreshingAutoHr(false);
    }
  };

  const saveMaxHrActive = async (next: "manual" | "auto") => {
    if (next === "auto" && profile.max_hr_auto == null) return;
    setError(null);
    try {
      const manual =
        profile.max_hr_manual != null ? profile.max_hr_manual : profile.max_hr;
      const payload = buildProfilePayload({
        max_hr_active: next,
        max_hr_manual: manual,
        max_hr: manual,
      });
      await api.post("/api/onboarding", payload);
      const response = await api.get("/api/onboarding");
      if (response.data?.data) {
        setProfile(response.data.data);
      }
    } catch (e: unknown) {
      console.error("Error saving max HR source:", e);
      const err = e as { response?: { data?: { message?: string } }; message?: string };
      setError(err.response?.data?.message || err.message || "Failed to save");
    }
  };

  const manualDisplay =
    profile.max_hr_manual != null ? profile.max_hr_manual : profile.max_hr;

  const manualZoneSourceChecked =
    profile.max_hr_active === "manual" ||
    (profile.max_hr_active == null && profile.max_hr_manual != null);
  const autoZoneSourceChecked =
    profile.max_hr_active === "auto" ||
    (profile.max_hr_active == null &&
      profile.max_hr_manual == null &&
      profile.max_hr_auto != null);

  return (
    <AuthGuard>
      <div className="max-w-2xl mx-auto mt-10 bg-white shadow-xl rounded-xl p-8 space-y-6 border">
        <div className="mb-4">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center text-gray-600 hover:text-gray-900 transition-colors"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back
          </button>
        </div>
        <div className="space-y-1 text-center">
          <h1 className="text-3xl font-bold text-gray-800">{isNewUser ? "Complete Your Profile" : "My Profile"}</h1>
          <p className="text-gray-500 text-sm">{isNewUser ? "Tell us a bit about yourself to get started" : "View and edit your profile information"}</p>
        </div>

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}
        {autoHrRefreshInfo && (
          <div className="bg-amber-50 border border-amber-200 text-amber-900 px-4 py-3 rounded text-sm">
            {autoHrRefreshInfo}
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
              label="Max HR (manual)"
              field="max_hr_manual"
              value={manualDisplay}
              editing={editingField === "max_hr_manual"}
              onEdit={() => handleEditField("max_hr_manual")}
              onSave={(value) => handleSaveField("max_hr_manual", value)}
              onCancel={handleCancelEdit}
              type="number"
              min={120}
              max={220}
              unit="bpm"
              isRequired={!profile.max_hr}
            />
            <div className="mb-4 pb-4 border-b border-gray-100">
              <div className="flex items-start gap-4">
                <div className="font-medium text-gray-700 w-32 flex-shrink-0">
                  Max HR (from activities):
                </div>
                <div className="flex-1 text-gray-900 flex flex-wrap items-center gap-2">
                  {profile.max_hr_auto != null ? (
                    <span>{profile.max_hr_auto} bpm</span>
                  ) : (
                    <span className="text-gray-400 italic">Not estimated yet</span>
                  )}
                  {profile.hrmax_confidence && profile.max_hr_auto != null && (
                    <span className="text-xs text-gray-500 ml-2">
                      ({profile.hrmax_confidence})
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => refreshAutoHrmax()}
                    disabled={refreshingAutoHr}
                    className="text-sm text-blue-600 hover:text-blue-800 underline disabled:opacity-50"
                  >
                    {refreshingAutoHr ? "Refreshing…" : "Refresh from activities"}
                  </button>
                </div>
              </div>
              <p className="text-xs text-gray-500 mt-2 ml-32 pl-0 max-w-md">
                Activity max HR is only shown when we have medium- or high-confidence data
                and it agrees with your manual max (within ~12 bpm). It is not the same
                as your watch or Strava max unless those line up.
              </p>
            </div>
            <div className="mb-4 pb-4 border-b border-gray-100">
              <div className="flex items-start gap-4">
                <div className="font-medium text-gray-700 w-32 flex-shrink-0">
                  Use for zones:
                </div>
                <div className="flex-1 space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="max_hr_active"
                      checked={manualZoneSourceChecked}
                      onChange={() => saveMaxHrActive("manual")}
                      className="text-blue-600"
                    />
                    <span>Manual entry</span>
                  </label>
                  <label
                    className={`flex items-center gap-2 ${profile.max_hr_auto == null ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
                  >
                    <input
                      type="radio"
                      name="max_hr_active"
                      disabled={profile.max_hr_auto == null}
                      checked={autoZoneSourceChecked}
                      onChange={() => saveMaxHrActive("auto")}
                      className="text-blue-600"
                    />
                    <span>Activity estimate</span>
                  </label>
                  {profile.max_hr != null && (
                    <p className="text-xs text-gray-500">
                      Effective max HR used for coaching:{" "}
                      <strong>{profile.max_hr} bpm</strong>
                    </p>
                  )}
                </div>
              </div>
            </div>
            <div className="mb-4 pb-4 border-b last:border-b-0">
              <div className="mt-2 space-y-2">
                <Link
                  to="/heart-rate-zones"
                  className="text-sm text-blue-600 hover:text-blue-800 underline flex items-center gap-1"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  What are HR zones?
                </Link>
                <Link
                  to="/pace-zones"
                  className="text-sm text-blue-600 hover:text-blue-800 underline flex items-center gap-1"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  What are pace zones?
                </Link>
              </div>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-2 mt-4">
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
              {profile.max_hr != null && (
                <p className="text-xs text-gray-500 mt-2">
                  ✓ HR zones in your plan use max HR of {profile.max_hr} bpm (
                  {profile.max_hr_active === "auto"
                    ? "activity estimate"
                    : "manual entry"}
                  ).
                </p>
              )}
            </div>
          </div>

          {/* Display Preferences Section */}
          <div className="border border-gray-200 rounded-lg p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">Display Preferences</h2>

            <InlineEditableField
              label="Unit System"
              field="unit_system"
              value={profile.unit_system || 'imperial'}
              editing={editingField === "unit_system"}
              onEdit={() => handleEditField("unit_system")}
              onSave={(value) => handleSaveField("unit_system", value)}
              onCancel={handleCancelEdit}
              type="select"
              options={[
                { value: 'imperial', label: 'Imperial (miles, min/mi)' },
                { value: 'metric', label: 'Metric (km, min/km)' }
              ]}
            />
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
    if (type === "height") {
      if (value && (value.height_feet || value.height_inches)) {
        const feet = value.height_feet || 0;
        const inches = value.height_inches || 0;
        return `${feet}'${inches}"`;
      }
      return <span className="text-gray-400 italic">Not set</span>;
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
    // Handle empty objects and falsy values
    if (!value || (typeof value === 'object' && Object.keys(value).length === 0)) {
      return <span className="text-gray-400 italic">Not set</span>;
    }
    return value;
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
