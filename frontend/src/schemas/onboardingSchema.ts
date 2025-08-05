import { z } from 'zod';

export const onboardingSchema = z
  .object({
    user_id: z.string().min(1),

    runnerLevel: z.enum(['Beginner', 'Intermediate', 'Expert']).optional(),

    raceHistory: z.boolean(),
    pastRaces: z.array(
      z.enum(['5K', '10K', 'Half Marathon', 'Marathon', 'Ultra', "Haven't raced yet"])
    ),

    raceDate: z.string().optional(),
    raceDistance: z
      .enum(['5K', '10K', 'Half Marathon', 'Marathon', 'Ultra', 'Other'])
      .optional(),

    runPreference: z.enum(['Distance', 'Time', 'No preference']).optional(),

    weight: z.number().min(80).max(400).optional(),

    height: z
      .object({
        feet: z.number().min(3, "Min 3ft").max(8, "Max 8ft"),
        inches: z.number().min(0).max(11),
      }),

    ageGroup: z
      .enum(['Under 18', '18-24', '25-34', '35-44', '45-54', '55+'])
      .optional(),

    trainingDays: z.array(
      z.enum(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'])
    ),

    mainGoal: z
      .enum([
        'General fitness',
        'Run a race',
        'Lose weight',
        'Run faster',
        'Other',
      ])
      .optional(),

    motivation: z
      .array(
        z.enum([
          'Health',
          'Competition',
          'Stress relief',
          'Enjoyment',
          'Other',
        ])
      )
      .min(1, 'Select at least one motivation'),

    longestRun: z.number().optional(),

    hasInjury: z.boolean().nullable().refine(val => val !== null, {
      message: '',
    }),

    injuryDetails: z.string().optional(),
  })

  // ✅ Validate injury details if hasInjury is true
  .refine(
    (data) => !data.hasInjury || (data.injuryDetails && data.injuryDetails.trim().length > 0),
    {
      path: ['injuryDetails'],
      message: 'Please describe your injury',
    }
  )

  // ✅ Validate height completeness if present
  .refine(
    (data) => {
      if (!data.height) return true;
      return (
        typeof data.height.feet === 'number' &&
        typeof data.height.inches === 'number'
      );
    },
    {
      path: ['height'],
      message: 'Please enter both height (feet and inches)',
    }
  );

export type OnboardingFormData = z.infer<typeof onboardingSchema>;
