/**
 * Founder-Normalized Tweet Heat Calculator
 * 
 * Calculates a "heat" value (0-1) based on how unusual the current gap is
 * relative to the founder's typical tweeting pattern.
 * 
 * This is ZOOM-INDEPENDENT: the same gap always produces the same color,
 * preserving fidelity at all timescales.
 */

// Color gradient: Green (healthy/active) → Red (danger/silent)
// This follows intuitive traffic light convention
export const HEAT_GRADIENT = [
  { stop: 1.0, color: '#00C853' },  // Bright Green (just tweeted)
  { stop: 0.7, color: '#76FF03' },  // Light Green (very active)
  { stop: 0.5, color: '#FFEB3B' },  // Yellow (getting quiet)
  { stop: 0.3, color: '#FF9800' },  // Orange (unusual silence)
  { stop: 0.15, color: '#FF5722' }, // Deep Orange (warning)
  { stop: 0.0, color: '#D50000' },  // Red (danger zone)
];

// Founder-specific constants (pre-computed from historical data)
// These should eventually come from a config/database per founder
export const FOUNDER_STATS = {
  alon: {
    medianGapDays: 0.8,    // He typically tweets every ~19 hours
    p90GapDays: 3.2,       // 90th percentile gap
    p99GapDays: 8.8,       // 99th percentile gap
    maxHistoricalGapDays: 12.1,  // Before current silence
  }
};

/**
 * Calculate heat value normalized by founder's typical tweet frequency
 * 
 * The formula: heat = exp(-gap / medianGap * k)
 * 
 * This means:
 * - At 0 days: heat = 1.0 (green)
 * - At median gap (0.8 days): heat ≈ 0.61 (green-yellow)
 * - At 3x median (2.4 days): heat ≈ 0.22 (orange)
 * - At 10x median (8 days): heat ≈ 0.007 (deep red)
 * 
 * @param daysSinceTweet - Days since the last tweet
 * @param _visibleRangeDays - IGNORED (kept for API compatibility, will be removed)
 * @returns Heat value from 0 (danger/silent) to 1 (healthy/active)
 */
export function calculateHeat(daysSinceTweet: number, _visibleRangeDays?: number): number {
  const { medianGapDays } = FOUNDER_STATS.alon;
  
  // Decay constant - tuned so that:
  // - At median gap: heat ≈ 0.61 (still healthy green-yellow)
  // - At 3x median: heat ≈ 0.22 (orange warning)
  // - At 5x median: heat ≈ 0.08 (deep orange/red)
  const k = 0.5;
  
  const normalizedGap = daysSinceTweet / medianGapDays;
  const heat = Math.exp(-normalizedGap * k);
  
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
 * Based on multiples of the founder's median gap
 */
export function getHeatLabel(daysSinceTweet: number): { label: string; emoji: string } {
  const { medianGapDays, p90GapDays, p99GapDays, maxHistoricalGapDays } = FOUNDER_STATS.alon;
  
  // Labels based on how unusual this gap is
  if (daysSinceTweet < medianGapDays) {
    return { label: 'Active', emoji: '🟢' };
  }
  if (daysSinceTweet < p90GapDays) {
    return { label: 'Normal', emoji: '🟢' };
  }
  if (daysSinceTweet < p99GapDays) {
    return { label: 'Quiet', emoji: '🟡' };
  }
  if (daysSinceTweet < maxHistoricalGapDays) {
    return { label: 'Warning', emoji: '🟠' };
  }
  // Beyond historical max = unprecedented
  return { label: 'Danger Zone', emoji: '🔴' };
}

