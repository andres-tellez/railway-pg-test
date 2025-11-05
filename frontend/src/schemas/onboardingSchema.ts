// src/schemas/onboardingSchema.ts
import { z } from 'zod';

// 1) Hoist literals + "as const"
export const Days = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'] as const;
export const Distances = ['5K','10K','Half Marathon','Marathon','Ultra','Other'] as const;
export const AgeGroups = ['18-29','30-39','40-49','50-59','60+'] as const;
export const Motivations = ['Health','Stress relief','Competition','Enjoyment','Weight loss','Other'] as const;

// 2) Create Zod enums from those tuples
const DaysEnum = z.enum(Days);
const DistanceEnum = z.enum(Distances);
const AgeGroupEnum = z.enum(AgeGroups);
const MotivationEnum = z.enum(Motivations);

// 3) Schema for User Profile form
export const onboardingSchema = z.object({
  user_id: z.string().uuid().optional(),  // ✅ enforce UUID

  // Motivation
  motivation: z.array(MotivationEnum).min(1, 'Select at least one motivation').optional(),

  // Physical Stats
  ageGroup: AgeGroupEnum,
  height: z
    .object({
      feet: z.number().int().min(3, 'Min 3ft').max(8, 'Max 8ft'),
      inches: z.number().int().min(0).max(11),
    }),
  weight: z.number().min(80).max(400).optional(),
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

export const DistanceLabels: Record<typeof Distances[number], string> = {
  '5K': '5K',
  '10K': '10K',
  'Half Marathon': 'Half Marathon',
  'Marathon': 'Marathon',
  'Ultra': 'Ultra',
  'Other': 'Other',
};

export const AgeGroupLabels: Record<typeof AgeGroups[number], string> = {
  '18-29': '18–29',
  '30-39': '30–39',
  '40-49': '40–49',
  '50-59': '50–59',
  '60+': '60+',
};

export const MotivationLabels: Record<typeof Motivations[number], string> = {
  'Health': 'Health',
  'Stress relief': 'Stress relief',
  'Competition': 'Competition',
  'Enjoyment': 'Enjoyment',
  'Weight loss': 'Weight loss',
  'Other': 'Other',
};




export type OnboardingFormData = z.infer<typeof onboardingSchema>;
