import { TimeLeft } from './time-left';

describe('TimeLeft', () => {
  const pipe = new TimeLeft();

  it('create an instance', () => {
    expect(pipe).toBeTruthy();
  });

  it('should return an empty string for null or undefined input', () => {
    expect(pipe.transform(null)).toBe('');
    expect(pipe.transform(undefined)).toBe('');
  });

  describe('with mocked date', () => {
    const baseTime = new Date('2025-01-01T12:00:00Z');

    beforeEach(() => {
      jasmine.clock().install();
      jasmine.clock().mockDate(baseTime);
    });

    afterEach(() => {
      jasmine.clock().uninstall();
    });

    it('should format durations over a day correctly (e.g., "3d 4h")', () => {
      const futureDate = new Date('2025-01-04T16:30:00Z'); // 3d 4h 30m
      expect(pipe.transform(futureDate)).toBe('3d 4h');
    });

    it('should format durations under a day correctly (e.g., "15h 30m")', () => {
      const futureDate = new Date('2025-01-02T03:30:45Z'); // 15h 30m 45s
      expect(pipe.transform(futureDate)).toBe('15h 30m');
    });

    it('should format durations under an hour correctly (e.g., "5m")', () => {
      const futureDate = new Date('2025-01-01T12:05:15Z'); // 5m 15s
      expect(pipe.transform(futureDate)).toBe('5m');
    });

    it('should format durations under a minute correctly as "< 1m"', () => {
      const futureDate = new Date('2025-01-01T12:00:30Z'); // 30s
      expect(pipe.transform(futureDate)).toBe('< 1m');
    });

    it('should return "Expired" for a past date', () => {
      const pastDate = new Date('2025-01-01T11:59:59Z');
      expect(pipe.transform(pastDate)).toBe('Expired');
    });

    it('should return "Expired" for the exact same date', () => {
      const sameDate = new Date('2025-01-01T12:00:00Z');
      expect(pipe.transform(sameDate)).toBe('Expired');
    });
  });
});
