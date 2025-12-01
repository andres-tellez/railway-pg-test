// frontend/src/pages/PlansManagement.tsx

import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useApiClient } from "@/utils/apiClient";
import { useAuthSetup } from "@/hooks/useAuthSetup";
import { AuthGuard } from "@/components/AuthGuard";
import { format, parseISO } from "date-fns";

type Plan = {
  id: number;
  plan_name: string;
  race_date: string;
  race_distance: string;
  race_name?: string;
  race_location?: string;
  primary_goal?: string;
  target_time?: string;
  training_days?: string[];
  created_at: string;
  is_active: boolean;
};

const PlansManagement: React.FC = () => {
  const { isReady, userId } = useAuthSetup();
  const api = useApiClient();
  const navigate = useNavigate();

  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<number | null>(null);
  const [switching, setSwitching] = useState<number | null>(null);

  useEffect(() => {
    if (!isReady || !userId) return;

    const fetchPlans = async () => {
      try {
        setLoading(true);
        const response = await api.get("/api/plan/list");
        setPlans(response.data.plans || []);
      } catch (err: any) {
        console.error("Error fetching plans:", err);
        setError("Failed to load plans");
      } finally {
        setLoading(false);
      }
    };

    fetchPlans();
  }, [isReady, userId, api]);

  const handleSetActive = async (planId: number) => {
    try {
      setSwitching(planId);
      setError(null);
      await api.post(`/api/plan/${planId}/set-active`);

      // Reload plans to reflect the active state
      const response = await api.get("/api/plan/list");
      setPlans(response.data.plans || []);

      // Redirect to the plan overview
      navigate("/plan/overview");
    } catch (err: any) {
      setError(err.response?.data?.error || "Failed to activate plan");
      setSwitching(null);
    }
  };

  const handleDelete = async (planId: number) => {
    try {
      setError(null);
      await api.delete(`/api/plan/${planId}`);

      // Remove the deleted plan from the list
      setPlans(plans.filter(p => p.id !== planId));
    } catch (err: any) {
      setError(err.response?.data?.error || "Failed to delete plan");
    } finally {
      setConfirming(null);
    }
  };

  const getPlanDetails = (plan: Plan) => {
    const details = [];
    if (plan.primary_goal) details.push(`Goal: ${plan.primary_goal}`);
    if (plan.target_time) details.push(`Target: ${plan.target_time}`);
    return details.join(" • ");
  };

  if (loading) {
    return (
      <AuthGuard>
        <div className="p-8 text-center text-gray-600">Loading plans...</div>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gray-50 py-8">
        <div className="max-w-4xl mx-auto px-4">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">My Training Plans</h1>
            <p className="text-gray-600">Manage and switch between your training plans</p>
          </div>

          {error && (
            <div className="mb-6 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          {/* Create New Plan Button */}
          <div className="mb-6">
            <button
              onClick={() => navigate("/plan/new")}
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Create New Plan
            </button>
          </div>

          {/* Plans List */}
          {plans.length === 0 ? (
            <div className="bg-white rounded-lg shadow-sm p-8 text-center">
              <p className="text-gray-600 mb-4">You don't have any training plans yet.</p>
              <button
                onClick={() => navigate("/plan/new")}
                className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-2 text-white hover:bg-blue-700 transition-colors"
              >
                Create Your First Plan
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {plans.map((plan) => (
                <div
                  key={plan.id}
                  className={`bg-white rounded-lg shadow-sm border-2 ${
                    plan.is_active ? "border-blue-500" : "border-gray-200"
                  } p-6`}
                >
                  <div className="flex items-start justify-between">
                    {/* Plan Info */}
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h2 className="text-xl font-semibold text-gray-900">
                          {plan.plan_name || `Training Plan - ${format(parseISO(plan.race_date), "MMM d, yyyy")}`}
                        </h2>
                        {plan.is_active && (
                          <span className="bg-blue-100 text-blue-700 px-3 py-1 rounded-full text-xs font-semibold">
                            Active
                          </span>
                        )}
                      </div>

                      <div className="space-y-1 text-sm text-gray-600">
                        <div>
                          <span className="font-semibold">Race:</span> {plan.race_distance} on{" "}
                          {format(parseISO(plan.race_date), "MMMM d, yyyy")}
                        </div>
                        {plan.race_name && (
                          <div>
                            <span className="font-semibold">Race Name:</span> {plan.race_name}
                          </div>
                        )}
                        {plan.race_location && (
                          <div>
                            <span className="font-semibold">Location:</span> {plan.race_location}
                          </div>
                        )}
                        {getPlanDetails(plan) && (
                          <div className="text-xs text-gray-500 mt-2">{getPlanDetails(plan)}</div>
                        )}
                        <div className="text-xs text-gray-400">
                          Created {format(parseISO(plan.created_at), "MMM d, yyyy")}
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex flex-col gap-2 ml-4">
                      {!plan.is_active && (
                        <button
                          onClick={() => handleSetActive(plan.id)}
                          disabled={switching === plan.id}
                          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 text-sm font-medium whitespace-nowrap"
                        >
                          {switching === plan.id ? "Activating..." : "Make Active"}
                        </button>
                      )}
                      <button
                        onClick={() => navigate(`/plan/overview`)}
                        className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm font-medium whitespace-nowrap"
                      >
                        {plan.is_active ? "View Plan" : "View"}
                      </button>
                      {confirming === plan.id ? (
                        <div className="flex flex-col gap-2">
                          <p className="text-xs text-red-600 font-semibold">Confirm delete?</p>
                          <div className="flex gap-1">
                            <button
                              onClick={() => handleDelete(plan.id)}
                              className="px-3 py-1.5 bg-red-600 text-white rounded text-xs font-medium hover:bg-red-700"
                            >
                              Yes
                            </button>
                            <button
                              onClick={() => setConfirming(null)}
                              className="px-3 py-1.5 bg-gray-200 text-gray-700 rounded text-xs font-medium hover:bg-gray-300"
                            >
                              No
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirming(plan.id)}
                          className="px-4 py-2 border border-red-300 text-red-600 rounded-lg hover:bg-red-50 transition-colors text-sm font-medium whitespace-nowrap"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AuthGuard>
  );
};

export default PlansManagement;
