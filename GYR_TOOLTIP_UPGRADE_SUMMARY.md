# GYR Tooltip Technology Upgrade

## ✅ Changed from HTML `title` to Custom Positioned Tooltips

**Before:** Simple HTML `title` attribute tooltips

```html
<div title="Week 1: 2025-10-06 - 85% (yellow)" />
```

**After:** Custom positioned tooltips matching bar chart technology

```jsx
{
  hoveredBar && (
    <div className="fixed z-50 bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-600 rounded-lg p-3 shadow-2xl pointer-events-none backdrop-blur-sm">
      {/* Rich tooltip content */}
    </div>
  );
}
```

## Key Improvements

### 1. 🎨 **Visual Consistency**

- **Same styling** as bar chart tooltips
- Dark gradient background (`from-gray-800 to-gray-900`)
- Rounded corners with border
- Backdrop blur effect
- Shadow and pointer-events-none

### 2. 📍 **Better Positioning**

- **Fixed positioning** relative to viewport
- **Centered** above the hovered bar
- **Transform** to translate(-50%, -100%)
- **Min-width** of 180px for consistent sizing

### 3. 📊 **Rich Content Structure**

- **Header** with week date in styled box
- **Data rows** with label/value pairs
- **Status explanation** with color-coded backgrounds
- **Consistent spacing** and typography

### 4. 🎯 **Enhanced Functionality**

- **Mouse enter/leave** event handling
- **Scroll hiding** (tooltip disappears when scrolling)
- **Dynamic positioning** based on bar location
- **State management** with React hooks

## Tooltip Examples

### Total Runs Tooltip:

```
┌─────────────────────────────┐
│ Week of Oct 6, 2025        │
├─────────────────────────────┤
│ Actual:     27.3 mi (4 runs)│
│ Planned:    17.0 mi         │
│ Completion: 160.6%          │
├─────────────────────────────┤
│ ❌ Well above plan (>130%)  │
└─────────────────────────────┘
```

### Weekly Pace Tooltip:

```
┌─────────────────────────────┐
│ Week of Oct 6, 2025        │
├─────────────────────────────┤
│ Current:    8:45/mi         │
│ 3-wk Avg:   8:52/mi         │
├─────────────────────────────┤
│ ✓ Same or faster than avg  │
└─────────────────────────────┘
```

### HR Zones Tooltip:

```
┌─────────────────────────────┐
│ Week of Oct 6, 2025        │
├─────────────────────────────┤
│ Z1-Z2 Time: 78.5%          │
│ Training:   80/20 Rule      │
├─────────────────────────────┤
│ ✓ Good 80/20 balance       │
└─────────────────────────────┘
```

## Technical Implementation

### Files Modified:

1. ✅ `frontend/src/components/cards/GYRMetricCard.tsx`

   - Added `useState` for hover state
   - Added `useScrollHideTooltip` hook
   - Replaced `title` attribute with custom tooltip
   - Added mouse event handlers

2. ✅ `frontend/src/utils/gyrCardUtils.ts`
   - Removed old `generateBarTooltip` function
   - Kept styling utilities

### Code Structure:

```jsx
// State management
const [hoveredBar, setHoveredBar] = useState<{index, x, y} | null>(null);

// Scroll hiding
useScrollHideTooltip(hoveredBar !== null, () => setHoveredBar(null));

// Mouse events
onMouseEnter={(e) => {
  const rect = e.currentTarget.getBoundingClientRect();
  setHoveredBar({index, x: rect.left + rect.width/2, y: rect.top - 10});
}}
onMouseLeave={() => setHoveredBar(null)}

// Conditional rendering
{hoveredBar && <CustomTooltip />}
```

## Benefits

✅ **Consistent UX**: Same look/feel as bar charts
✅ **Better Readability**: Rich formatting and structure
✅ **Responsive**: Positioned relative to hovered element
✅ **Accessible**: Proper z-index and pointer events
✅ **Performance**: Only renders when needed
✅ **Maintainable**: Uses shared hooks and patterns

## Status

🎉 **Complete** - GYR cards now use the same tooltip technology as bar charts with identical styling, positioning, and behavior!
