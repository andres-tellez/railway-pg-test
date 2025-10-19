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
  notes?: string;
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
              {Array.isArray(workout.segments) ? (workout.segments as any[]).map((segment: any, index: number) => (
                <div key={index} className="grid grid-cols-4 gap-3 px-4 py-2 hover:bg-gray-50 transition-colors items-center">
                  <div className="text-xs font-medium text-gray-900">{segment.name}</div>
                  <div className="text-xs text-gray-700">{segment.distance || '-'}</div>
                  <div className="text-xs text-gray-700">{segment.target_zone || '-'}</div>
                  <div className="text-xs text-gray-600">{segment.notes || '-'}</div>
                </div>
              )) : workout.segments && typeof workout.segments === 'object' ?
                Object.entries(workout.segments).map(([key, value], index) => (
                  <div key={index} className="grid grid-cols-4 gap-3 px-4 py-2 hover:bg-gray-50 transition-colors items-center">
                    <div className="text-xs font-medium text-gray-900 capitalize">{key}</div>
                    <div className="text-xs text-gray-700">-</div>
                    <div className="text-xs text-gray-700">{workout.target_zone}</div>
                    <div className="text-xs text-gray-600">{String(value)}</div>
                  </div>
                )) : []
              }
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

        // Debug: Log workout date range
        console.log(`📅 Training plan loaded: ${res.data.workouts.length} workouts`);
        if (res.data.workouts.length > 0) {
          const dates = res.data.workouts.map((w: any) => w.date).sort();
          console.log(`📅 Date range: ${dates[0]} to ${dates[dates.length - 1]}`);
          console.log(`📅 Race date: ${res.data.race_date}`);
        }

        const today = format(new Date(), 'yyyy-MM-dd');
        if (mapped[today]) {
          setSelectedDate(today);
          console.log(`📅 Selected today: ${today}`);
        } else if (res.data.workouts.length > 0) {
          // Default to current month, but select the first workout if today has no workout
          const firstWorkoutDate = res.data.workouts[0].date;
          setSelectedDate(firstWorkoutDate);
          console.log(`📅 Selected first workout: ${firstWorkoutDate}`);

          // Always navigate to the first month with workouts
          const firstWorkoutMonthStr = firstWorkoutDate.substring(0, 7);
          setCurrentMonth(parseISO(firstWorkoutDate));
          console.log(`📅 Set current month to first workout month: ${firstWorkoutMonthStr}`);
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
      {/* Safety Warning */}
      {plan && plan.notes && plan.notes.includes('⚠️ SAFETY WARNING:') && (
        <div className="mb-6 rounded-xl border border-orange-200 bg-orange-50 p-4 shadow-sm">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-orange-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-orange-800">
                Training Plan Safety Notice
              </h3>
              <div className="mt-2 text-sm text-orange-700">
                <p>{plan.notes.split('⚠️ SAFETY WARNING: ')[1]}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modern Calendar Card */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-2xl font-bold tracking-tight text-gray-900">
            {format(currentMonth, 'MMMM yyyy')}
          </h2>
          <div className="flex gap-2">
            <button
              onClick={() => {
                const newDate = new Date(currentMonth);
                newDate.setMonth(newDate.getMonth() - 1);
                setCurrentMonth(newDate);
              }}
              className="h-10 w-10 rounded-lg border border-gray-200 bg-transparent hover:bg-gray-50 hover:text-gray-900 flex items-center justify-center transition-colors"
            >
              <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <button
              onClick={() => {
                const newDate = new Date(currentMonth);
                newDate.setMonth(newDate.getMonth() + 1);
                setCurrentMonth(newDate);
              }}
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

            // Check if this is the race date from the actual plan data
            const isRaceDate = plan?.race_date ? dateStr === plan.race_date : false;

            return (
              <button
                key={dateStr}
                onClick={() => setSelectedDate(dateStr)}
                className={`relative aspect-square rounded-lg transition-all duration-200 flex items-center justify-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 ${
                  isRaceDate && 'bg-gradient-to-br from-yellow-400 to-orange-500 text-white font-bold shadow-lg'
                } ${
                  !workout && !isRaceDate && 'bg-gray-50 hover:bg-gray-100 text-gray-500 hover:text-gray-900'
                } ${
                  workout && !isRaceDate && 'bg-gray-800 text-white hover:bg-gray-700 shadow-sm'
                } ${
                  isSelected && 'ring-2 ring-blue-500 ring-offset-2 ring-offset-white shadow-md'
                } ${
                  isTodayFlag && !isSelected && !isRaceDate && 'ring-1 ring-blue-300'
                }`}
              >
                <span
                  className={`text-base font-semibold leading-none ${
                    isRaceDate && 'text-white font-bold'
                  } ${
                    workout && !isRaceDate && 'text-white font-bold'
                  } ${
                    !workout && !isRaceDate && 'text-gray-500'
                  }`}
                >
                  {format(date, 'd')}
                </span>
              </button>
            );
          })}
        </div>
      </div>


      {/* Workout Details */}
      {plan && (
        <div className="mt-6 rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
          {selectedDate && workoutsByDate[selectedDate] ? (
            <WorkoutDetails workout={workoutsByDate[selectedDate]} />
          ) : (
            <p className="text-sm text-gray-500">No workout scheduled for this day.</p>
          )}
        </div>
      )}

    </div>
  );
};

export default MyPlan;
