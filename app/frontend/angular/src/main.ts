/// <reference types="@angular/localize" />

import { bootstrapApplication } from '@angular/platform-browser';
import { App } from './app/app';
import { appConfig } from './app/app.config';
import { environment } from './environments/environment';

if (environment.production) {
  if (environment.apiUrl.includes('your-production-api-domain.com')) {
    console.error('FATAL: Production apiUrl is not configured. Update environment.prod.ts.');
    document.body.innerHTML =
      '<h1 style="color: red; text-align: center; margin-top: 50px;">FATAL: Production API URL is not configured.</h1>';
    throw new Error('Production apiUrl is not configured.');
  }
}

bootstrapApplication(App, appConfig).catch((err) => console.error(err));
