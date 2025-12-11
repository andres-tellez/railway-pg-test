// @file HomeScreen2.tsx
// @component HomeScreen2
// @description: Week timeline view with improved workout details (WorkoutDetails2)
// @features: Interactive week timeline, improved workout details with visual range bars, completion status
// @architecture: Optimized with useMemo, useCallback, and extracted components

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { format } from 'date-fns';
import { useApiClient } from '../utils/apiClient';
import { useAuthSetup } from '../hooks/useAuthSetup';
import { AuthGuard } from '../components/AuthGuard';
import WelcomeModal from '../components/WelcomeModal';
import { useSearchParams, useNavigate } from 'react-router-dom';
import WeekDayButton from '../components/home/WeekDayButton';
import ProgressBar from '../components/home/ProgressBar';
import WorkoutDetails from '../components/home/WorkoutDetails';
import {
  getThisWeekRange,
  processWeekData,
  calculateWeeklyProgress,
  type Workout,
  type Activity,
  type WeekDay,
} from '../utils/weekTimelineUtils';
import {
  toDateString,
  dateStringToDate,
  getWeekRange,
  getPreviousWeek,
  getNextWeek,
  isSundayEvening,
  isFutureWeek,
  isPastWeek,
} from '../utils/dateUtils';
import { WEEK_TIMELINE_STYLES } from '../utils/weekTimelineStyles';
// Import test utilities (available in browser console)
import '../utils/dateTestUtils';
import MaxHrBanner from '../components/MaxHrBanner';

