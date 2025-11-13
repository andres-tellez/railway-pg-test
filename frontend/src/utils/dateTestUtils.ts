/**
 * Date Testing Utilities
 * 
 * Test date matching logic before deployment.
 * Run these tests in the browser console or use the test page.
 */

import { format } from 'date-fns';
import { getThisWeekRange, processWeekData, matchActivityToWorkout } from './weekTimelineUtils';
import type { Workout, Activity, WeekDay } from './weekTimelineUtils';

/**
 * Test data generator - creates mock workouts and activities
 */
export function createTestData(testDate: string = '2024-11-12'): {
  workouts: Workout[];
  activities: Activity[];
} {
  // Parse test date
  const [year, month, day] = testDate.split('-').map(Number);
  const baseDate = new Date(year, month - 1, day);
  
  // Create workouts for the week (Monday to Sunday)
  const workouts: Workout[] = [];
  const activities: Activity[] = [];
  
  // Monday (workout)
  const monday = new Date(baseDate);
  monday.setDate(baseDate.getDate() - (baseDate.getDay() === 0 ? 6 : baseDate.getDay() - 1));
  
  for (let i = 0; i < 7; i++) {
    const date = new Date(monday);
    date.setDate(monday.getDate() + i);
    const dateStr = format(date, 'yyyy-MM-dd');
    
    // Add workout on Mon, Wed, Fri
    if (i % 2 === 0) {
      workouts.push({
        date: dateStr,
        workout_type: i === 0 ? 'Easy' : i === 2 ? 'Tempo' : 'Long Run',
        miles: 5 + i * 2,
        description: `Test workout for ${dateStr}`,
      });
      
      // Add activity for Monday (completed)
      if (i === 0) {
        activities.push({
          activity_id: 1000 + i,
          date: dateStr + 'T00:00:00', // Simulate datetime string from API
          distance_miles: 5,
          name: `Test Run ${dateStr}`,
          type: 'Run',
        });
      }
    }
  }
  
  return { workouts, activities };
}

/**
 * Test date matching with various date formats
 */
export function testDateMatching(): {
  passed: number;
  failed: number;
  results: Array<{ test: string; passed: boolean; details: string }>;
} {
  const results: Array<{ test: string; passed: boolean; details: string }> = [];
  let passed = 0;
  let failed = 0;
  
  // Test 1: Date-only string matching
  const test1 = {
    workout: { date: '2024-11-12', workout_type: 'Easy', miles: 5 } as Workout,
    activity: { activity_id: 1, date: '2024-11-12T00:00:00', distance_miles: 5, name: 'Test', type: 'Run' } as Activity,
  };
  const match1 = matchActivityToWorkout(test1.activity, test1.workout);
  const passed1 = match1 === true;
  results.push({
    test: 'Date-only string matching (same day)',
    passed: passed1,
    details: `Workout: ${test1.workout.date}, Activity: ${test1.activity.date}, Match: ${match1}`,
  });
  if (passed1) passed++; else failed++;
  
  // Test 2: Datetime string matching
  const test2 = {
    workout: { date: '2024-11-12', workout_type: 'Easy', miles: 5 } as Workout,
    activity: { activity_id: 2, date: '2024-11-12T14:30:00', distance_miles: 5, name: 'Test', type: 'Run' } as Activity,
  };
  const match2 = matchActivityToWorkout(test2.activity, test2.workout);
  const passed2 = match2 === true;
  results.push({
    test: 'Datetime string matching (same day, different time)',
    passed: passed2,
    details: `Workout: ${test2.workout.date}, Activity: ${test2.activity.date}, Match: ${match2}`,
  });
  if (passed2) passed++; else failed++;
  
  // Test 3: Next day (should not match)
  const test3 = {
    workout: { date: '2024-11-12', workout_type: 'Easy', miles: 5 } as Workout,
    activity: { activity_id: 3, date: '2024-11-13T00:00:00', distance_miles: 5, name: 'Test', type: 'Run' } as Activity,
  };
  const match3 = matchActivityToWorkout(test3.activity, test3.workout);
  const passed3 = match3 === false;
  results.push({
    test: 'Next day (should not match)',
    passed: passed3,
    details: `Workout: ${test3.workout.date}, Activity: ${test3.activity.date}, Match: ${match3} (should be false)`,
  });
  if (passed3) passed++; else failed++;
  
  // Test 4: Previous day (should not match)
  const test4 = {
    workout: { date: '2024-11-12', workout_type: 'Easy', miles: 5 } as Workout,
    activity: { activity_id: 4, date: '2024-11-11T00:00:00', distance_miles: 5, name: 'Test', type: 'Run' } as Activity,
  };
  const match4 = matchActivityToWorkout(test4.activity, test4.workout);
  const passed4 = match4 === false;
  results.push({
    test: 'Previous day (should not match)',
    passed: passed4,
    details: `Workout: ${test4.workout.date}, Activity: ${test4.activity.date}, Match: ${match4} (should be false)`,
  });
  if (passed4) passed++; else failed++;
  
  return { passed, failed, results };
}

/**
 * Test week range calculation
 */
