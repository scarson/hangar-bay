## AI Analysis Guidance for Cascade

This file is over 200 lines long. Unless you are only looking for a specific section, you should read the entire file, which may require multiple tool calls.

# Angular HTTP & Data Loading (Hangar Bay)

**Last Updated:** 2025-06-09

## 1. Introduction

Modern web applications frequently interact with backend APIs to fetch and send data. Angular's `HttpClient` module provides a robust and flexible way to make HTTP requests. This document outlines how Hangar Bay will utilize `HttpClient`, including best practices for typed requests/responses, interceptors, error handling, and integrating data loading with our Signal-based state management.

Referenced from: Angular Docs, `llms-full.txt` (positions 35-38), `../angular-frontend-architecture.md` (Section 2.5).

## 2. `HttpClient` Setup

`HttpClient` is available through the `HttpClientModule`. For standalone applications, you provide it using `provideHttpClient()` in your `app.config.ts`.

```typescript
// app.config.ts
import { ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient, withInterceptors } from '@angular/common/http'; // Import provideHttpClient and withInterceptors
import { APP_ROUTES } from './app.routes';
import { authInterceptorFn, errorLoggingInterceptorFn } from './core/interceptors'; // Example interceptors

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(APP_ROUTES),
    provideHttpClient(
      // Register functional interceptors here
      withInterceptors([
        authInterceptorFn,       // For adding auth tokens
        errorLoggingInterceptorFn // For logging HTTP errors
      ])
    )
    // ... other providers
  ]
};
```
- **`withInterceptors([...])`:** Allows registering functional interceptors. Class-based interceptors are still supported but functional interceptors are often simpler for standalone apps.

## 3. Making HTTP Requests

Inject `HttpClient` into your services to make requests.

### 3.1. Basic Request Types

`HttpClient` methods return `Observable<T>`, where `T` is the expected response body type.

-   **GET:** Retrieve data.
    ```typescript
    import { Injectable, inject } from '@angular/core';
    import { HttpClient, HttpParams } from '@angular/common/http';
    import { Observable } from 'rxjs';
    import { User } from './user.model'; // Define your data models

    @Injectable({ providedIn: 'root' })
    export class DataService {
      private http = inject(HttpClient);
      private apiUrl = '/api'; // Base API URL

      getUsers(isActive?: boolean): Observable<User[]> {
        let params = new HttpParams();
        if (typeof isActive === 'boolean') {
          params = params.set('active', isActive.toString());
        }
        return this.http.get<User[]>(`${this.apiUrl}/users`, { params });
      }

      getUserById(id: string): Observable<User> {
        return this.http.get<User>(`${this.apiUrl}/users/${id}`);
      }
    }
    ```

-   **POST:** Send data to create a new resource.
    ```typescript
    // In DataService
    createUser(user: Omit<User, 'id'>): Observable<User> {
      return this.http.post<User>(`${this.apiUrl}/users`, user);
    }
    ```

-   **PUT:** Send data to update an existing resource.
    ```typescript
    // In DataService
    updateUser(userId: string, updates: Partial<User>): Observable<User> {
      return this.http.put<User>(`${this.apiUrl}/users/${userId}`, updates);
    }
    ```

-   **DELETE:** Remove a resource.
    ```typescript
    // In DataService
    deleteUser(userId: string): Observable<void> { // Often returns no body
      return this.http.delete<void>(`${this.apiUrl}/users/${userId}`);
    }
    ```

### 3.2. Strongly Typing Requests and Responses
- **Always type your requests and responses.** This improves code reliability and developer experience.
- Define interfaces or classes for your data models (e.g., `User`, `Product`).
  ```typescript
  // product.model.ts
  export interface Product {
    id: string;
    name: string;
    price: number;
    description?: string;
  }
  ```
  ```typescript
  // In a service
  getProduct(id: string): Observable<Product> {
    return this.http.get<Product>(`${this.apiUrl}/products/${id}`);
  }
  ```

### 3.3. Request Options

