import React, { useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";


const API = (import.meta as any).env.VITE_BACKEND_URL;

export default function AskGptMvpUI() {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState("");
const [loading, setLoading] = useState(false);
  const [readinessData, setReadinessData] = useState<any>(null);
  const [trainingProfileData, setTrainingProfileData] = useState<any>(null);
  const [structuredPlanData, setStructuredPlanData] = useState<any>(null);
  const [fourStagePlanData, setFourStagePlanData] = useState<any>(null);
  const [vdotEstimationData, setVdotEstimationData] = useState<any>(null);
  const [gptProfileNormalizationData, setGptProfileNormalizationData] = useState<any>(null);
  const [gptPlanGenerationData, setGptPlanGenerationData] = useState<any>(null);
  const { getAccessTokenSilently } = useAuth0();

  const handleAsk = async () => {
    if (!question.trim()) return;
    setLoading(true);
    setResponse("");

    try {
      const token = await getAccessTokenSilently();
      const res = await fetch(`${API}/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({ question }),
      });

      const data = await res.json();
      setResponse(data.response || data.error || "No response returned.");
    } catch (err) {
      console.error("Error:", err);
      setResponse("❌ Error contacting backend.");
    } finally {
      setLoading(false);
    }
  };

  const handleReadinessTest = async () => {
    setLoading(true);
    setReadinessData(null);

    try {
      const token = await getAccessTokenSilently();
      const user_id = localStorage.getItem("user_id");
      
      console.log("🔍 Frontend Debug:");
      console.log("  • API URL:", `${API}/api/plan/readiness-assessment`);
      console.log("  • User ID:", user_id);
      console.log("  • Token length:", token?.length || 0);
      
      if (!user_id) {
        setReadinessData({ error: "User ID not found. Please refresh the page and try again." });
        return;
      }

      console.log("📡 Making request...");
      const res = await fetch(`${API}/api/plan/readiness-assessment`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`,
          "X-User-Id": user_id,
        },
      });

      console.log("📡 Response status:", res.status);
      console.log("📡 Response headers:", Object.fromEntries(res.headers.entries()));

      const data = await res.json();
      console.log("📡 Response data:", data);
      
      if (data.success) {
        // Handle new structure with summary/debug split
        const assessment = data.readiness_assessment;
        if (assessment.summary) {
          // New structure: use summary for display, debug for console
          console.log("📊 Debug data:", assessment.debug);
          setReadinessData(assessment.summary);
        } else {
          // Fallback for old structure
          setReadinessData(assessment);
        }
      } else {
        setReadinessData({ error: data.error || "Failed to get readiness assessment" });
      }
    } catch (err) {
      console.error("❌ Frontend Error:", err);
      setReadinessData({ error: "❌ Error contacting backend." });
    } finally {
      setLoading(false);
    }
  };

  const handleTrainingProfileTest = async () => {
    setLoading(true);
    setTrainingProfileData(null);

    try {
      const token = await getAccessTokenSilently();
      const user_id = localStorage.getItem("user_id");
      
      console.log("🔍 Frontend Debug (Stage 2):");
      console.log("  • API URL:", `${API}/api/plan/training-profile`);
      console.log("  • User ID:", user_id);
      
      if (!user_id) {
        setTrainingProfileData({ error: "User ID not found. Please refresh the page and try again." });
        return;
      }

      console.log("📡 Making Stage 2 request...");
      const res = await fetch(`${API}/api/plan/training-profile`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`,
          "X-User-Id": user_id,
        },
      });

      console.log("📡 Response status:", res.status);
      const data = await res.json();
      console.log("📡 Stage 2 Response data:", data);
      
      if (data.success) {
        setTrainingProfileData({
          stage1: data.stage1_readiness,
          stage2: data.stage2_training_profile
        });
      } else {
        setTrainingProfileData({ error: data.error || "Failed to get training profile" });
      }
    } catch (err) {
      console.error("❌ Frontend Error:", err);
      setTrainingProfileData({ error: "❌ Error contacting backend." });
    } finally {
      setLoading(false);
    }
  };

  const handleStructuredPlanTest = async () => {
    setLoading(true);
    setStructuredPlanData(null);

    try {
      const token = await getAccessTokenSilently();
      const user_id = localStorage.getItem("user_id");
      
      console.log("🔍 Frontend Debug (Stage 3):");
      console.log("  • API URL:", `${API}/api/plan/structured-plan`);
      console.log("  • User ID:", user_id);
      
      if (!user_id) {
        setStructuredPlanData({ error: "User ID not found. Please refresh the page and try again." });
        return;
      }

      console.log("📡 Making Stage 3 request...");
      const res = await fetch(`${API}/api/plan/structured-plan`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`,
          "X-User-Id": user_id,
        },
      });

      console.log("📡 Response status:", res.status);
      const data = await res.json();
      console.log("📡 Stage 3 Response data:", data);
      
      if (data.success) {
        setStructuredPlanData({
          stage1: data.stage1_readiness,
          stage2: data.stage2_training_profile,
          stage3_4: data.stage3_4_structured_plan
        });
      } else {
        setStructuredPlanData({ error: data.error || "Failed to get structured plan" });
      }
    } catch (err) {
      console.error("❌ Frontend Error:", err);
      setStructuredPlanData({ error: "❌ Error contacting backend." });
    } finally {
      setLoading(false);
    }
  };

  const handleFourStagePlanGeneration = async () => {
    setLoading(true);
    setFourStagePlanData(null);

    try {
      const token = await getAccessTokenSilently();
      const user_id = localStorage.getItem("user_id");
      
      console.log("🚀 Frontend Debug (Four-Stage Plan):");
      console.log("  • API URL:", `${API}/api/plan/four-stage-plan`);
      console.log("  • User ID:", user_id);
      
      if (!user_id) {
        setFourStagePlanData({ error: "User ID not found. Please refresh the page and try again." });
        return;
      }

      // Get race date from user profile or use a default
      const raceDate = "2025-12-07"; // You could make this dynamic
      const raceDistance = "Marathon";
      
      console.log("📡 Making Four-Stage Plan request...");
      const res = await fetch(`${API}/api/plan/four-stage-plan`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "X-User-Id": user_id,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          race_date: raceDate,
          race_distance: raceDistance
        })
      });

      console.log("📡 Response status:", res.status);
      const data = await res.json();
      console.log("📡 Four-Stage Plan Response data:", data);
      
      if (data.success) {
        setFourStagePlanData(data);
        // Optionally redirect to the plan view
        if (data.plan_id) {
          console.log("🎉 Plan created! ID:", data.plan_id);
          // Redirect to plan overview page
          window.location.href = `/plan/overview`;
        }
      } else {
        setFourStagePlanData({ error: data.error || "Failed to generate four-stage plan" });
      }
    } catch (err) {
      console.error("❌ Frontend Error:", err);
      setFourStagePlanData({ error: "❌ Error contacting backend." });
    } finally {
      setLoading(false);
    }
  };

  const handleVdotEstimation = async () => {
    setLoading(true);
    setVdotEstimationData(null);
    
    try {
      const token = await getAccessTokenSilently();
      const user_id = localStorage.getItem("user_id");
      
      console.log("🏃 VDOT Estimation request details:");
      console.log("  • API URL:", `${API}/api/plan/vdot-estimation`);
      console.log("  • User ID:", user_id);
      
      if (!user_id) {
        setVdotEstimationData({ error: "User ID not found. Please refresh the page and try again." });
        return;
      }

      console.log("📡 Making VDOT Estimation request...");
      const res = await fetch(`${API}/api/plan/vdot-estimation`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`,
          "X-User-Id": user_id,
        }
      });

      console.log("📡 Response status:", res.status);
      const data = await res.json();
      console.log("📡 VDOT Estimation Response data:", data);
      
      if (data.success) {
        setVdotEstimationData(data);
      } else {
        setVdotEstimationData({ error: data.error || "Failed to get VDOT estimation" });
      }
    } catch (err) {
      console.error("❌ Frontend Error:", err);
      setVdotEstimationData({ error: "❌ Error contacting backend." });
    } finally {
      setLoading(false);
    }
  };

  const handleGptProfileNormalization = async () => {
    setLoading(true);
    setGptProfileNormalizationData(null);
    
    try {
      const token = await getAccessTokenSilently();
      const user_id = localStorage.getItem("user_id");
      
      console.log("📊 GPT Profile Normalization request details:");
      console.log("  • API URL:", `${API}/api/plan/gpt-profile-normalization`);
      console.log("  • User ID:", user_id);
      
      if (!user_id) {
        setGptProfileNormalizationData({ error: "User ID not found. Please refresh the page and try again." });
        return;
      }

      console.log("📡 Making GPT Profile Normalization request...");
      const res = await fetch(`${API}/api/plan/gpt-profile-normalization`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`,
          "X-User-Id": user_id,
        }
      });

      console.log("📡 Response status:", res.status);
      const data = await res.json();
      console.log("📡 GPT Profile Normalization Response data:", data);
      
      if (data.success) {
        setGptProfileNormalizationData(data);
      } else {
        setGptProfileNormalizationData({ error: data.error || "Failed to get profile normalization" });
      }
    } catch (err) {
      console.error("❌ Frontend Error:", err);
      setGptProfileNormalizationData({ error: "❌ Error contacting backend." });
    } finally {
      setLoading(false);
    }
  };

  const handleGptPlanGeneration = async () => {
    setLoading(true);
    setGptPlanGenerationData(null);
    
    try {
      const token = await getAccessTokenSilently();
      const user_id = localStorage.getItem("user_id");
      
      console.log("📅 GPT Plan Generation request details:");
      console.log("  • API URL:", `${API}/api/plan/gpt-plan-generation`);
      console.log("  • User ID:", user_id);
      
      if (!user_id) {
        setGptPlanGenerationData({ error: "User ID not found. Please refresh the page and try again." });
        return;
      }

      // Get race details (same as 4-stage plan)
      const raceDate = "2025-12-07";
      const raceDistance = "Marathon";

      console.log("📡 Making GPT Plan Generation request...");
      const res = await fetch(`${API}/api/plan/gpt-plan-generation`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "X-User-Id": user_id,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          race_date: raceDate,
          race_distance: raceDistance
        })
      });

      console.log("📡 Response status:", res.status);
      const data = await res.json();
      console.log("📡 GPT Plan Generation Response data:", data);
      
      if (data.success) {
        setGptPlanGenerationData(data);
        // Redirect to plan view if plan was saved
        if (data.plan_id) {
          console.log("🎉 GPT plan created! ID:", data.plan_id);
          // Redirect to plan overview page
          window.location.href = `/plan/overview`;
        }
      } else {
        setGptPlanGenerationData({ error: data.error || "Failed to generate plan" });
      }
    } catch (err) {
      console.error("❌ Frontend Error:", err);
      setGptPlanGenerationData({ error: "❌ Error contacting backend." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto mt-10 p-4">
      <div className="border rounded-xl shadow-xl p-6 bg-white">
        <h1 className="text-2xl font-bold mb-4">SmartCoach Ask</h1>
        <textarea
          placeholder="Ask a question about your training week..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="w-full min-h-[100px] p-2 border rounded-lg mb-4"
        />
        <div className="flex gap-2 mb-4 flex-wrap">
          <button
            onClick={handleAsk}
            disabled={loading}
            className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            {loading ? "Loading..." : "Ask CoachGPT"}
          </button>
          <button
            onClick={handleReadinessTest}
            disabled={loading}
            className="bg-green-600 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            🏃 Stage 1: Readiness
          </button>
          <button
            onClick={handleTrainingProfileTest}
            disabled={loading}
            className="bg-purple-600 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            🏗️ Stage 2: Training Profile
          </button>
          <button
            onClick={handleStructuredPlanTest}
            disabled={loading}
            className="bg-orange-600 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            🎯 Stage 3+4: Pace-Aware Plan
          </button>
          <button
            onClick={handleFourStagePlanGeneration}
            disabled={loading}
            className="bg-purple-600 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            🚀 Generate Complete Plan (4-Stage)
          </button>
          <button
            onClick={handleVdotEstimation}
            disabled={loading}
            className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            🧮 GPT Fitness Analysis
          </button>
          <button
            onClick={handleGptProfileNormalization}
            disabled={loading}
            className="bg-teal-600 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            ⚙️ GPT Profile Normalization
          </button>
          <button
            onClick={handleGptPlanGeneration}
            disabled={loading}
            className="bg-indigo-600 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            📅 GPT Complete Plan
          </button>
        </div>
        {response && (
          <div className="mt-4 bg-gray-50 p-4 rounded-xl border text-sm whitespace-pre-line">
            {response}
          </div>
        )}
        {readinessData && (
          <div className="mt-4 bg-green-50 p-4 rounded-xl border border-green-200">
            <h3 className="font-bold mb-2">🏃 Stage 1: Athlete Readiness Assessment</h3>
            {readinessData.error ? (
              <p className="text-red-600">{readinessData.error}</p>
            ) : (
              <div className="text-sm space-y-1">
                <p><strong>Readiness Index:</strong> {readinessData.readiness_index} / 100</p>
                <p><strong>Category:</strong> {readinessData.category}</p>
                <p><strong>Recommendation:</strong> {readinessData.recommendation}</p>
                <p><strong>Base Mileage:</strong> {readinessData.base_mileage} mi/week</p>
                <p><strong>Longest Run:</strong> {readinessData.longest_run} mi</p>
                <p><strong>Consistency:</strong> {readinessData.consistency_score}%</p>
                <p><strong>HR Distribution:</strong> {readinessData.pct_easy}% easy, {readinessData.pct_threshold}% threshold, {readinessData.pct_hard}% hard</p>
                <p className="text-xs text-gray-500 mt-2">✅ Check Flask logs for detailed breakdown</p>
              </div>
            )}
          </div>
        )}

        {trainingProfileData && (
          <div className="mt-4 bg-purple-50 p-4 rounded-xl border border-purple-200">
            <h3 className="font-bold mb-2">🏗️ Stage 2: Training Profile Normalization</h3>
            {trainingProfileData.error ? (
              <p className="text-red-600">{trainingProfileData.error}</p>
            ) : (
              <div className="text-sm space-y-1">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <h4 className="font-semibold text-green-700 mb-1">Stage 1 Summary:</h4>
                    <p><strong>Category:</strong> {trainingProfileData.stage1?.summary?.category || trainingProfileData.stage1?.category}</p>
                    <p><strong>Readiness:</strong> {trainingProfileData.stage1?.summary?.readiness_index || trainingProfileData.stage1?.readiness_index} / 100</p>
                  </div>
                  <div>
                    <h4 className="font-semibold text-purple-700 mb-1">Stage 2 Parameters:</h4>
                    <p><strong>Phase:</strong> {trainingProfileData.stage2?.phase}</p>
                    <p><strong>Ramp Limit:</strong> {(trainingProfileData.stage2?.ramp_limit_pct * 100).toFixed(1)}% per week</p>
                    <p><strong>Target Mileage:</strong> {trainingProfileData.stage2?.target_weekly_mileage} mi/week</p>
                  </div>
                </div>
                <div className="mt-2 pt-2 border-t border-purple-200">
                  <p><strong>Long-Run Cap:</strong> {trainingProfileData.stage2?.long_run_cap} mi</p>
                  <p><strong>Threshold Sessions:</strong> {trainingProfileData.stage2?.threshold_sessions_per_week} per week</p>
                  <p><strong>Easy Run Ratio:</strong> {(trainingProfileData.stage2?.easy_run_ratio * 100).toFixed(0)}%</p>
                  <p><strong>Training Days:</strong> {trainingProfileData.stage2?.recommended_training_days} per week</p>
                </div>
                <p className="text-xs text-gray-500 mt-2">✅ Check Flask logs for detailed Stage 1 & 2 breakdown</p>
              </div>
            )}
          </div>
        )}

        {structuredPlanData && (
          <div className="mt-4 bg-orange-50 p-4 rounded-xl border border-orange-200">
            <h3 className="font-bold mb-2">🎯 Stage 3+4: Pace-Aware Training Plan</h3>
            {structuredPlanData.error ? (
              <p className="text-red-600">{structuredPlanData.error}</p>
            ) : (
              <div className="text-sm space-y-3">
                <div className="grid grid-cols-3 gap-4 text-xs">
                  <div>
                    <h4 className="font-semibold text-green-700 mb-1">Stage 1:</h4>
                    <p><strong>Category:</strong> {structuredPlanData.stage1?.summary?.category || structuredPlanData.stage1?.category}</p>
                    <p><strong>Readiness:</strong> {structuredPlanData.stage1?.summary?.readiness_index || structuredPlanData.stage1?.readiness_index} / 100</p>
                  </div>
                  <div>
                    <h4 className="font-semibold text-purple-700 mb-1">Stage 2:</h4>
                    <p><strong>Phase:</strong> {structuredPlanData.stage2?.phase}</p>
                    <p><strong>Target:</strong> {structuredPlanData.stage2?.target_weekly_mileage} mi/week</p>
                  </div>
                  <div>
                    <h4 className="font-semibold text-orange-700 mb-1">Stage 3+4:</h4>
                    <p><strong>Weeks:</strong> {structuredPlanData.stage3_4?.weeks?.length || 0}</p>
                    <p><strong>Peak:</strong> {Math.max(...(structuredPlanData.stage3_4?.weeks?.map((w: any) => w.total_miles) || [0]))} mi</p>
                  </div>
                </div>
                
                <div className="border-t border-orange-200 pt-2">
                  <h4 className="font-semibold mb-2">🏃 Pace-Aware Weekly Plan:</h4>
                  <div className="max-h-64 overflow-y-auto space-y-2">
                    {structuredPlanData.stage3_4?.weeks?.slice(0, 3).map((week: any, idx: number) => (
                      <div key={idx} className="bg-white p-3 rounded border text-xs">
                        <div className="flex justify-between items-center mb-2">
                          <span className="font-semibold text-orange-700">Week {week.week_number}: {week.total_miles} mi</span>
                          <span className="text-gray-500 bg-gray-100 px-2 py-1 rounded">{week.phase}</span>
                        </div>
                        <div className="space-y-1">
                          {week.workouts?.map((workout: any, workoutIdx: number) => (
                            <div key={workoutIdx} className="flex justify-between items-center text-gray-700">
                              <span className="font-medium">
                                {workout.workout_type} ({workout.distance_mi} mi)
                              </span>
                              <div className="text-right">
                                <div className="text-orange-600 font-medium">{workout.target_pace}</div>
                                <div className="text-gray-500">{workout.target_hr}</div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                    {structuredPlanData.stage3_4?.weeks?.length > 3 && (
                      <p className="text-xs text-gray-500 italic text-center">
                        ... and {structuredPlanData.stage3_4.weeks.length - 3} more weeks with pace targets
                      </p>
                    )}
                  </div>
                </div>
                
                <p className="text-xs text-gray-500 mt-2">✅ Complete pace-aware plan with VDOT-based targets and Strava HR zones</p>
              </div>
            )}
          </div>
        )}

        {fourStagePlanData && (
          <div className="mt-4 bg-purple-50 p-4 rounded-xl border border-purple-200">
            <h3 className="font-bold mb-2">🚀 Four-Stage Plan Generation</h3>
            {fourStagePlanData.error ? (
              <p className="text-red-600">{fourStagePlanData.error}</p>
            ) : (
              <div className="text-sm space-y-3">
                <div className="bg-white p-3 rounded border">
                  <h4 className="font-semibold text-purple-700 mb-2">✅ Plan Generated Successfully!</h4>
                  <div className="grid grid-cols-2 gap-4 text-xs">
                    <div>
                      <p><strong>Plan ID:</strong> {fourStagePlanData.plan_id}</p>
                      <p><strong>Plan Name:</strong> {fourStagePlanData.plan_name}</p>
                      <p><strong>Race Date:</strong> {fourStagePlanData.race_date}</p>
                      <p><strong>Race Distance:</strong> {fourStagePlanData.race_distance}</p>
                    </div>
                    <div>
                      <p><strong>Total Workouts:</strong> {fourStagePlanData.workouts_count}</p>
                      <p><strong>Duration:</strong> {fourStagePlanData.weeks_count} weeks</p>
                      <p><strong>Category:</strong> {fourStagePlanData.stage_summary?.readiness_category}</p>
                      <p><strong>Phase:</strong> {fourStagePlanData.stage_summary?.training_phase}</p>
                    </div>
                  </div>
                  <div className="mt-3 p-2 bg-purple-100 rounded text-xs">
                    <p><strong>Target Mileage:</strong> {fourStagePlanData.stage_summary?.target_mileage} mi/week</p>
                    <p><strong>Peak Mileage:</strong> {fourStagePlanData.stage_summary?.peak_mileage} mi</p>
                  </div>
                  <div className="mt-2 text-xs text-gray-600">
                    <p>🎉 Your personalized training plan has been saved to the database!</p>
                    <p>💡 The plan includes pace targets, HR zones, and structured workout segments.</p>
                    <p className="mt-2">🔄 Redirecting you to your plan overview...</p>
                  </div>
                  <a 
                    href="/plan/overview" 
                    className="mt-3 block text-center bg-purple-600 text-white px-4 py-2 rounded text-sm hover:bg-purple-700"
                  >
                    View My Training Plan →
                  </a>
                </div>
              </div>
            )}
          </div>
        )}
        {vdotEstimationData && (
          <div className="mt-4 bg-blue-50 p-4 rounded-xl border border-blue-200">
            <h3 className="font-bold mb-2">🧮 GPT Fitness Analysis</h3>
            {vdotEstimationData.error ? (
              <p className="text-red-600">{vdotEstimationData.error}</p>
            ) : (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="bg-white p-3 rounded border">
                    <h4 className="font-semibold text-blue-800 mb-2">Fitness Assessment</h4>
                    <p><strong>VDOT Estimate:</strong> {vdotEstimationData.vdot_estimation?.vdot_estimate}</p>
                    <p><strong>Category:</strong> {vdotEstimationData.vdot_estimation?.category}</p>
                    <p><strong>Readiness Index:</strong> {vdotEstimationData.vdot_estimation?.readiness_index}/100</p>
                  </div>
                  <div className="bg-white p-3 rounded border">
                    <h4 className="font-semibold text-blue-800 mb-2">Training Metrics</h4>
                    {vdotEstimationData.vdot_estimation?.derived_metrics && (
                      <div className="space-y-1">
                        <p><strong>Avg Weekly:</strong> {vdotEstimationData.vdot_estimation.derived_metrics.avg_weekly_mileage} mi</p>
                        <p><strong>Longest Run:</strong> {vdotEstimationData.vdot_estimation.derived_metrics.longest_run_mi} mi</p>
                        <p><strong>Consistency:</strong> {vdotEstimationData.vdot_estimation.derived_metrics.consistency_score}%</p>
                        <p><strong>Weeks w/ 3+ runs:</strong> {vdotEstimationData.vdot_estimation.derived_metrics.weeks_with_3plus_runs}/{vdotEstimationData.vdot_estimation.derived_metrics.total_weeks}</p>
                      </div>
                    )}
                  </div>
                </div>
                {vdotEstimationData.vdot_estimation?.derived_metrics?.hr_distribution && (
                  <div className="bg-white p-3 rounded border text-sm">
                    <h4 className="font-semibold text-blue-800 mb-2">HR Zone Distribution</h4>
                    <div className="grid grid-cols-3 gap-2">
                      <p><strong>Easy (Z1-2):</strong> {vdotEstimationData.vdot_estimation.derived_metrics.hr_distribution.Z1_2}%</p>
                      <p><strong>Threshold (Z3):</strong> {vdotEstimationData.vdot_estimation.derived_metrics.hr_distribution.Z3}%</p>
                      <p><strong>Hard (Z4):</strong> {vdotEstimationData.vdot_estimation.derived_metrics.hr_distribution.Z4}%</p>
                    </div>
                  </div>
                )}
                {vdotEstimationData.vdot_estimation?.summary && (
                  <div className="bg-white p-3 rounded border text-sm">
                    <h4 className="font-semibold text-blue-800 mb-2">Coach Summary</h4>
                    <p>{vdotEstimationData.vdot_estimation.summary}</p>
                  </div>
                )}
                <div className="text-xs text-gray-600">
                  <p>🤖 This analysis was generated by GPT using Jack Daniels methodology.</p>
                  <p>📊 Compare with our 4-stage system results above for validation.</p>
                </div>
              </div>
            )}
          </div>
        )}
        {gptProfileNormalizationData && (
          <div className="mt-4 bg-teal-50 p-4 rounded-xl border border-teal-200">
            <h3 className="font-bold mb-2">⚙️ GPT Training Profile Normalization</h3>
            {gptProfileNormalizationData.error ? (
              <p className="text-red-600">{gptProfileNormalizationData.error}</p>
            ) : (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="bg-white p-3 rounded border">
                    <h4 className="font-semibold text-teal-800 mb-2">Training Phase & Intensity</h4>
                    <p><strong>Phase:</strong> {gptProfileNormalizationData.normalized_profile?.phase}</p>
                    <p><strong>Target Weekly:</strong> {gptProfileNormalizationData.normalized_profile?.target_weekly_mileage} mi</p>
                    <p><strong>Long Run Cap:</strong> {gptProfileNormalizationData.normalized_profile?.long_run_cap} mi</p>
                    <p><strong>Easy Ratio:</strong> {(gptProfileNormalizationData.normalized_profile?.easy_run_ratio * 100).toFixed(0)}%</p>
                  </div>
                  <div className="bg-white p-3 rounded border">
                    <h4 className="font-semibold text-teal-800 mb-2">Progression Limits</h4>
                    <p><strong>Ramp Limit:</strong> {(gptProfileNormalizationData.normalized_profile?.ramp_limit_pct * 100).toFixed(1)}%/week</p>
                    <p><strong>Max Weekly Increase:</strong> {gptProfileNormalizationData.normalized_profile?.max_weekly_increase} mi</p>
                    <p><strong>Threshold Sessions:</strong> {gptProfileNormalizationData.normalized_profile?.threshold_sessions_per_week}/week</p>
                    <p><strong>Recovery Week:</strong> Every {gptProfileNormalizationData.normalized_profile?.recovery_week_frequency} weeks</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div className="bg-white p-3 rounded border">
                    <h4 className="font-semibold text-teal-800 mb-2">Mileage Bounds</h4>
                    <p><strong>Min Weekly:</strong> {gptProfileNormalizationData.normalized_profile?.min_weekly_mileage} mi</p>
                    <p><strong>Max Weekly:</strong> {gptProfileNormalizationData.normalized_profile?.max_weekly_mileage} mi</p>
                    <p><strong>Mileage Multiplier:</strong> {gptProfileNormalizationData.normalized_profile?.mileage_multiplier}x</p>
                  </div>
                  <div className="bg-white p-3 rounded border">
                    <h4 className="font-semibold text-teal-800 mb-2">Other Parameters</h4>
                    <p><strong>Training Days:</strong> {gptProfileNormalizationData.normalized_profile?.recommended_training_days} days/week</p>
                    <p><strong>VDOT Adjustment:</strong> {gptProfileNormalizationData.normalized_profile?.vdot_adjustment}</p>
                  </div>
                </div>
                {gptProfileNormalizationData.normalized_profile?.notes && (
                  <div className="bg-white p-3 rounded border text-sm">
                    <h4 className="font-semibold text-teal-800 mb-2">Coach Notes</h4>
                    <p>{gptProfileNormalizationData.normalized_profile.notes}</p>
                  </div>
                )}
                <div className="text-xs text-gray-600">
                  <p>🤖 These parameters were generated by GPT using Jack Daniels normalization rules.</p>
                  <p>📊 Compare with our Stage 2 system results to validate accuracy.</p>
                </div>
              </div>
            )}
          </div>
        )}
        {gptPlanGenerationData && (
          <div className="mt-4 bg-indigo-50 p-4 rounded-xl border border-indigo-200">
            <h3 className="font-bold mb-2">📅 GPT Complete Training Plan</h3>
            {gptPlanGenerationData.error ? (
              <p className="text-red-600">{gptPlanGenerationData.error}</p>
            ) : gptPlanGenerationData.plan_id ? (
              <div className="space-y-3">
                <div className="bg-white p-3 rounded border text-sm">
                  <h4 className="font-semibold text-indigo-800 mb-2">✅ Plan Generated & Saved!</h4>
                  <p><strong>Plan ID:</strong> {gptPlanGenerationData.plan_id}</p>
                  <p><strong>Plan Name:</strong> {gptPlanGenerationData.plan_name}</p>
                  <p><strong>Race Date:</strong> {gptPlanGenerationData.race_date}</p>
                  <p><strong>Race Distance:</strong> {gptPlanGenerationData.race_distance}</p>
                </div>
                <div className="bg-white p-3 rounded border text-sm">
                  <h4 className="font-semibold text-indigo-800 mb-2">📊 Plan Details</h4>
                  <p><strong>Total Weeks:</strong> 8 weeks</p>
                  <p><strong>Total Workouts:</strong> ~40 workouts</p>
                  <p><strong>Methodology:</strong> Jack Daniels (GPT-generated)</p>
                </div>
                <div className="mt-3 p-2 bg-indigo-100 rounded text-xs">
                  <p>🎉 Your GPT-generated training plan has been saved to the database!</p>
                  <p>💡 The plan includes progressive mileage, proper taper, and structured workouts.</p>
                  <p className="mt-2">🔄 Redirecting you to your plan overview...</p>
                </div>
                <a 
                  href="/plan/overview" 
                  className="mt-3 block text-center bg-indigo-600 text-white px-4 py-2 rounded text-sm hover:bg-indigo-700"
                >
                  View My GPT Training Plan →
                </a>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-orange-600">⚠️ Plan generated but not saved to database</p>
                {gptPlanGenerationData.training_plan && (
                  <pre className="bg-gray-100 p-2 rounded text-xs overflow-auto">
                    {JSON.stringify(gptPlanGenerationData.training_plan, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
