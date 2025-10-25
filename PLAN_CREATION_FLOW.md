# Plan Creation Flow - User Experience

## Overview

Users can create new marathon training plans from the My Plan calendar view. This flow allows them to update their goals, change race dates, or create plans for different marathons.

## User Flow

### Current State: User has a plan

**My Plan Calendar View** shows:

- Current training plan in calendar format
- Workouts scheduled for each day
- Race date highlighted
- "Create New Plan" button in top right

### Action: Click "Create New Plan"

**What happens:**

1. User navigates to `/onboarding` page
2. Form is **pre-filled** with their existing profile data:
   - Race date (they can change this)
   - Training days (they can modify)
   - Physical stats (age group, height, weight)
   - Race name/location (optional fields)
3. User can review and modify any fields

### Submission

**When user clicks "Submit" on onboarding:**

1. Backend validates the data
2. Backend generates a new training plan using GPT
3. New plan is saved to database with `is_active=True`
4. **Old plan is automatically deactivated** (but not deleted)
5. User is redirected to updated My Plan calendar

### Multi-Plan Management (Future)

**My Plans Dropdown** (to be added):

- Shows all user's plans
- "Active" badge on current plan
- "Switch to this plan" option for inactive plans
- "Delete this plan" option (with confirmation)
- "Create New Plan" button

**Plan Management Modal:**

- List all plans with race dates
- Visual indicator of which is active
- Actions: Switch, View Details, Delete

## Technical Flow

### Frontend Flow

```
My Plan Calendar View
    ↓
User clicks "Create New Plan" button
    ↓
Navigate to /onboarding (with existing profile data)
    ↓
User modifies fields and submits
    ↓
POST /api/user-profile (update profile)
    ↓
POST /api/plan/generate (create new plan)
    ↓
GET /api/plan/current (fetch new active plan)
    ↓
Redirect to My Plan calendar view
```

### Backend Flow

```
POST /api/plan/generate
    ↓
1. Fetch user's profile data
2. Fetch Strava activities (mileage data)
3. Calculate current weekly mileage
4. Assess readiness
5. Generate plan with GPT
6. Validate plan safety
7. Save plan (is_active=True)
8. Deactivate old plan (if exists)
9. Return new plan data
```

## Onboarding Pre-Fill Logic

**What gets pre-filled:**

- ✅ Race date (from current plan)
- ✅ Training days (from user profile)
- ✅ Age group (from user profile)
- ✅ Height (from user profile)
- ✅ Weight (from user profile, if provided)
- ✅ Race name (optional, from user profile)
- ✅ Race location (optional, from user profile)

**What doesn't get pre-filled:**

- Goal selection (always defaults to "Complete the Marathon")

**User can modify:**

- Any pre-filled field
- Add/remove training days
- Change race date
- Update physical stats

## Benefits

1. **User Control**: Users can create new plans whenever they need
2. **Flexible**: Can train for different marathons
3. **Non-Destructive**: Old plans are preserved (can be re-activated)
4. **Fast**: Pre-filling makes it quick to update just the race date
5. **Clear**: Button is prominent in the calendar view

## Future Enhancements

### Phase 2: Plan Management UI

- Add "My Plans" dropdown in navigation
- Show list of all plans with race dates
- Allow switching between plans
- Show "Active" badge
- Delete plans (with confirmation)

### Phase 3: Plan Comparison

- Side-by-side comparison of plans
- "Which plan should I use?" advisor
- Duplicate plan for modification
- Archive old plans

### Phase 4: Plan Sharing

- Export plan as PDF
- Share plan link (read-only)
- Copy plan to another user

## Implementation Status

- ✅ "Create New Plan" button added to My Plan view
- ✅ Button navigates to /onboarding
- ⏳ Onboarding form pre-fill logic (to implement)
- ⏳ Backend plan generation endpoint (to implement)
- ⏳ Auto-deactivation of old plan (to implement)
- ⏳ Plan management dropdown (future)
