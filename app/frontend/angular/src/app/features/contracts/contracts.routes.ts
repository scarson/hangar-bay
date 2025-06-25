import { Routes } from '@angular/router';

import { ContractBrowsePage } from './contract-browse-page/contract-browse-page';

/**
 * Defines the routes for the lazy-loaded contracts feature.
 */
import { contractFilterResolver } from './contract-filter.resolver';

/**
 * Defines the routes for the lazy-loaded contracts feature.
 */
export const CONTRACTS_ROUTES: Routes = [
  {
    path: '',
    component: ContractBrowsePage,
    title: 'Browse Contracts',
    resolve: {
      filters: contractFilterResolver,
    },
  },
];