#### 3.3.1. `HttpHeaders`
- For setting custom headers (e.g., `Content-Type`, `Authorization`).
  ```typescript
  import { HttpHeaders } from '@angular/common/http';

  // ...
  const headers = new HttpHeaders()
    .set('Content-Type', 'application/json')
    .set('X-Custom-Header', 'HangarBayApp');

  createItem(item: any): Observable<any> {
    return this.http.post(`${this.apiUrl}/items`, item, { headers });
  }
  ```
- Note: `HttpHeaders` are immutable. Each `set` operation returns a new instance.
- Interceptors are generally preferred for adding headers like `Authorization` consistently.

#### 3.3.2. `HttpParams`
- For adding URL query parameters in a type-safe way.
  ```typescript
  import { HttpParams } from '@angular/common/http';

  // ...
  searchItems(term: string, category?: string): Observable<Item[]> {
    let params = new HttpParams().set('q', term);
    if (category) {
      params = params.set('category', category);
    }
    return this.http.get<Item[]>(`${this.apiUrl}/search`, { params });
  }
  ```
- `HttpParams` are also immutable.

#### 3.3.3. `observe` and `responseType`
- **`observe`:** Can be set to `'response'` to get the full `HttpResponse` object (including headers, status code) instead of just the body. Can also be `'events'` for progress events.
  ```typescript
  // Get full response
  getItemWithFullResponse(id: string): Observable<HttpResponse<Item>> {
    return this.http.get<Item>(`${this.apiUrl}/items/${id}`, { observe: 'response' });
  }
  ```
- **`responseType`:** Specifies the expected response format (e.g., `'json'` (default), `'text'`, `'blob'`, `'arraybuffer'`).
  ```typescript
  // Get a file as a blob
  downloadFile(url: string): Observable<Blob> {
    return this.http.get(url, { responseType: 'blob' });
  }
  ```

## 4. HTTP Interceptors

Interceptors provide a way to globally transform HTTP requests and responses. They are ideal for cross-cutting concerns.

### 4.1. Functional Interceptors (`HttpInterceptorFn`)
- **Preferred for Standalone Apps:** Simpler to define and register.
- An `HttpInterceptorFn` takes `HttpRequest<any>` and `HttpHandlerFn` (which passes the request to the next interceptor or backend) and returns `Observable<HttpEvent<any>>`.

#### Example: Auth Token Interceptor
```typescript
// core/interceptors/auth.interceptor.ts
import { HttpInterceptorFn, HttpRequest, HttpHandlerFn, HttpEvent } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthService } from '../services/auth.service'; // Example auth service
import { Observable } from 'rxjs';

export const authInterceptorFn: HttpInterceptorFn = (
  req: HttpRequest<any>,
  next: HttpHandlerFn
): Observable<HttpEvent<any>> => {
  const authService = inject(AuthService);
  const authToken = authService.getTokenSignal(); // Assuming getTokenSignal() returns the token or null

  if (authToken && !req.url.includes('/auth/login')) { // Don't add token to login requests
    const authReq = req.clone({
      setHeaders: {
        Authorization: `Bearer ${authToken}`
      }
    });
    return next(authReq);
  }
  return next(req);
};
```

#### Example: Error Logging Interceptor
```typescript
// core/interceptors/error-logging.interceptor.ts
import { HttpInterceptorFn, HttpRequest, HttpHandlerFn, HttpEvent, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';

export const errorLoggingInterceptorFn: HttpInterceptorFn = (
  req: HttpRequest<any>,
  next: HttpHandlerFn
): Observable<HttpEvent<any>> => {
  return next(req).pipe(
    catchError((error: HttpErrorResponse) => {
      console.error('HTTP Error Interceptor:', {
        url: req.url,
        status: error.status,
        message: error.message,
        errorBody: error.error // The actual error response body
      });
      // Optionally, transform the error or perform other side effects
      // Re-throw the error to be handled by the calling service/component
      return throwError(() => error);
    })
  );
};
```
- **Registration:** Functional interceptors are registered using `withInterceptors([...])` in `provideHttpClient` (see section 2).

## 5. Error Handling

