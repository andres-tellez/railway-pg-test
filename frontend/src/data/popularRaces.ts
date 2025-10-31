// Popular marathons and half marathons database
// This can be expanded with more races over time

export type TerrainType = "Flat" | "Rolling" | "Hilly" | "Mountainous";
export type CourseType = "Point-to-Point" | "Loop" | "Out-and-Back" | "Multi-Loop";
export type RaceType = "Road" | "Trail" | "Mixed Surface";

export interface Race {
  name: string;
  location: string;
  distance: "Marathon" | "Half Marathon";
  // Optional metadata
  terrain?: TerrainType;
  elevation_gain?: number; // in feet
  course_type?: CourseType;
  race_type?: RaceType;
  difficulty_rating?: number; // 1-5 scale
  typical_weather?: string; // e.g., "Cool, 45-60°F"
  qualification_required?: boolean;
}

export const popularRaces: Race[] = [
  // Major Marathons
  {
    name: "Boston Marathon",
    location: "Boston, MA",
    distance: "Marathon",
    terrain: "Rolling",
    elevation_gain: 430,
    course_type: "Point-to-Point",
    race_type: "Road",
    difficulty_rating: 4,
    qualification_required: true,
    typical_weather: "Cool, 40-55°F, variable"
  },
  {
    name: "New York City Marathon",
    location: "New York, NY",
    distance: "Marathon",
    terrain: "Rolling",
    elevation_gain: 890,
    course_type: "Point-to-Point",
    race_type: "Road",
    difficulty_rating: 4,
    typical_weather: "Cool, 45-55°F"
  },
  {
    name: "Chicago Marathon",
    location: "Chicago, IL",
    distance: "Marathon",
    terrain: "Flat",
    elevation_gain: 200,
    course_type: "Loop",
    race_type: "Road",
    difficulty_rating: 2,
    typical_weather: "Cool, 40-55°F, windy"
  },
  {
    name: "London Marathon",
    location: "London, UK",
    distance: "Marathon",
    terrain: "Flat",
    elevation_gain: 300,
    course_type: "Point-to-Point",
    race_type: "Road",
    difficulty_rating: 2,
    typical_weather: "Cool, 45-60°F, potentially rainy"
  },
  {
    name: "Berlin Marathon",
    location: "Berlin, Germany",
    distance: "Marathon",
    terrain: "Flat",
    elevation_gain: 200,
    course_type: "Point-to-Point",
    race_type: "Road",
    difficulty_rating: 1,
    typical_weather: "Cool, 45-60°F",
    qualification_required: false
  },
  {
    name: "Tokyo Marathon",
    location: "Tokyo, Japan",
    distance: "Marathon",
    terrain: "Flat",
    elevation_gain: 250,
    course_type: "Loop",
    race_type: "Road",
    difficulty_rating: 2,
    typical_weather: "Cool, 40-50°F, humid"
  },
  {
    name: "Los Angeles Marathon",
    location: "Los Angeles, CA",
    distance: "Marathon",
    terrain: "Rolling",
    elevation_gain: 850,
    course_type: "Point-to-Point",
    difficulty_rating: 3
  },
  {
    name: "Marine Corps Marathon",
    location: "Washington, DC",
    distance: "Marathon",
    terrain: "Rolling",
    elevation_gain: 600,
    course_type: "Point-to-Point",
    difficulty_rating: 3
  },
  {
    name: "Houston Marathon",
    location: "Houston, TX",
    distance: "Marathon",
    terrain: "Flat",
    elevation_gain: 150,
    course_type: "Loop",
    difficulty_rating: 2,
    typical_weather: "Warm, 55-70°F, humid"
  },
  {
    name: "Philadelphia Marathon",
    location: "Philadelphia, PA",
    distance: "Marathon",
    terrain: "Flat",
    elevation_gain: 300,
    course_type: "Loop",
    difficulty_rating: 2
  },
  {
    name: "Portland Marathon",
    location: "Portland, OR",
    distance: "Marathon",
    terrain: "Rolling",
    elevation_gain: 700,
    difficulty_rating: 3
  },
  {
    name: "Seattle Marathon",
    location: "Seattle, WA",
    distance: "Marathon",
    terrain: "Hilly",
    elevation_gain: 1200,
    difficulty_rating: 4,
    typical_weather: "Cool, 40-55°F, potentially rainy"
  },
  {
    name: "San Francisco Marathon",
    location: "San Francisco, CA",
    distance: "Marathon",
    terrain: "Hilly",
    elevation_gain: 1400,
    difficulty_rating: 5,
    typical_weather: "Cool, 50-65°F, foggy"
  },
  { name: "Miami Marathon", location: "Miami, FL", distance: "Marathon" },
  { name: "Disney World Marathon", location: "Orlando, FL", distance: "Marathon" },
  { name: "Walt Disney World Marathon", location: "Orlando, FL", distance: "Marathon" },
  {
    name: "Austin Marathon",
    location: "Austin, TX",
    distance: "Marathon",
    terrain: "Hilly",
    elevation_gain: 1100,
    course_type: "Loop",
    difficulty_rating: 4,
    typical_weather: "Warm, 55-70°F, humid"
  },
  { name: "Dallas Marathon", location: "Dallas, TX", distance: "Marathon" },
  { name: "Detroit Marathon", location: "Detroit, MI", distance: "Marathon" },
  { name: "Cleveland Marathon", location: "Cleveland, OH", distance: "Marathon" },
  { name: "Minneapolis Marathon", location: "Minneapolis, MN", distance: "Marathon" },
  { name: "Denver Marathon", location: "Denver, CO", distance: "Marathon" },
  { name: "Phoenix Marathon", location: "Phoenix, AZ", distance: "Marathon" },
  { name: "Las Vegas Marathon", location: "Las Vegas, NV", distance: "Marathon" },
  { name: "Honolulu Marathon", location: "Honolulu, HI", distance: "Marathon" },
  { name: "Paris Marathon", location: "Paris, France", distance: "Marathon" },
  { name: "Amsterdam Marathon", location: "Amsterdam, Netherlands", distance: "Marathon" },
  { name: "Rome Marathon", location: "Rome, Italy", distance: "Marathon" },
  { name: "Madrid Marathon", location: "Madrid, Spain", distance: "Marathon" },
  { name: "Barcelona Marathon", location: "Barcelona, Spain", distance: "Marathon" },
  { name: "Dublin Marathon", location: "Dublin, Ireland", distance: "Marathon" },
  { name: "Edinburgh Marathon", location: "Edinburgh, Scotland", distance: "Marathon" },
  { name: "Toronto Marathon", location: "Toronto, Canada", distance: "Marathon" },
  { name: "Vancouver Marathon", location: "Vancouver, Canada", distance: "Marathon" },
  { name: "Sydney Marathon", location: "Sydney, Australia", distance: "Marathon" },
  { name: "Melbourne Marathon", location: "Melbourne, Australia", distance: "Marathon" },

  // Popular Half Marathons
  { name: "Disney World Half Marathon", location: "Orlando, FL", distance: "Half Marathon" },
  { name: "Rock 'n' Roll Las Vegas Half Marathon", location: "Las Vegas, NV", distance: "Half Marathon" },
  { name: "Brooklyn Half Marathon", location: "Brooklyn, NY", distance: "Half Marathon" },
  { name: "Philadelphia Half Marathon", location: "Philadelphia, PA", distance: "Half Marathon" },
  { name: "Austin Half Marathon", location: "Austin, TX", distance: "Half Marathon" },
  { name: "Detroit Free Press Half Marathon", location: "Detroit, MI", distance: "Half Marathon" },
  { name: "Seattle Half Marathon", location: "Seattle, WA", distance: "Half Marathon" },
  { name: "San Francisco Half Marathon", location: "San Francisco, CA", distance: "Half Marathon" },
  { name: "Chicago Half Marathon", location: "Chicago, IL", distance: "Half Marathon" },
  { name: "Miami Half Marathon", location: "Miami, FL", distance: "Half Marathon" },
];

/**
 * Search races by name (case-insensitive, partial match)
 */
export function searchRaces(query: string, maxResults: number = 10): Race[] {
  if (!query.trim()) return [];

  const lowerQuery = query.toLowerCase().trim();

  return popularRaces
    .filter(race =>
      race.name.toLowerCase().includes(lowerQuery) ||
      race.location.toLowerCase().includes(lowerQuery)
    )
    .slice(0, maxResults);
}
