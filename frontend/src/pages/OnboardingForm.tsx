// src/pages/OnboardingForm.tsx
import React, { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { authFetchJSON } from "@/utils/authFetch";

type Profile = {
  runner_level?: string;
  race_history?: boolean;
  race_date?: string | null;
  race_distance?: string | null;
  past_races?: string[];
  heightFeet?: number;     // UI only (server normalizes to height.feet)
  heightInches?: number;   // UI only (server normalizes to height.inches)
  weight?: number | null;
  training_days?: string[];
  main_goal?: string | null;
  motivation?: string[];
  age_group?: string | null;
  longestRun?: number | null;   // server maps to longest_run
  run_preference?: string | null;
};

const OnboardingForm: React.FC = () => {
  const { getAccessTokenSilently, isAuthenticated } = useAuth0();
  const navigate = useNavigate();
  const ran = useRef(false);

  const [form, setForm] = useState<Profile>({
    runner_level: "",
    race_history: false,
    race_date: "",
    race_distance: "",
    past_races: [],
    heightFeet: undefined,
    heightInches: undefined,
    weight: undefined,
    training_days: [],
    main_goal: "",
    motivation: [],
    age_group: "",
    longestRun: undefined,
    run_preference: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Stable token getter for authFetchJSON
  const getToken = useCallback(
    () =>
      getAccessTokenSilently({
        authorizationParams: {
          audience: import.meta.env.VITE_AUTH0_AUDIENCE,
          scope: "openid profile email offline_access",
        },
      }),
    [getAccessTokenSilently]
  );

  // Load existing profile (server uses token.sub; no querystring)
  useEffect(() => {
    if (!isAuthenticated || ran.current) return;
    ran.current = true;

    const ac = new AbortController();
    (async () => {
      try {
        setLoading(true);
        setError(null);

        const { res, json } = await authFetchJSON<{ status: string; data?: any }>(
          "/api/onboarding",
          getToken,
          { signal: ac.signal }
        );

        if (res.status === 404) {
          // Not onboarded yet; keep defaults
          setLoading(false);
          return;
        }
        if (!res.ok) throw new Error(`GET /api/onboarding ${res.status}`);

        const data = json?.data ?? {};
        setForm((prev) => ({
          ...prev,
          runner_level: data.runner_level ?? "",
          race_history: !!data.race_history,
          race_date: data.race_date ?? "",
          race_distance: data.race_distance ?? "",
          past_races: data.past_races ?? [],
          heightFeet: data.height_feet ?? undefined,
          heightInches: data.height_inches ?? undefined,
          weight: data.weight ?? undefined,
          training_days: data.training_days ?? [],
          main_goal: data.main_goal ?? "",
          motivation: data.motivation ?? [],
          age_group: data.age_group ?? "",
          longestRun: data.longest_run ?? undefined,
          run_preference: data.run_preference ?? "",
        }));

        setLoading(false);
      } catch (e: any) {
        if (e?.name === "AbortError") return;
        setError(e?.message || "Failed to load profile");
        setLoading(false);
      }
    })();

    return () => ac.abort();
  }, [isAuthenticated, getToken]);

  // Submit → POST /api/onboarding (server uses token.sub; DO NOT send user_id)
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const payload: Record<string, any> = { ...form };
      // (Optional) If your UI stores strings for numbers, coerce here.

      const { res, json } = await authFetchJSON(
        "/api/onboarding",
        getToken,
        { method: "POST", body: JSON.stringify(payload) }
      );

      if (!res.ok) {
        const msg =
          json?.message ||
          (json?.errors ? JSON.stringify(json.errors) : `save failed ${res.status}`);
        throw new Error(msg);
      }

      navigate("/dashboard", { replace: true });
    } catch (e: any) {
      setError(e?.message || "Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  // ------- Render (replace with your real fields/UI) -------
  if (loading) return <div className="p-8">Loading profile…</div>;

  return (
    <form className="p-8 space-y-4 max-w-xl" onSubmit={handleSubmit}>
      <h1 className="text-2xl font-bold">Onboarding</h1>

      {error && (
        <div className="p-3 rounded border border-red-300 bg-red-50 text-red-700">
          {error}
        </div>
      )}

      <div>
        <label className="block text-sm mb-1">Runner Level</label>
        <input
          className="border px-2 py-1 w-full"
          value={form.runner_level || ""}
          onChange={(e) => setForm({ ...form, runner_level: e.target.value })}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-sm mb-1">Height (ft)</label>
          <input
            className="border px-2 py-1 w-full"
            type="number"
            value={form.heightFeet ?? ""}
            onChange={(e) =>
              setForm({ ...form, heightFeet: e.target.value === "" ? undefined : Number(e.target.value) })
            }
          />
        </div>
        <div>
          <label className="block text-sm mb-1">Height (in)</label>
          <input
            className="border px-2 py-1 w-full"
            type="number"
            value={form.heightInches ?? ""}
            onChange={(e) =>
              setForm({ ...form, heightInches: e.target.value === "" ? undefined : Number(e.target.value) })
            }
          />
        </div>
      </div>

      {/* Add the rest of your fields here (dates, enums, multi-selects, etc.) */}

      <button
        className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-60"
        disabled={saving}
        type="submit"
      >
        {saving ? "Saving…" : "Save & Continue"}
      </button>
    </form>
  );
};

export default OnboardingForm;