Proper error handling is crucial for a good user experience.

### 5.1. Client-Side vs. Server-Side Errors
- `HttpErrorResponse` distinguishes between client-side errors (network issues, JavaScript errors before request) and server-side errors (HTTP status codes 4xx, 5xx).
  - `error.error` contains the error details. If it's an `ErrorEvent` (client-side), `error.message` is relevant. If it's a server response, `error.error` might be the parsed JSON error body from the server.

### 5.2. Using `catchError` Operator
- The `catchError` RxJS operator is used in services to handle errors from HTTP requests.
  ```typescript
  // In DataService
  import { catchError, tap } from 'rxjs/operators';
  import { throwError } from 'rxjs';

  getProduct(id: string): Observable<Product | null> { // Return null on error for example
    return this.http.get<Product>(`${this.apiUrl}/products/${id}`).pipe(
      tap(product => console.log('Fetched product:', product)),
      catchError(err => {
        console.error('Error fetching product:', err);
        // Optionally, transform the error for the component
        // Or return a safe default value, like null or an empty array
        // return of(null);
        // Or re-throw a user-friendly error message or the original error
        return throwError(() => new Error(`Failed to load product ${id}. Status: ${err.status}`));
      })
    );
  }
  ```

### 5.3. Displaying Errors to Users
- Components subscribing to service methods should handle errors and display appropriate messages to the user.
- Use signals in services or components to track loading and error states.
  ```typescript
  // In a component using the DataService
  // product = toSignal(this.dataService.getProduct(this.productId()), { initialValue: undefined });
  // error = toSignal(this.dataService.getProduct(this.productId()).pipe(catchError(e => of(e))), { initialValue: null });
  // This approach with toSignal for errors can be tricky; often better to manage error state explicitly.

  // Explicit error state management in component:
  // product = signal<Product | null>(null);
  // error = signal<string | null>(null);
  // isLoading = signal<boolean>(false);
  // loadProduct(id: string) {
  //   this.isLoading.set(true); this.error.set(null);
  //   this.dataService.getProduct(id).subscribe({
  //     next: p => { this.product.set(p); this.isLoading.set(false); },
  //     error: e => { this.error.set(e.message); this.isLoading.set(false); }
  //   });
  // }
  ```

## 6. Data Loading Patterns & State Management

- **Services Own Data Fetching:** Components should delegate data fetching logic to services.
- **Signals for State:** Services should manage fetched data, loading states, and error states using Signals. Components can then subscribe to these signals (often via `toSignal` or direct signal reads).
  ```typescript
  // Example in UserService (from 04-state-management-and-rxjs.md)
  // private readonly _currentUser = signal<User | null>(null);
  // readonly currentUser = this._currentUser.asReadonly();
  // fetchUser(id: string) { /* ... uses HttpClient, updates _currentUser and error/loading signals ... */ }
  ```
- **Caching:** For frequently accessed, slowly changing data, consider implementing caching strategies in services (e.g., simple in-memory cache with expiration, `shareReplay` with RxJS, or more advanced solutions).

## 7. Best Practices

- **Type Safety:** Always use strongly typed requests and responses.
- **Interceptors:** Use interceptors for global concerns like auth, logging, and consistent error handling/formatting.
- **Error Handling:** Implement robust error handling in services and provide clear feedback to users in components.
- **Unsubscribe:** `HttpClient` observables typically complete after emitting a single value (the response) or an error. For these, explicit unsubscription is often not needed if you're just taking the first value. However, if you transform them into longer-lived observables (e.g., with `shareReplay` without `refCount: true`), ensure proper unsubscription (e.g., using `takeUntilDestroyed` or `toSignal`'s auto-cleanup).
- **Centralized API Configuration:** Store base API URLs and common paths in environment files or a dedicated configuration service.
- **Loading Indicators:** Always provide visual feedback (loading spinners, disabled buttons) to the user during HTTP requests.
- **Optimistic Updates (Advanced):** For a snappier UI, consider optimistic updates for POST/PUT/DELETE operations, then revert if the server call fails. This adds complexity.
