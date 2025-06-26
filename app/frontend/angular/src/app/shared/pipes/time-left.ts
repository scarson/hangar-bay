import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'timeLeft',
  standalone: true,
})
export class TimeLeft implements PipeTransform {
  transform(value: string | Date | null | undefined): string {
    if (!value) {
      return '';
    }

    const expiryDate = new Date(value);
    const now = new Date();
    let diffMs = expiryDate.getTime() - now.getTime();

    if (diffMs <= 0) {
      return 'Expired';
    }

    const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    diffMs -= days * (1000 * 60 * 60 * 24);

    const hours = Math.floor(diffMs / (1000 * 60 * 60));
    diffMs -= hours * (1000 * 60 * 60);

    const minutes = Math.floor(diffMs / (1000 * 60));

    if (days > 0) {
      return `${days}d ${hours}h`;
    }
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    if (minutes > 0) {
      return `${minutes}m`;
    }

    return '< 1m';
  }
}
