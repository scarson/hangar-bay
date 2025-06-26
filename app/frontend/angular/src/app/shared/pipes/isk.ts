import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'isk',
  standalone: true,
})
export class Isk implements PipeTransform {
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