export function testWeekRange(testDate: string = '2024-11-12'): {
  passed: boolean;
  details: {
    testDate: string;
    weekStart: string;
    weekEnd: string;
    weekStartDay: number;
    weekEndDay: number;
  };
} {
  const [year, month, day] = testDate.split('-').map(Number);
  const testDateObj = new Date(year, month - 1, day);
  
  // Override getThisWeekRange to use test date
  const today = testDateObj;
  const weekStart = new Date(today);
  weekStart.setDate(today.getDate() - (today.getDay() === 0 ? 6 : today.getDay() - 1));
  weekStart.setHours(0, 0, 0, 0);
  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekStart.getDate() + 6);
  weekEnd.setHours(23, 59, 59, 999);
  
  const weekStartStr = format(weekStart, 'yyyy-MM-dd');
  const weekEndStr = format(weekEnd, 'yyyy-MM-dd');
  
  // Verify weekStart is Monday (day 1)
  const weekStartDay = weekStart.getDay();
  const weekEndDay = weekEnd.getDay();
  const passed = weekStartDay === 1 && weekEndDay === 0;
  
  return {
    passed,
    details: {
      testDate,
      weekStart: weekStartStr,
      weekEnd: weekEndStr,
      weekStartDay,
      weekEndDay,
    },
  };
}

/**
 * Test processWeekData with mock data
 */
export function testProcessWeekData(testDate: string = '2024-11-12'): {
  passed: boolean;
  details: {
    testDate: string;
    weekDays: WeekDay[];
    workoutsMatched: number;
    expectedWorkouts: number;
  };
} {
  const { workouts, activities } = createTestData(testDate);
  
  // Calculate week range
  const [year, month, day] = testDate.split('-').map(Number);
  const testDateObj = new Date(year, month - 1, day);
  const weekStart = new Date(testDateObj);
  weekStart.setDate(testDateObj.getDate() - (testDateObj.getDay() === 0 ? 6 : testDateObj.getDay() - 1));
  weekStart.setHours(0, 0, 0, 0);
  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekStart.getDate() + 6);
  weekEnd.setHours(23, 59, 59, 999);
  
  const weekDays = processWeekData(workouts, activities, weekStart, weekEnd);
  
  const workoutsMatched = weekDays.filter(d => d.workout).length;
  const expectedWorkouts = workouts.length;
  const passed = workoutsMatched === expectedWorkouts;
  
  return {
    passed,
    details: {
      testDate,
      weekDays: weekDays.map(d => ({
        dateStr: d.dateStr,
        hasWorkout: !!d.workout,
        workoutDate: d.workout?.date,
        isCompleted: d.isCompleted,
      })),
      workoutsMatched,
      expectedWorkouts,
    },
  };
}

/**
 * Run all tests and log results
 */
export function runAllDateTests(testDate: string = '2024-11-12'): void {
  console.log('🧪 Running Date Matching Tests...');
  console.log('='.repeat(60));
  
  const matchingTests = testDateMatching();
  console.log(`\n📋 Date Matching Tests: ${matchingTests.passed}/${matchingTests.passed + matchingTests.failed} passed`);
  matchingTests.results.forEach((result, idx) => {
    const icon = result.passed ? '✅' : '❌';
    console.log(`${icon} Test ${idx + 1}: ${result.test}`);
    console.log(`   ${result.details}`);
  });
  
  console.log('\n' + '='.repeat(60));
  const weekRangeTest = testWeekRange(testDate);
  console.log(`\n📅 Week Range Test: ${weekRangeTest.passed ? '✅ PASSED' : '❌ FAILED'}`);
  console.log(`   Test Date: ${weekRangeTest.details.testDate}`);
  console.log(`   Week Start: ${weekRangeTest.details.weekStart} (Day: ${weekRangeTest.details.weekStartDay}, should be 1=Monday)`);
  console.log(`   Week End: ${weekRangeTest.details.weekEnd} (Day: ${weekRangeTest.details.weekEndDay}, should be 0=Sunday)`);
  
  console.log('\n' + '='.repeat(60));
  const processTest = testProcessWeekData(testDate);
  console.log(`\n🔄 Process Week Data Test: ${processTest.passed ? '✅ PASSED' : '❌ FAILED'}`);
  console.log(`   Test Date: ${processTest.details.testDate}`);
  console.log(`   Workouts Matched: ${processTest.details.workoutsMatched}/${processTest.details.expectedWorkouts}`);
  console.log(`   Week Days:`);
  processTest.details.weekDays.forEach(day => {
    const workoutInfo = day.hasWorkout 
      ? `Workout: ${day.workoutDate} ${day.isCompleted ? '✓' : ''}`
      : 'No workout';
    console.log(`     ${day.dateStr}: ${workoutInfo}`);
  });
  
  console.log('\n' + '='.repeat(60));
  console.log('\n✨ Test Summary:');
  const totalPassed = matchingTests.passed + (weekRangeTest.passed ? 1 : 0) + (processTest.passed ? 1 : 0);
  const totalTests = matchingTests.passed + matchingTests.failed + 2;
  console.log(`   ${totalPassed}/${totalTests} test suites passed`);
  
  if (totalPassed === totalTests) {
    console.log('   🎉 All tests passed!');
  } else {
    console.log('   ⚠️  Some tests failed. Review the output above.');
  }
}

/**
 * Make test functions available globally for browser console
 */
if (typeof window !== 'undefined') {
  (window as any).dateTestUtils = {
    runAllDateTests,
    testDateMatching,
    testWeekRange,
    testProcessWeekData,
    createTestData,
  };
  console.log('🧪 Date test utilities loaded! Run window.dateTestUtils.runAllDateTests() in the console.');
}

