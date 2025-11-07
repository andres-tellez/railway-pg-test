# How Your Target Pace is Determined

## Initial Pace Seed (Week 1)

Your target pace is calculated using a **two-path approach** based on your available running history:

### Path 1: Based on Your Strava History (Preferred)

If you have **6 or more runs in the last 6 weeks**:

1. **Calculate your median easy pace** from all your recent runs (2+ miles)
2. **Build pace zones** around that:
   - **EASY**: Median pace + 15 to 45 seconds per mile (keep it conversational)
   - **STEADY**: Median pace - 15 to + 15 seconds per mile (slightly faster)
   - **MARATHON**: Median pace - 60 seconds per mile (race goal)
   - **THRESHOLD**: Marathon pace - 20 to 30 seconds per mile (hard efforts)

**Example**: If your median easy pace is 11:00/mile (660 sec/mi):

- Easy: 11:15–11:45/mile
- Steady: 10:45–11:15/mile
- Marathon: ~10:00/mile
- Threshold: ~9:30–9:40/mile

### Path 2: Conservative Calibration (Fallback)

If you have **insufficient recent data**:

1. Assume a conservative marathon pace of **10:00/mile**
2. Build zones from that assumption:
   - **EASY**: 11:00–11:30/mile
   - **STEADY**: 10:30–11:00/mile
   - **MARATHON**: 10:00/mile
   - **THRESHOLD**: 9:30–9:40/mile

**This ensures "Just Finish" plans start safely and build gradually.**

---

## How Paces Change Week-to-Week

Currently, **all weeks in your pre-generated plan use the same pace seed**. This is by design for "Just Finish" plans to keep things simple and predictable.

However, we've built **Weekly Adjustments** infrastructure that will adapt paces based on your feedback:

### Adjustments Based on Weekly Feedback

When you log your runs (completion + RPE), the system can adjust paces:

#### Too Hard (RPE ≥ 5/10)

- **Slows all paces by 10 seconds per mile**
- **Disables quality workouts** next week (no strides, no marathon pace finishes)
- **Reason**: Body is stressed; recovery takes priority

**Example**: Week 1 paces 11:15–11:45/mile → Week 2 paces 11:25–11:55/mile

#### Low Completion (< 60% of planned miles)

- **Slows all paces by 15 seconds per mile**
- **Disables quality workouts** next week
- **Reason**: Volume is the challenge; paces need to be more manageable

**Example**: Week 1 paces 11:15–11:45/mile → Week 2 paces 11:30–12:00/mile

#### Too Easy (RPE ≤ 2/10 + 80%+ completion)

- **Speeds all paces by 5 seconds per mile**
- **Keeps quality workouts enabled**
- **Reason**: Runner is fitter than expected; can handle slightly faster paces

**Example**: Week 1 paces 11:15–11:45/mile → Week 2 paces 11:10–11:40/mile

#### Normal Week

- **No adjustment** → same paces continue
- **Reason**: System maintains consistency when you're on track

---

## Week-to-Week Behavior in Your Current Plan

**All workouts in your entire plan are pre-generated with the same pace seed.** This means:

- ✅ **Consistency**: Same target paces throughout the plan
- ✅ **Predictability**: You know what to expect each week
- ✅ **Safety**: Conservative paces stay conservative

### Future: Rolling Mode (Not Yet Enabled)

When we enable "rolling mode" plan generation:

- You'll log your week's runs (distance completed + RPE)
- At the end of each week, the system will **rebuild next week's workouts** with adjusted paces
- Paces will adapt based on your performance and recovery

**Example timeline**:

1. **Week 1**: Easy 11:15–11:45/mile
2. **Week 2 (after logging)**: If you found Week 1 easy, Week 2 might become 11:10–11:40/mile
3. **Week 3 (after logging)**: If Week 2 was too hard, Week 3 might become 11:25–11:55/mile

---

## Key Takeaway

**Your target paces are personalized to you** based on:

1. Your recent Strava history (if available)
2. Conservative calibration (if no history)
3. Week-to-week feedback (when rolling mode is enabled)

The system prioritizes **safety and consistency** for "Just Finish" plans, ensuring you can complete workouts and build fitness gradually rather than burning out.
