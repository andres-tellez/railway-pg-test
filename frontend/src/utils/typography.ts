/**
 * Typography Scale and Constants
 *
 * Best Practices:
 * 1. Use a consistent scale (1.25x or 1.5x ratio)
 * 2. Limit to 4-5 font sizes for consistency
 * 3. Use semantic naming (heading, body, caption)
 * 4. Ensure sufficient contrast (WCAG AA minimum)
 * 5. Responsive sizing (mobile-first approach)
 */

export const TYPOGRAPHY = {
  // Headings
  h1: {
    mobile: "text-3xl",      // 30px / 1.875rem
    desktop: "text-4xl",     // 36px / 2.25rem
    weight: "font-bold",
    lineHeight: "leading-tight",
  },
  h2: {
    mobile: "text-2xl",      // 24px / 1.5rem
    desktop: "text-3xl",     // 30px / 1.875rem
    weight: "font-bold",
    lineHeight: "leading-tight",
  },
  h3: {
    mobile: "text-xl",       // 20px / 1.25rem
    desktop: "text-2xl",     // 24px / 1.5rem
    weight: "font-semibold",
    lineHeight: "leading-snug",
  },

  // Body Text
  bodyLarge: {
    mobile: "text-lg",       // 18px / 1.125rem
    desktop: "text-xl",       // 20px / 1.25rem
    weight: "font-normal",
    lineHeight: "leading-relaxed",
  },
  body: {
    mobile: "text-base",     // 16px / 1rem
    desktop: "text-base",    // 16px / 1rem
    weight: "font-normal",
    lineHeight: "leading-relaxed",
  },
  bodySmall: {
    mobile: "text-sm",       // 14px / 0.875rem
    desktop: "text-sm",      // 14px / 0.875rem
    weight: "font-normal",
    lineHeight: "leading-relaxed",
  },

  // Captions & Labels
  caption: {
    mobile: "text-xs",       // 12px / 0.75rem
    desktop: "text-xs",      // 12px / 0.75rem
    weight: "font-normal",
    lineHeight: "leading-relaxed",
  },

  // Buttons
  button: {
    mobile: "text-sm",       // 14px
    desktop: "text-base",    // 16px
    weight: "font-medium",
  },
} as const;

/**
 * Get responsive typography classes
 */
export function getTypographyClasses(
  variant: keyof typeof TYPOGRAPHY,
  includeWeight: boolean = true,
  includeLineHeight: boolean = true
): string {
  const typo = TYPOGRAPHY[variant];
  const classes = [
    typo.mobile,
    `md:${typo.desktop}`,
  ];

  if (includeWeight) {
    classes.push(typo.weight);
  }

  if (includeLineHeight && 'lineHeight' in typo) {
    classes.push(typo.lineHeight);
  }

  return classes.join(" ");
}