const HomeScreen2: React.FC = () => {
  const { isReady, userId } = useAuthSetup();
  const api = useApiClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [showWelcome, setShowWelcome] = useState(false);

  const [weekDays, setWeekDays] = useState<WeekDay[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [hasPlan, setHasPlan] = useState<boolean>(true);
  const [allActivities, setAllActivities] = useState<Activity[]>([]);
  const [planStartDate, setPlanStartDate] = useState<string | null>(null);

  // Track the current week being viewed (starts with this week)
  const [currentWeekStart, setCurrentWeekStart] = useState<string>(() => {
    return getThisWeekRange().weekStart;
  });

  // Memoize week range calculation based on current week
  const weekRange = useMemo(() => getWeekRange(currentWeekStart), [currentWeekStart]);

  // Fetch week data
  useEffect(() => {
    if (!isReady || !userId) return;

    const fetchWeekData = async () => {
      try {
        setLoading(true);
        const { weekStart, weekEnd } = weekRange;

        // Fetch current plan and activities in parallel
        let workouts: Workout[] = [];
        let planExists = false;

        try {
          const planRes = await api.get('/api/plan/current');
          const allWorkouts = planRes.data.workouts || [];
          // Store plan start date
          if (planRes.data.start_date) {
            setPlanStartDate(planRes.data.start_date);
          }
          // Filter workouts for the current week being viewed
          workouts = allWorkouts.filter((w: Workout) => {
            const workoutDate = toDateString(w.date);
            return workoutDate >= weekStart && workoutDate <= weekEnd;
          });
          planExists = true;
          setHasPlan(true);

        } catch (planError: any) {
          // Check if it's a 404 (no plan) vs other error
          if (planError.response?.status === 404) {
            planExists = false;
            setHasPlan(false);
            setPlanStartDate(null);
            workouts = [];
          } else {
            // Other error - log it but continue
            console.error('Error fetching plan:', planError);
            setHasPlan(false);
            setPlanStartDate(null);
            workouts = [];
          }
        }

        // Fetch activities regardless of plan status
        const activitiesRes = await api.get('/api/activities/');
        const fetchedActivities: Activity[] = activitiesRes.data?.activities || [];
        setAllActivities(fetchedActivities);

        // Filter activities for this week - SIMPLE string comparison
        const weekActivities = fetchedActivities.filter((act: Activity) => {
          const actDate = toDateString(act.date);
          return actDate >= weekStart && actDate <= weekEnd;
        });

        // Process week data
        const processedDays = processWeekData(workouts, weekActivities, weekStart, weekEnd);
        setWeekDays(processedDays);

        // Calculate progress
        const progress = calculateWeeklyProgress(processedDays);

        // Set selected date: prefer today if in this week, otherwise first day with workout, otherwise first day
        const todayDay = processedDays.find((d) => d.isToday);
        if (todayDay) {
          setSelectedDate(todayDay.dateStr);
        } else {
          const firstWorkoutDay = processedDays.find((d) => d.workout);
          if (firstWorkoutDay) {
            setSelectedDate(firstWorkoutDay.dateStr);
          } else if (processedDays.length > 0) {
            // If no workouts, select first day of the week
            setSelectedDate(processedDays[0].dateStr);
          }
        }
      } catch (error) {
        console.error('Failed to fetch week data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchWeekData();
  }, [isReady, userId, api, weekRange, currentWeekStart]);

  // Welcome modal logic
  useEffect(() => {
    const welcomeShown = localStorage.getItem('smartcoach_welcome_shown');
    const fromOnboarding = searchParams.get('welcome') === 'true';

    if (fromOnboarding || !welcomeShown) {
      setShowWelcome(true);
      if (!welcomeShown) {
        localStorage.setItem('smartcoach_welcome_shown', 'true');
      }
      if (fromOnboarding) {
        navigate('/home', { replace: true });
      }
    }
  }, [searchParams, navigate]);

  // Memoized handlers
  const handleCloseWelcome = useCallback(() => {
    setShowWelcome(false);
  }, []);

  const handleDayClick = useCallback((dateStr: string) => {
    setSelectedDate(dateStr);
  }, []);

  // Week navigation handlers
  const handlePreviousWeek = useCallback(() => {
    const prevWeekStart = getPreviousWeek(currentWeekStart);
    setCurrentWeekStart(prevWeekStart);
    setSelectedDate(null); // Reset selection, will be set in useEffect
  }, [currentWeekStart]);

  const handleNextWeek = useCallback(() => {
    const nextWeekStart = getNextWeek(currentWeekStart);
    setCurrentWeekStart(nextWeekStart);
    setSelectedDate(null); // Reset selection, will be set in useEffect
  }, [currentWeekStart]);

  // Check if viewing next week and if details are available
  const isViewingNextWeek = useMemo(() => {
    return isFutureWeek(currentWeekStart);
  }, [currentWeekStart]);

  const isViewingPastWeek = useMemo(() => {
    return isPastWeek(currentWeekStart);
  }, [currentWeekStart]);

  // Check if next week details should be available (after Sunday evening)
  const nextWeekDetailsAvailable = useMemo(() => {
    if (!isViewingNextWeek) return true;
    return isSundayEvening();
  }, [isViewingNextWeek]);

  // Memoized computed values
  const selectedDay = useMemo(
    () => weekDays.find((d) => d.dateStr === selectedDate),
    [weekDays, selectedDate]
  );

  const weeklyProgress = useMemo(
    () => calculateWeeklyProgress(weekDays),
    [weekDays]
  );

  const nextWorkoutDay = useMemo(() => {
    if (!selectedDay) return undefined;
    const currentIdx = weekDays.findIndex((d) => d.dateStr === selectedDate);
    return weekDays
      .slice(currentIdx + 1)
      .find((d) => d.workout && !d.isRestDay);
  }, [weekDays, selectedDate, selectedDay]);

  if (loading) {
    return (
      <AuthGuard>
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading...</p>
          </div>
        </div>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-4xl mx-auto px-2 sm:px-4 py-4 sm:py-6">
          <MaxHrBanner />
          {/* Week Timeline */}
          <div className={`${WEEK_TIMELINE_STYLES.container} ${WEEK_TIMELINE_STYLES.containerPadding} mb-6`}>
            {/* Week Navigation Header */}
            <div className="flex items-center justify-between mb-4">
              <button
                onClick={handlePreviousWeek}
                className="flex items-center justify-center w-10 h-10 sm:w-12 sm:h-12 rounded-lg bg-gray-100 hover:bg-gray-200 active:bg-gray-300 border-2 border-gray-300 hover:border-gray-400 transition-all duration-200 shadow-sm hover:shadow-md"
                aria-label="Previous week"
              >
                <span className="text-xl sm:text-2xl font-bold text-gray-700">←</span>
              </button>

              {/* Month/Year Context */}
              <div className="flex-1 text-center px-2">
                <div className="text-sm font-semibold text-gray-900">
                  {format(dateStringToDate(weekRange.weekStart), 'MMMM yyyy')}
                </div>
                {currentWeekStart === getThisWeekRange().weekStart && (
                  <div className="text-xs text-blue-600 font-medium mt-0.5">This Week</div>
                )}
                {isViewingPastWeek && (
                  <div className="text-xs text-gray-500 font-medium mt-0.5">Past Week</div>
                )}
                {isViewingNextWeek && (
                  <div className="text-xs text-gray-500 font-medium mt-0.5">Next Week</div>
                )}
              </div>

              <button
                onClick={handleNextWeek}
                className="flex items-center justify-center w-10 h-10 sm:w-12 sm:h-12 rounded-lg bg-gray-100 hover:bg-gray-200 active:bg-gray-300 border-2 border-gray-300 hover:border-gray-400 transition-all duration-200 shadow-sm hover:shadow-md"
                aria-label="Next week"
              >
                <span className="text-xl sm:text-2xl font-bold text-gray-700">→</span>
              </button>
            </div>

            {/* Past Week Message */}
            {isViewingPastWeek && hasPlan && (
              <div className="mb-4 p-3 bg-gray-50 border border-gray-200 rounded-md">
                <p className="text-sm text-gray-700">
                  Viewing past week: See how you performed against your plan.
                </p>
              </div>
            )}

            <div className={WEEK_TIMELINE_STYLES.dayGrid}>
              {weekDays.map((day) => (
                <WeekDayButton
                  key={day.dateStr}
                  date={day.date}
                  dateStr={day.dateStr}
                  isSelected={day.dateStr === selectedDate}
                  isCompleted={day.isCompleted}
                  isRestDay={day.isRestDay}
                  isToday={day.isToday}
                  workout={day.workout}
                  onClick={handleDayClick}
                />
              ))}
            </div>

            {/* Progress Summary - Only show if plan exists */}
            {hasPlan && (
              <ProgressBar
                completed={weeklyProgress.completed}
                total={weeklyProgress.total}
                milesCompleted={weeklyProgress.milesCompleted}
                milesTotal={weeklyProgress.milesTotal}
              />
            )}
          </div>


          {/* Details Panel - Show for both plan and no-plan scenarios */}
          {selectedDay && (
            <div className={WEEK_TIMELINE_STYLES.detailsPanel}>
              <WorkoutDetails
                date={selectedDay.date}
                dateStr={selectedDay.dateStr}
                workout={selectedDay.workout}
                activity={selectedDay.activity}
                isCompleted={selectedDay.isCompleted}
                isRestDay={selectedDay.isRestDay}
                hasPlan={hasPlan}
                planStartDate={planStartDate}
                nextWorkoutDay={nextWorkoutDay ? {
                  date: nextWorkoutDay.date,
                  workout: nextWorkoutDay.workout!,
                } : undefined}
              />
            </div>
          )}
        </div>

        {showWelcome && <WelcomeModal onClose={handleCloseWelcome} />}
      </div>
    </AuthGuard>
  );
};

export default HomeScreen2;
