/**
 * Node.js test script for date matching logic
 * Run with: node test-date-logic.js
 */

// Mock date-fns functions for Node.js
const format = (date, pattern) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return pattern.replace('yyyy', year).replace('MM', month).replace('dd', day);
};

const startOfWeek = (date, options) => {
  const d = new Date(date);
  const day = d.getDay();
  const diff = (day < options.weekStartsOn ? 7 : 0) + day - options.weekStartsOn;
  d.setDate(d.getDate() - diff);
  d.setHours(0, 0, 0, 0);
  return d;
};

const endOfWeek = (date, options) => {
  const start = startOfWeek(date, options);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  end.setHours(23, 59, 59, 999);
  return end;
};

// Test date normalization
function normalizeDateString(dateStr) {
  return dateStr.split('T')[0];
}

// Test getThisWeekRange
function testGetThisWeekRange(testDate = '2024-11-12') {
  console.log('\n🧪 Testing getThisWeekRange()');
  console.log('='.repeat(60));
  
  const [year, month, day] = testDate.split('-').map(Number);
  const today = new Date(year, month - 1, day);
  const todayOnly = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  
  const weekStart = startOfWeek(todayOnly, { weekStartsOn: 1 });
  const weekEnd = endOfWeek(todayOnly, { weekStartsOn: 1 });
  
  const weekStartOnly = new Date(weekStart.getFullYear(), weekStart.getMonth(), weekStart.getDate());
  const weekEndOnly = new Date(weekEnd.getFullYear(), weekEnd.getMonth(), weekEnd.getDate());
  
  const weekStartStr = format(weekStartOnly, 'yyyy-MM-dd');
  const weekEndStr = format(weekEndOnly, 'yyyy-MM-dd');
  
  console.log(`Test Date: ${testDate}`);
  console.log(`Week Start: ${weekStartStr} (Day: ${weekStartOnly.getDay()}, should be 1=Monday)`);
  console.log(`Week End: ${weekEndStr} (Day: ${weekEndOnly.getDay()}, should be 0=Sunday)`);
  
  const passed = weekStartOnly.getDay() === 1 && weekEndOnly.getDay() === 0;
  console.log(`Result: ${passed ? '✅ PASSED' : '❌ FAILED'}`);
  
  return passed;
}

// Test date matching
function testDateMatching() {
  console.log('\n🧪 Testing Date Matching');
  console.log('='.repeat(60));
  
  function matchActivityToWorkout(activity, workout) {
    const activityDateStr = activity.date.split('T')[0];
    const workoutDateStr = workout.date.split('T')[0];
    
    const [activityYear, activityMonth, activityDay] = activityDateStr.split('-').map(Number);
    const [workoutYear, workoutMonth, workoutDay] = workoutDateStr.split('-').map(Number);
    
    const activityDateLocal = new Date(activityYear, activityMonth - 1, activityDay);
    const workoutDateLocal = new Date(workoutYear, workoutMonth - 1, workoutDay);
    
    const daysDiff = Math.abs(
      (activityDateLocal.getTime() - workoutDateLocal.getTime()) / (1000 * 60 * 60 * 24)
    );
    
    if (daysDiff > 1) return false;
    
    const distanceDiff = Math.abs(activity.distance_miles - workout.miles) / workout.miles;
    return distanceDiff <= 0.3;
  }
  
  const tests = [
    {
      name: 'Same day (date-only)',
      workout: { date: '2024-11-12', miles: 5 },
      activity: { date: '2024-11-12T00:00:00', distance_miles: 5 },
      expected: true,
    },
    {
      name: 'Same day (datetime)',
      workout: { date: '2024-11-12', miles: 5 },
      activity: { date: '2024-11-12T14:30:00', distance_miles: 5 },
      expected: true,
    },
    {
      name: 'Next day (should not match)',
      workout: { date: '2024-11-12', miles: 5 },
      activity: { date: '2024-11-13T00:00:00', distance_miles: 5 },
      expected: false,
    },
    {
      name: 'Previous day (should not match)',
      workout: { date: '2024-11-12', miles: 5 },
      activity: { date: '2024-11-11T00:00:00', distance_miles: 5 },
      expected: false,
    },
  ];
  
  let passed = 0;
  let failed = 0;
  
  tests.forEach((test, idx) => {
    const result = matchActivityToWorkout(test.activity, test.workout);
    const testPassed = result === test.expected;
    
    console.log(`\nTest ${idx + 1}: ${test.name}`);
    console.log(`  Workout: ${test.workout.date}, Activity: ${test.activity.date}`);
    console.log(`  Expected: ${test.expected}, Got: ${result}`);
    console.log(`  Result: ${testPassed ? '✅ PASSED' : '❌ FAILED'}`);
    
    if (testPassed) passed++;
    else failed++;
  });
  
  console.log(`\nSummary: ${passed}/${tests.length} tests passed`);
  
  return failed === 0;
}

// Test date string normalization
function testDateNormalization() {
  console.log('\n🧪 Testing Date Normalization');
  console.log('='.repeat(60));
  
  const tests = [
    { input: '2024-11-12', expected: '2024-11-12' },
    { input: '2024-11-12T00:00:00', expected: '2024-11-12' },
    { input: '2024-11-12T14:30:00', expected: '2024-11-12' },
  ];
  
  let passed = 0;
  
  tests.forEach((test, idx) => {
    const result = normalizeDateString(test.input);
    const testPassed = result === test.expected;
    
    console.log(`Test ${idx + 1}: "${test.input}" -> "${result}" (expected: "${test.expected}")`);
    console.log(`  Result: ${testPassed ? '✅ PASSED' : '❌ FAILED'}`);
    
    if (testPassed) passed++;
  });
  
  console.log(`\nSummary: ${passed}/${tests.length} tests passed`);
  
  return passed === tests.length;
}

// Run all tests
console.log('🚀 Running Date Logic Tests');
console.log('='.repeat(60));

const test1 = testDateNormalization();
const test2 = testDateMatching();
const test3 = testGetThisWeekRange('2024-11-12'); // Tuesday
const test4 = testGetThisWeekRange('2024-11-10'); // Sunday
const test5 = testGetThisWeekRange('2024-11-11'); // Monday

console.log('\n' + '='.repeat(60));
console.log('📊 Final Results');
console.log('='.repeat(60));
console.log(`Date Normalization: ${test1 ? '✅ PASSED' : '❌ FAILED'}`);
console.log(`Date Matching: ${test2 ? '✅ PASSED' : '❌ FAILED'}`);
console.log(`Week Range (Tuesday): ${test3 ? '✅ PASSED' : '❌ FAILED'}`);
console.log(`Week Range (Sunday): ${test4 ? '✅ PASSED' : '❌ FAILED'}`);
console.log(`Week Range (Monday): ${test5 ? '✅ PASSED' : '❌ FAILED'}`);

const allPassed = test1 && test2 && test3 && test4 && test5;
console.log('\n' + '='.repeat(60));
console.log(`Overall: ${allPassed ? '✅ ALL TESTS PASSED' : '❌ SOME TESTS FAILED'}`);
console.log('='.repeat(60));

process.exit(allPassed ? 0 : 1);

