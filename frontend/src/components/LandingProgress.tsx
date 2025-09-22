// frontend/src/components/LandingProgress.tsx

import React, { useEffect, useMemo, useState } from "react";
import { useApiClient } from "../utils/apiClient";

type Stage = "starting" | "fetching" | "enriching" | "done" | "error";

interface ProgressResponse {
  stage: string;     // raw backend stage
  ui_stage: Stage;   // normalized stage from backend
  message: string;
  percent: number;
}

const STAGE_LABELS: Record<Stage, string> = {
  starting: "Starting import",
  fetching: "Fetching from Strava",
  enriching: "Enriching activities",
  done: "Finished",
  error: "Error",
};

const ORDER: Stage[] = ["starting", "fetching", "enriching", "done"];

interface Props {
  userId: string; // ✅ main app identifier (UUID from Auth0 mapping)
}

export function LandingProgress({ userId }: Props) {
  const api = useApiClient();

  const [percent, setPercent] = useState(2);
  const [stage, setStage] = useState<Stage>("starting");
  const [line, setLine] = useState("Starting…");
  const [log, setLog] = useState<string[]>([]);

  useEffect(() => {
    if (!userId) return;

    const interval = setInterval(async () => {
      try {
        const res = await api.get<ProgressResponse>(`/progress/status`);
        const data = res.data;

        // ✅ Use ui_stage provided by backend
        setStage(data.ui_stage);

        const label = data.message || STAGE_LABELS[data.ui_stage];
        setLine(label);
        setPercent(Math.max(2, Math.min(100, data.percent)));

        // Rolling log (latest 6 entries)
        setLog((prev) => {
          const next = [`${new Date().toLocaleTimeString()} - ${label}`, ...prev];
          return next.slice(0, 6);
        });

        if (import.meta.env.MODE !== "production") {
          console.log("📊 Progress update:", data);
        }
      } catch (err) {
        console.error("❌ Failed to poll progress:", err);
      }
    }, 3000); // Poll every 3 seconds

    return () => clearInterval(interval);
  }, [api, userId]);

  const steps = useMemo(
    () =>
      ORDER.map((s) => ({
        key: s,
        label: STAGE_LABELS[s],
        done: ORDER.indexOf(s) <= ORDER.indexOf(stage),
        active: s === stage,
      })),
    [stage]
  );

  return (
    <div className="w-full max-w-xl mx-auto rounded-2xl border border-zinc-200 shadow-sm bg-white p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Step 1 · Import from Strava</h2>
        <span className="text-sm text-zinc-500">{percent.toFixed(0)}%</span>
      </div>

      {/* Progress bar */}
      <div className="h-3 w-full bg-zinc-100 rounded-full overflow-hidden mb-4">
        <div
          className="h-full rounded-full transition-all duration-300 bg-blue-500"
          style={{ width: `${percent}%` }}
        />
      </div>

      {/* Live line */}
      <div className="flex items-center justify-between mb-4">
        <div className="text-sm text-zinc-700">{line}</div>
      </div>

      {/* Steps list */}
      <ol className="grid grid-cols-2 gap-2 mb-4">
        {steps.map((s) => (
          <li key={s.key} className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                s.done
                  ? "bg-green-500"
                  : s.active
                  ? "bg-amber-500 animate-pulse"
                  : "bg-zinc-300"
              }`}
            />
            <span
              className={`text-xs ${s.active ? "text-zinc-900" : "text-zinc-500"}`}
            >
              {s.label}
            </span>
          </li>
        ))}
      </ol>

      {/* Log */}
      <div className="bg-zinc-50 border border-zinc-200 rounded-lg p-2 h-24 overflow-auto text-xs font-mono text-zinc-700">
        {log.length > 0 ? (
          log.map((l, i) => (
            <div key={i} className="truncate">
              {l}
            </div>
          ))
        ) : (
          <div className="text-xs text-zinc-500">Waiting for progress...</div>
        )}
      </div>
    </div>
  );
}
