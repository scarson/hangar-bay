import { Routes } from '@angular/router';

import { ThemeTest } from './features/testing/pages/theme-test/theme-test';

export const routes: Routes = [
  { path: 'theme-test', component: ThemeTest },
  {
    path: '',
    redirectTo: 'contracts',
    pathMatch: 'full',
  },
  {
    path: 'home',
    loadComponent: () => import('./features/home/home').then(m => m.Home),
  },
  {
    path: 'contracts',
    loadChildren: () =>
      import('./features/contracts/contracts.routes').then(
        (m) => m.CONTRACTS_ROUTES
      ),
  },
  {
    path: '**',
    redirectTo: 'contracts', // Redirect any unknown paths to the main contracts feature
  },
];

