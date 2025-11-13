// @file HomeScreen.tsx
// @component HomeScreen
// @description: Week timeline view showing this week's workouts with details panel
// @features: Interactive week timeline, workout details, completion status
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
import { WEEK_TIMELINE_STYLES } from '../utils/weekTimelineStyles';

const HomeScreen: React.FC = () => {
  const { isReady, userId } = useAuthSetup();
  const api = useApiClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [showWelcome, setShowWelcome] = useState(false);

  const [weekDays, setWeekDays] = useState<WeekDay[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [hasPlan, setHasPlan] = useState<boolean>(true);

  // Memoize week range calculation
  const weekRange = useMemo(() => getThisWeekRange(), []);

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
          workouts = planRes.data.workouts || [];
          planExists = true;
          setHasPlan(true);
        } catch (planError: any) {
          // Check if it's a 404 (no plan) vs other error
          if (planError.response?.status === 404) {
            planExists = false;
            setHasPlan(false);
            workouts = [];
          } else {
            // Other error - log it but continue
            console.error('Error fetching plan:', planError);
            setHasPlan(false);
            workouts = [];
          }
        }

        // Fetch activities regardless of plan status
        const activitiesRes = await api.get('/api/activities/');
        const allActivities: Activity[] = activitiesRes.data?.activities || [];

        // Filter activities for this week
        const weekActivities = allActivities.filter((act: Activity) => {
          const actDate = new Date(act.date);
          return actDate >= weekStart && actDate <= weekEnd;
        });

        // Process week data
        const processedDays = processWeekData(workouts, weekActivities, weekStart, weekEnd);
        setWeekDays(processedDays);

        // Calculate progress
        const progress = calculateWeeklyProgress(processedDays);

        // Set selected date to today if it has a workout, otherwise first day with workout
        const todayDay = processedDays.find((d) => d.isToday);
        if (todayDay) {
          setSelectedDate(todayDay.dateStr);
        } else {
          const firstWorkoutDay = processedDays.find((d) => d.workout);
          if (firstWorkoutDay) {
            setSelectedDate(firstWorkoutDay.dateStr);
          } else if (processedDays.length > 0) {
            // If no workouts, select today
            setSelectedDate(todayDay?.dateStr || processedDays[0].dateStr);
          }
        }
      } catch (error) {
        console.error('Failed to fetch week data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchWeekData();
  }, [isReady, userId, api, weekRange]);

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
        <div className="max-w-4xl mx-auto px-4 py-6">
          {/* Week Timeline */}
          <div className={`${WEEK_TIMELINE_STYLES.container} ${WEEK_TIMELINE_STYLES.containerPadding} mb-6`}>
            <h2 className={WEEK_TIMELINE_STYLES.title}>THIS WEEK</h2>

            <div className={WEEK_TIMELINE_STYLES.dayGrid}>
              {weekDays.map((day) => (
                <WeekDayButton
                  key={day.dateStr}
                  date={day.date}
                  dateStr={day.dateStr}
                  isSelected={day.dateStr === selectedDate}
                  isCompleted={day.isCompleted}
                  isRestDay={day.isRestDay}
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

          {/* Empty State - No Plan */}
          {!hasPlan && (
            <div className={WEEK_TIMELINE_STYLES.emptyStateSection}>
              <div className={WEEK_TIMELINE_STYLES.emptyStateIcon}>📅</div>
              <h3 className={WEEK_TIMELINE_STYLES.emptyStateTitle}>
                No Training Plan
              </h3>
              <p className={WEEK_TIMELINE_STYLES.emptyStateText}>
                You don't have an active training plan yet. Create a personalized plan to start tracking your workouts and progress toward your race goals.
              </p>
              <Link
                to="/plan/new"
                className={WEEK_TIMELINE_STYLES.emptyStateButton}
              >
                Create Training Plan
                <svg className="ml-2 w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </Link>
            </div>
          )}

          {/* Details Panel - Only show if plan exists */}
          {hasPlan && selectedDay && (
            <div className={WEEK_TIMELINE_STYLES.detailsPanel}>
              <WorkoutDetails
                date={selectedDay.date}
                dateStr={selectedDay.dateStr}
                workout={selectedDay.workout}
                activity={selectedDay.activity}
                isCompleted={selectedDay.isCompleted}
                isRestDay={selectedDay.isRestDay}
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

export default HomeScreen;
