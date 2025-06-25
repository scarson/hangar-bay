import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'home',
    pathMatch: 'full',
  },
  {
    path: 'home',
    loadComponent: () => import('./features/home/home').then(m => m.Home),
  },
  {
    path: 'contracts',
    loadChildren: () => import('./features/contracts/contracts.routes').then(r => r.CONTRACTS_ROUTES)
  },
  {
    path: '**',
    redirectTo: 'home',
  },
];
