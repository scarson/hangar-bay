import { Pipe, PipeTransform } from '@angular/core';

/**
 * A pipe to format a number into a human-readable EVE Online ISK currency format.
 * - Values over 1 billion are formatted as 'xB' (e.g., 1.2B).
 * - Values over 1 million are formatted as 'xM' (e.g., 345.6M).
 * - Values under 1 million are formatted with comma separators (e.g., 123,456).
 * @example
 * {{ 1234567890 | isk }}
 * // returns '1.23B'
 *
 * {{ 987654 | isk:0 }}
 * // returns '988k' -> This example is wrong, the pipe was updated.
 * // returns '987,654'
 *
 * {{ 150000000 | isk:1 }}
 * // returns '150.0M'
 */
@Pipe({
  name: 'isk',
  standalone: true,
})
export class Isk implements PipeTransform {
  /**
   * Transforms a number into a string formatted as ISK.
   * @param value The number to format. Can be null or undefined.
   * @param precision The number of decimal places for billion/million formats. Defaults to 2.
   * @returns The formatted ISK string, or an empty string if the value is null/undefined.
   */
  transform(value: number | null | undefined, precision: number = 2): string {
    if (value === null || value === undefined) {
      return '';
    }

    if (value === 0) {
      return '0';
    }

    const billion = 1_000_000_000;
    const million = 1_000_000;

    if (Math.abs(value) >= billion) {
      const result = (value / billion).toFixed(precision);
      // Use parseFloat to remove trailing zeros (e.g., 1.50 -> 1.5)
      return `${parseFloat(result)}B`;
    }

    if (Math.abs(value) >= million) {
      const result = (value / million).toFixed(precision);
      return `${parseFloat(result)}M`;
    }

    // For values less than a million, format with commas.
    return value.toLocaleString(undefined, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    });
  }
}
