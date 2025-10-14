/**
 * Custom hook to hide tooltips when the user scrolls
 * This prevents tooltips from staying visible in the wrong position during scroll
 *
 * This hook wraps the centralized setupScrollHideTooltip utility from chartUtils
 */

import { useEffect } from 'react';
import { setupScrollHideTooltip } from '../utils/chartUtils';

/**
 * Hides tooltips when scrolling occurs
 * @param isTooltipVisible - Whether the tooltip is currently visible
 * @param hideTooltip - Function to call to hide the tooltip
 */
export const useScrollHideTooltip = (
  isTooltipVisible: boolean,
  hideTooltip: () => void
) => {
  useEffect(() => {
    // Use centralized tooltip behavior from chartUtils
    const cleanup = setupScrollHideTooltip(isTooltipVisible, hideTooltip);

    // Return cleanup function
    return cleanup;
  }, [isTooltipVisible, hideTooltip]);
};
