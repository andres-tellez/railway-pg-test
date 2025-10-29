// frontend/src/schemas/planSchema.ts

import { z } from "zod";

export const planSchema = z.object({
  // Race details (required)
  race_date: z.string().min(1, "Race date is required"),
  race_distance: z.string().default("Marathon"),
  race_name: z.string().optional(),
  race_location: z.string().optional(),

  // Plan goals (required)
  primary_goal: z.enum(["Just Finish", "Target Time"], {
    errorMap: () => ({ message: "Please select a primary goal" })
  }),
  marathon_experience: z.enum(["First", "Some", "Experienced"], {
    errorMap: () => ({ message: "Please select your marathon experience level" })
  }),
  target_time: z.string().optional(),

  // Training schedule (required)
  training_days: z.array(z.string()).min(1, "Select at least one training day"),

  // Additional notes (optional)
  notes: z.string().optional(),
}).refine((data) => {
  // If primary_goal is "Target Time", target_time is required
  if (data.primary_goal === "Target Time" && !data.target_time) {
    return false;
  }
  return true;
}, {
  message: "Target time is required when selecting 'Target Time' as your goal",
  path: ["target_time"]
});

export type PlanFormData = z.infer<typeof planSchema>;

// Helper types for form data
export type PrimaryGoal = "Just Finish" | "Target Time";
export type MarathonExperience = "First" | "Some" | "Experienced";

// Training days options
export const trainingDaysOptions = [
  { value: "Mon", label: "Monday" },
  { value: "Tue", label: "Tuesday" },
  { value: "Wed", label: "Wednesday" },
  { value: "Thu", label: "Thursday" },
  { value: "Fri", label: "Friday" },
  { value: "Sat", label: "Saturday" },
  { value: "Sun", label: "Sunday" },
];

// Primary goal options
export const primaryGoalOptions = [
  { value: "Just Finish" as const, label: "Just Finish" },
  { value: "Target Time" as const, label: "Target Time" },
];

// Marathon experience options
export const marathonExperienceOptions = [
  { value: "First" as const, label: "First marathon (never completed one)" },
  { value: "Some" as const, label: "Some experience (completed 1-2 marathons)" },
  { value: "Experienced" as const, label: "Experienced (completed 3+ marathons)" },
];
