/**
 * Client-side scoring calculator for Stage 2 complexity assessment
 * Mirrors backend/core/scoring/ logic for live preview
 * Must produce identical results to backend calculations
 */

import type { Band, ComplexityClass, AttributeBands } from "./types"

/**
 * Weight matrix - matches backend/data/reference/weight_matrix.json
 * DO NOT MODIFY without updating backend reference file
 */
export const WEIGHTS: Record<keyof AttributeBands, Record<Band, number>> = {
  activities: { XS: 2, S: 2, M: 4, L: 6, XL: 8 },
  business_rules: { XS: 2, S: 2, M: 4, L: 6, XL: 8 },
  layouts: { XS: 1, S: 1, M: 2, L: 3, XL: 4 },
  interfaces: { XS: 1, S: 1, M: 2, L: 3, XL: 4 },
  technology: { XS: 1, S: 1, M: 2, L: 3, XL: 4 },
}

/**
 * Effort table - matches backend/data/reference/effort_table.json
 * Values are in weeks
 */
export const EFFORT_TABLE: Record<
  ComplexityClass,
  { min_weeks: number; max_weeks: number; sprints: number }
> = {
  XS: { min_weeks: 1, max_weeks: 1, sprints: 1 },
  S: { min_weeks: 2, max_weeks: 4, sprints: 2 },
  M: { min_weeks: 5, max_weeks: 5, sprints: 5 },
  L: { min_weeks: 6, max_weeks: 6, sprints: 6 },
  XL: { min_weeks: 8, max_weeks: 8, sprints: 8 },
}

/**
 * Calculate total score from attribute bands
 */
export function calculateScore(bands: Partial<AttributeBands>): number {
  let total = 0

  for (const [attr, band] of Object.entries(bands)) {
    if (attr in WEIGHTS && band) {
      const weight = WEIGHTS[attr as keyof AttributeBands]?.[band as Band]
      if (weight !== undefined) {
        total += weight
      }
    }
  }

  return total
}

/**
 * Calculate individual attribute weights
 */
export function calculateAttributeWeights(
  bands: Partial<AttributeBands>
): Record<string, number> {
  const weights: Record<string, number> = {}

  for (const [attr, band] of Object.entries(bands)) {
    if (attr in WEIGHTS && band) {
      const weight = WEIGHTS[attr as keyof AttributeBands]?.[band as Band]
      if (weight !== undefined) {
        weights[attr] = weight
      }
    }
  }

  return weights
}

/**
 * Check if bands qualify for XS special case
 * XS special case: max 2 attributes selected, all in XS column
 */
export function isXsSpecialCase(bands: Partial<AttributeBands>): boolean {
  const entries = Object.entries(bands).filter(([_, band]) => band !== undefined)

  // Must have at most 2 attributes
  if (entries.length > 2) return false

  // All selected attributes must be XS
  return entries.every(([_, band]) => band === "XS")
}

/**
 * Classify complexity based on total score
 * Mirrors backend/core/scoring/classifier.py
 */
export function classifyScore(
  score: number,
  bands?: Partial<AttributeBands>
): ComplexityClass {
  // Check XS special case first
  if (bands && isXsSpecialCase(bands)) {
    return "XS"
  }

  // Numeric classification
  if (score >= 23 && score <= 28) return "XL"
  if (score >= 16 && score <= 22) return "L"
  if (score >= 9 && score <= 15) return "M"
  if (score >= 7 && score <= 8) return "S"
  if (score <= 6) return "XS"

  // Fallback for out-of-range scores
  return "M"
}

/**
 * Get effort estimate for a complexity class
 */
export function getEffort(complexityClass: ComplexityClass): {
  min_weeks: number
  max_weeks: number
  sprints: number
} {
  return EFFORT_TABLE[complexityClass]
}

/**
 * Complete scoring pipeline - calculate score, classify, and get effort
 */
export function scoreComplexity(bands: Partial<AttributeBands>): {
  total_score: number
  complexity_class: ComplexityClass
  effort_min_weeks: number
  effort_max_weeks: number
  sprints: number
  attribute_weights: Record<string, number>
} {
  const total_score = calculateScore(bands)
  const complexity_class = classifyScore(total_score, bands)
  const effort = getEffort(complexity_class)
  const attribute_weights = calculateAttributeWeights(bands)

  return {
    total_score,
    complexity_class,
    effort_min_weeks: effort.min_weeks,
    effort_max_weeks: effort.max_weeks,
    sprints: effort.sprints,
    attribute_weights,
  }
}

/**
 * Validate if all required bands are selected
 */
export function hasAllBands(bands: Partial<AttributeBands>): boolean {
  const required: Array<keyof AttributeBands> = [
    "activities",
    "business_rules",
    "layouts",
    "interfaces",
    "technology",
  ]
  return required.every((attr) => bands[attr] !== undefined)
}

/**
 * Format band display label
 */
export function formatBandLabel(band: Band): string {
  return band
}

/**
 * Format complexity class display label with color
 */
export function getComplexityColor(cls: ComplexityClass): string {
  switch (cls) {
    case "XS":
      return "text-green-600 dark:text-green-400"
    case "S":
      return "text-blue-600 dark:text-blue-400"
    case "M":
      return "text-yellow-600 dark:text-yellow-400"
    case "L":
      return "text-orange-600 dark:text-orange-400"
    case "XL":
      return "text-red-600 dark:text-red-400"
  }
}
