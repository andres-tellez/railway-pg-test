// src/schemas/onboardingSchema.ts
import { z } from 'zod';

// 1) Hoist literals + "as const"
export const Days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'] as const;
export const Races = ['5K','10K','Half Marathon','Marathon','Ultra',"Haven't raced yet"] as const;
export const Distances = ['5K','10K','Half Marathon','Marathon','Ultra','Other'] as const;
export const RunnerLevels = ['Beginner','Intermediate','Expert'] as const;
export const AgeGroups = ['Under 18','18-24','25-34','35-44','45-54','55+'] as const;
export const RunPrefs = ['Distance','Time','No preference'] as const;
export const Goals = ['General fitness','Run a race','Lose weight','Run faster','Other'] as const;
export const Motivations = ['Health','Competition','Stress relief','Enjoyment','Other'] as const;

// 2) Create Zod enums from those tuples
const DaysEnum = z.enum(Days);
const RaceEnum = z.enum(Races);
const DistanceEnum = z.enum(Distances);
const RunnerLevelEnum = z.enum(RunnerLevels);
const AgeGroupEnum = z.enum(AgeGroups);
const RunPrefEnum = z.enum(RunPrefs);
const GoalEnum = z.enum(Goals);
const MotivationEnum = z.enum(Motivations);

// 3) Schema (aligned with your UI + multi-step)
export const onboardingSchema = z.object({
  user_id: z.string().uuid().optional(),  // ✅ enforce UUID

  runnerLevel: RunnerLevelEnum,
  mainGoal: GoalEnum.optional(),
  runPreference: RunPrefEnum.optional(),
  ageGroup: AgeGroupEnum.optional(),

  raceHistory: z.boolean().default(false),
  pastRaces: z.array(RaceEnum).default([]),

  raceDate: z.string().optional(),
  raceDistance: DistanceEnum.optional(),

  trainingDays: z.array(DaysEnum).min(1, 'Select at least one training day'),

  height: z
    .object({
      feet: z.number().int().min(3, 'Min 3ft').max(8, 'Max 8ft').optional(),
      inches: z.number().int().min(0).max(11).optional(),
    })
    .optional(),

  weight: z.number().min(80).max(400).optional(),

  motivation: z.array(MotivationEnum).min(1, 'Select at least one motivation'),
}).refine(
  (data) => {
    if (!data.height) return true;
    const { feet, inches } = data.height;
    const hasFeet = typeof feet === 'number';
    const hasInches = typeof inches === 'number';
    return (hasFeet && hasInches) || (!hasFeet && !hasInches);
  },
  { path: ['height'], message: 'Please enter both height (feet and inches) or leave blank' }
);

// 2b) Value-to-label mappings (for UI display)
export const DayLabels: Record<typeof Days[number], string> = {
  Mon: 'Mon',
  Tue: 'Tue',
  Wed: 'Wed',
  Thu: 'Thu',
  Fri: 'Fri',
  Sat: 'Sat',
  Sun: 'Sun',
};

export const RaceLabels: Record<typeof Races[number], string> = {
  '5K': '5K',
  '10K': '10K',
  'Half Marathon': 'Half Marathon',
  'Marathon': 'Marathon',
  'Ultra': 'Ultra',
  "Haven't raced yet": "Haven't raced yet",
};

export const DistanceLabels: Record<typeof Distances[number], string> = {
  '5K': '5K',
  '10K': '10K',
  'Half Marathon': 'Half Marathon',
  'Marathon': 'Marathon',
  'Ultra': 'Ultra',
  'Other': 'Other',
};

export const RunnerLevelLabels: Record<typeof RunnerLevels[number], string> = {
  Beginner: 'Beginner',
  Intermediate: 'Intermediate',
  Expert: 'Expert',
};

export const AgeGroupLabels: Record<typeof AgeGroups[number], string> = {
  'Under 18': 'Under 18',
  '18-24': '18–24',
  '25-34': '25–34',
  '35-44': '35–44',
  '45-54': '45–54',
  '55+': '55+',
};

export const RunPrefLabels: Record<typeof RunPrefs[number], string> = {
  Distance: 'Distance',
  Time: 'Time',
  'No preference': 'No preference',
};

export const GoalLabels: Record<typeof Goals[number], string> = {
  'General fitness': 'General fitness',
  'Run a race': 'Run a race',
  'Lose weight': 'Lose weight',
  'Run faster': 'Run faster',
  'Other': 'Other',
};

export const MotivationLabels: Record<typeof Motivations[number], string> = {
  Health: 'Health',
  Competition: 'Competition',
  'Stress relief': 'Stress relief',
  Enjoyment: 'Enjoyment',
  Other: 'Other',
};




export type OnboardingFormData = z.infer<typeof onboardingSchema>;
