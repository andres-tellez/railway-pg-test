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
    <div className="w-full max-w-md mx-auto">
      {/* Month Header */}
      <div className="flex items-center justify-between px-4 mt-4">
        <button
          onClick={() =>
            setCurrentMonth(new Date(currentMonth.setMonth(currentMonth.getMonth() - 1)))
          }
          className="text-2xl"
        >
          ←
        </button>
        <h2 className="text-xl font-semibold">{format(currentMonth, 'MMMM yyyy')}</h2>
        <button
          onClick={() =>
            setCurrentMonth(new Date(currentMonth.setMonth(currentMonth.getMonth() + 1)))
          }
          className="text-2xl"
        >
          →
        </button>
      </div>

      {/* Weekday Labels */}
      <div className="grid grid-cols-7 gap-2 text-center text-sm text-gray-500 px-2 mt-6">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
          <div key={day}>{day}</div>
        ))}
      </div>

      {/* Calendar Days */}
      <div className="grid grid-cols-7 gap-2 text-center text-sm px-2 mt-2">
        {Array.from({ length: offset }).map((_, idx) => (
          <div key={`empty-${idx}`} />
        ))}

        {days.map((date) => {
          const dateStr = format(date, 'yyyy-MM-dd');
          const workout = workoutsByDate[dateStr];
          const isSelected = selectedDate === dateStr;
          const isTodayFlag = isToday(date);

          return (
            <div
              key={dateStr}
              className={`p-2 rounded-md cursor-pointer flex flex-col items-center justify-center
                ${isSelected ? 'border-2 border-black' : 'border border-transparent'}
                hover:bg-gray-100 transition`}
              onClick={() => setSelectedDate(dateStr)}
            >
              <div className="text-sm">{format(date, 'd')}</div>
              {workout && (
                <div
                  className={`w-3 h-3 rounded-md mt-1 ${
                    workout.type === 'RUN'
                      ? 'bg-red-500'
                      : workout.type === 'STRENGTH'
                      ? 'bg-yellow-400'
                      : 'bg-gray-300'
                  }`}
                />
              )}
              {isTodayFlag && <div className="w-1.5 h-1.5 bg-black rounded-full mt-1" />}
            </div>
          );
        })}
      </div>

      {/* Workout Details */}
      <div className="mt-6 px-4 py-4 border-t bg-white">
        {selectedDate && workoutsByDate[selectedDate] ? (
          <>
            <h3 className="text-lg font-semibold mb-1">
              {workoutsByDate[selectedDate].type}
            </h3>
            <p className="text-sm text-gray-700">
              {workoutsByDate[selectedDate].description}
            </p>
          </>
        ) : (
          <p className="text-sm text-gray-400">No workout scheduled for this day.</p>
        )}
      </div>
    </div>
  );
};

export default MyPlan;
