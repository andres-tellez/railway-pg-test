import { z } from 'zod';

export const onboardingSchema = z.object({
  runnerLevel: z.enum(['Beginner', 'Intermediate', 'Expert']),

  raceHistory: z.boolean(),
  raceDate: z.string().optional(),
  raceDistance: z.enum(['5K', '10K', 'Half Marathon', 'Marathon', 'Ultra', 'Other']).optional(),

  pastRaces: z.array(
    z.enum(['5K', '10K', 'Half Marathon', 'Marathon', 'Ultra', "Haven't raced yet"])
  ),

  height: z.object({
    feet: z.number().min(3).max(8),
    inches: z.number().min(0).max(11),
  }),

  weight: z.number().min(80).max(400),

  trainingDaysPerWeek: z.number().min(1).max(7),
  trainingDays: z.array(
    z.enum(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
  ).optional(),

  mainGoal: z.enum(['General fitness', 'Run a race', 'Lose weight', 'Run faster', 'Other']),
  motivation: z.array(
    z.enum(['Health', 'Competition', 'Stress relief', 'Enjoyment', 'Other'])
  ),

  ageGroup: z.enum(['Under 18', '18-24', '25-34', '35-44', '45-54', '55+']),

  longestRun: z.number().optional(),

  runPreference: z.enum(['Distance', 'Time', 'No preference']),
  hasInjury: z.boolean(),
  injuryDetails: z.string().optional(),
});

export type OnboardingFormData = z.infer<typeof onboardingSchema>;
