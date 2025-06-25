import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { NgZone } from '@angular/core';
import { appConfig } from './app.config';

describe('appConfig', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [...appConfig.providers],
    });
  });

  it('should provide Router', () => {
    expect(() => TestBed.inject(Router)).not.toThrow();
  });

  it('should provide HttpClient', () => {
    expect(() => TestBed.inject(HttpClient)).not.toThrow();
  });

  it('should provide NoopNgZone for zoneless operation', () => {
    const ngZone = TestBed.inject(NgZone);
    // Verify that the provided NgZone is the NoopNgZone, confirming zoneless setup.
    // We check the constructor name to avoid relying on private Angular APIs.
    expect(ngZone.constructor.name).toBe('NoopNgZone');
  });
});
