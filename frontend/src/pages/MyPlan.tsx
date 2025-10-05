/**
 * @file MyPlan.tsx
 * @component MyPlan
 * @description: Displays user's monthly training plan with a calendar layout.
 */

import React, { useEffect, useState } from 'react';
import {
  format,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  getDay,
  isToday,
  parseISO,
} from 'date-fns';
import { useApiClient } from '@/utils/apiClient';

type Workout = {
  date: string;
  type: 'RUN' | 'REST' | 'STRENGTH';
  description: string;
  // New structured fields
  workout_type?: string;
  miles?: number;
  target_zone?: string;
  target_hr?: string;
  focus?: string;
  segments?: Array<{
    name: string;
    distance: string;
    target_zone: string;
    notes: string;
  }>;
};

type PlanResponse = {
  plan_id: string;
  start_date: string;
  race_date: string;
  workouts: any[];
};

const convertWorkoutType = (raw: string): Workout['type'] => {
  const normalized = raw.toLowerCase();
  if (normalized.includes('rest')) return 'REST';
  if (normalized.includes('strength')) return 'STRENGTH';
  return 'RUN';
};

// Component to render structured workout data
const WorkoutDetails: React.FC<{ workout: Workout }> = ({ workout }) => {
  // Simple workout (no segments) - use 3-line template
  if (!workout.segments || workout.segments.length === 0) {
    return (
      <div className="space-y-3">
        {/* Workout Header */}
        <div className="font-semibold text-lg text-gray-900">
          {workout.workout_type?.toUpperCase() || workout.type} - {workout.miles} MILES
        </div>

        {/* Target Zone */}
        {workout.target_zone && workout.target_hr && (
          <div className="text-sm text-gray-800">
            <span className="font-semibold">Target:</span> {workout.target_zone} ({workout.target_hr})
          </div>
        )}

        {/* Focus with bold emphasis */}
        {workout.focus && (
          <div className="text-sm text-gray-800">
            <span className="font-semibold">Focus:</span> {workout.focus}
          </div>
        )}
      </div>
    );
  }

  // Complex workout (with segments) - use table format
  return (
    <div className="space-y-4">
      {/* Workout Header */}
      <div className="font-semibold text-lg text-gray-900">
        {workout.workout_type?.toUpperCase() || workout.type} - {workout.miles} MILES
      </div>

      {/* Target Zone */}
      {workout.target_zone && workout.target_hr && (
        <div className="text-sm text-gray-800">
          <span className="font-semibold">Target:</span> {workout.target_zone} ({workout.target_hr})
        </div>
      )}

      {/* Focus with bold emphasis and extra spacing */}
      {workout.focus && (
        <div className="text-sm text-gray-800 pb-2">
          <span className="font-semibold">Focus:</span> {workout.focus}
        </div>
      )}

        {/* Workout Structure Table */}
        <div className="space-y-3">
          <div className="text-sm font-semibold text-gray-700">
            Workout Structure:
          </div>

          <div className="bg-white border border-gray-300 rounded-lg shadow-sm overflow-hidden">
            {/* Table Header */}
            <div className="bg-gray-100 border-b border-gray-300">
              <div className="grid grid-cols-4 gap-3 px-4 py-2 text-xs font-semibold text-gray-700">
                <div>Segment</div>
                <div>Distance</div>
                <div>Target</div>
                <div>Notes</div>
              </div>
            </div>

            {/* Table Rows */}
            <div className="divide-y divide-gray-200">
              {workout.segments.map((segment, index) => (
                <div key={index} className="grid grid-cols-4 gap-3 px-4 py-2 hover:bg-gray-50 transition-colors items-center">
                  <div className="text-xs font-medium text-gray-900">{segment.name}</div>
                  <div className="text-xs text-gray-700">{convertDistanceToMiles(segment.distance)}</div>
                  <div className="text-xs text-gray-700">{segment.target_zone}</div>
                  <div className="text-xs text-gray-600">{segment.notes}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
    </div>
  );
};

// Helper function to convert distances to miles for US users
const convertDistanceToMiles = (distance: string): string => {
  // If already in miles, return as-is
  if (distance.includes('mile')) {
    return distance;
  }

  // Convert meters to miles
  const metersMatch = distance.match(/(\d+)m/);
  if (metersMatch) {
    const meters = parseInt(metersMatch[1]);
    const miles = meters * 0.000621371; // Convert meters to miles
    return `${miles.toFixed(2)} miles`;
  }

  // If no conversion needed, return original
  return distance;
};

const MyPlan: React.FC = () => {
  const api = useApiClient(); // ✅ Moved here — top-level inside the component
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [workoutsByDate, setWorkoutsByDate] = useState<Record<string, Workout>>({});
  const [currentMonth, setCurrentMonth] = useState(new Date());

  useEffect(() => {
    const fetchPlan = async () => {
      try {
        const res = await api.get('/api/plan/current'); // ✅ Use it, don't re-invoke it
        setPlan(res.data);

        const mapped: Record<string, Workout> = {};
        res.data.workouts.forEach((w: any) => {
          mapped[w.date] = {
            date: w.date,
            type: convertWorkoutType(w.workout_type),
            description: w.description,
            // Map new structured fields
            workout_type: w.workout_type,
            miles: w.miles,
            target_zone: w.target_zone,
            target_hr: w.target_hr,
            focus: w.focus,
            segments: w.segments,
          };
        });
        setWorkoutsByDate(mapped);

        const today = format(new Date(), 'yyyy-MM-dd');
        if (mapped[today]) {
          setSelectedDate(today);
        } else if (res.data.workouts.length > 0) {
          const firstWorkoutDate = res.data.workouts[0].date;
          setSelectedDate(firstWorkoutDate);
          setCurrentMonth(parseISO(firstWorkoutDate));
        } else {
          setSelectedDate(null);
        }
      } catch (error: any) {
        console.error("Failed to fetch current plan:", error);
        setPlan(null);
        setSelectedDate(null);
      }
    };

    fetchPlan();
  }, []); // ✅ 'api' is stable, no need to include in deps

  const days = eachDayOfInterval({
    start: startOfMonth(currentMonth),
    end: endOfMonth(currentMonth),
  });

  const offset = getDay(startOfMonth(currentMonth));

  return (
    <div className="w-full max-w-lg mx-auto">
      {/* Modern Calendar Card */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-2xl font-bold tracking-tight text-gray-900">
            {format(currentMonth, 'MMMM yyyy')}
          </h2>
          <div className="flex gap-2">
            <button
              onClick={() =>
                setCurrentMonth(new Date(currentMonth.setMonth(currentMonth.getMonth() - 1)))
              }
              className="h-10 w-10 rounded-lg border border-gray-200 bg-transparent hover:bg-gray-50 hover:text-gray-900 flex items-center justify-center transition-colors"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <button
              onClick={() =>
                setCurrentMonth(new Date(currentMonth.setMonth(currentMonth.getMonth() + 1)))
              }
              className="h-10 w-10 rounded-lg border border-gray-200 bg-transparent hover:bg-gray-50 hover:text-gray-900 flex items-center justify-center transition-colors"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>

        {/* Weekday headers */}
        <div className="mb-4 grid grid-cols-7 gap-2">
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
            <div key={day} className="text-center text-xs font-medium uppercase tracking-wider text-gray-500">
              {day}
            </div>
          ))}
        </div>

        {/* Calendar grid */}
        <div className="grid grid-cols-7 gap-3">
          {Array.from({ length: offset }).map((_, idx) => (
            <div key={`empty-${idx}`} />
          ))}

          {days.map((date) => {
            const dateStr = format(date, 'yyyy-MM-dd');
            const workout = workoutsByDate[dateStr];
            const isSelected = selectedDate === dateStr;
            const isTodayFlag = isToday(date);

            return (
              <button
                key={dateStr}
                onClick={() => setSelectedDate(dateStr)}
                className={`relative aspect-square rounded-lg transition-all duration-200 flex items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 ${
                  !workout && 'bg-gray-50 hover:bg-gray-100 text-gray-500 hover:text-gray-900'
                } ${
                  workout && 'bg-gray-800 text-white hover:bg-gray-700 shadow-sm'
                } ${
                  isSelected && 'ring-2 ring-blue-500 ring-offset-2 ring-offset-white shadow-md'
                } ${
                  isTodayFlag && !isSelected && 'ring-1 ring-blue-300'
                }`}
              >
                <span
                  className={`text-base font-semibold leading-none ${
                    workout && 'text-white font-bold'
                  } ${!workout && 'text-gray-500'}`}
                >
                  {format(date, 'd')}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Workout Details */}
      <div className="mt-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        {selectedDate && workoutsByDate[selectedDate] ? (
          <WorkoutDetails workout={workoutsByDate[selectedDate]} />
        ) : (
          <p className="text-sm text-gray-500">No workout scheduled for this day.</p>
        )}
      </div>
    </div>
  );
};

export default MyPlan;
