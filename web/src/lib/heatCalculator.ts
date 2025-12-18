/**
 * Adaptive Tweet Heat Calculator
 * 
 * Calculates a "heat" value (0-1) based on days since last tweet,
 * where the decay rate adapts to the visible time range.
 */

// Color gradient: Twitter Blue (active) → Red (danger/silent)
export const HEAT_GRADIENT = [
  { stop: 1.0, color: '#1DA1F2' },  // Twitter Blue (just tweeted)
  { stop: 0.8, color: '#00CED1' },  // Cyan (very active)
  { stop: 0.6, color: '#32CD32' },  // Green (healthy)
  { stop: 0.4, color: '#FFD700' },  // Yellow (getting quiet)
  { stop: 0.2, color: '#FF8C00' },  // Orange (warning)
  { stop: 0.0, color: '#DC143C' },  // Red (danger zone)
];

/**
 * Calculate heat value with adaptive τ and absolute thresholds
 * 
 * @param daysSinceTweet - Days since the last tweet
 * @param visibleRangeDays - The visible time range in days (for adaptive scaling)
 * @returns Heat value from 0 (cold/silent) to 1 (hot/active)
 */
export function calculateHeat(daysSinceTweet: number, visibleRangeDays: number): number {
  const k = 7; // Tuning constant: it takes ~1/7 of visible range to cool down
  const tau = Math.max(visibleRangeDays / k, 0.5); // Min tau of 0.5 days to prevent extreme sensitivity
  
  let heat = Math.exp(-daysSinceTweet / tau);
  
  // Absolute thresholds based on Alon's actual data (99th percentile = 8.8 days)
  // Ensures extreme silences are ALWAYS in danger zone regardless of zoom
  if (daysSinceTweet > 14) {
    heat = Math.min(heat, 0.15); // Force into red zone
  } else if (daysSinceTweet > 7) {
    heat = Math.min(heat, 0.25); // Force into orange zone
  }
  
  return Math.max(0, Math.min(1, heat));
}

/**
 * Parse hex color to RGB components
 */
function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return { r: 0, g: 0, b: 0 };
  return {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16),
  };
}

/**
 * Convert RGB to hex string
 */
function rgbToHex(r: number, g: number, b: number): string {
  return '#' + [r, g, b].map(x => {
    const hex = Math.round(x).toString(16);
    return hex.length === 1 ? '0' + hex : hex;
  }).join('');
}

/**
 * Interpolate between two colors
 */
function lerpColor(color1: string, color2: string, t: number): string {
  const c1 = hexToRgb(color1);
  const c2 = hexToRgb(color2);
  
  return rgbToHex(
    c1.r + (c2.r - c1.r) * t,
    c1.g + (c2.g - c1.g) * t,
    c1.b + (c2.b - c1.b) * t
  );
}

/**
 * Interpolate color based on heat value
 * 
 * @param heat - Heat value from 0 (cold) to 1 (hot)
 * @returns Hex color string
 */
export function interpolateColor(heat: number): string {
  // Clamp heat to [0, 1]
  const h = Math.max(0, Math.min(1, heat));
  
  // Find the two gradient stops to interpolate between
  let lowerStop = HEAT_GRADIENT[HEAT_GRADIENT.length - 1];
  let upperStop = HEAT_GRADIENT[0];
  
  for (let i = 0; i < HEAT_GRADIENT.length - 1; i++) {
    if (h <= HEAT_GRADIENT[i].stop && h >= HEAT_GRADIENT[i + 1].stop) {
      upperStop = HEAT_GRADIENT[i];
      lowerStop = HEAT_GRADIENT[i + 1];
      break;
    }
  }
  
  // Interpolate between the two stops
  const range = upperStop.stop - lowerStop.stop;
  if (range === 0) return upperStop.color;
  
  const t = (h - lowerStop.stop) / range;
  return lerpColor(lowerStop.color, upperStop.color, t);
}

/**
 * Find days since last tweet for a given timestamp
 * Uses binary search for efficiency
 * 
 * @param timestamp - Unix timestamp to check
 * @param sortedTweetTimestamps - Sorted array of tweet timestamps
 * @returns Days since the last tweet before this timestamp (or Infinity if no prior tweets)
 */
export function findDaysSinceLastTweet(
  timestamp: number,
  sortedTweetTimestamps: number[]
): number {
  if (sortedTweetTimestamps.length === 0) return Infinity;
  
  // Binary search for the largest tweet timestamp <= timestamp
  let left = 0;
  let right = sortedTweetTimestamps.length - 1;
  let lastTweetBefore = -1;
  
  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    if (sortedTweetTimestamps[mid] <= timestamp) {
      lastTweetBefore = mid;
      left = mid + 1;
    } else {
      right = mid - 1;
    }
  }
  
  // No tweet before this timestamp
  if (lastTweetBefore === -1) {
    // Use first tweet as reference (show as fully cold before any tweets)
    return Infinity;
  }
  
  const lastTweetTs = sortedTweetTimestamps[lastTweetBefore];
  const daysSince = (timestamp - lastTweetTs) / 86400; // Convert seconds to days
  
  return Math.max(0, daysSince);
}

/**
 * Get human-readable label for the current heat state
 */
export function getHeatLabel(daysSinceTweet: number): { label: string; emoji: string } {
  if (daysSinceTweet < 1) return { label: 'Active', emoji: '🐦' };
  if (daysSinceTweet < 3) return { label: 'Recent', emoji: '🟢' };
  if (daysSinceTweet < 7) return { label: 'Quiet', emoji: '🟡' };
  if (daysSinceTweet < 14) return { label: 'Warning', emoji: '🟠' };
  return { label: 'Danger Zone', emoji: '🔴' };
}

