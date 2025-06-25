import { inject } from '@angular/core';
import { ActivatedRouteSnapshot, ResolveFn, RouterStateSnapshot } from '@angular/router';

import { ContractSearchFilters } from './contract.models';
import { ContractSearch } from './contract-search';

/**
 * A resolver that parses contract search filters from the URL query parameters
 * and uses them to set the initial state of the ContractSearch service.
 */
export const contractFilterResolver: ResolveFn<void> = (
  route: ActivatedRouteSnapshot,
  state: RouterStateSnapshot
) => {
  const contractSearch = inject(ContractSearch);
  const queryParams = route.queryParams;

  const page = parseInt(queryParams['page'], 10) || 1;
  const size = parseInt(queryParams['size'], 10) || 20;
  const search = queryParams['search'] || undefined;

  const initialFilters: ContractSearchFilters = {
    page: isNaN(page) ? 1 : page,
    size: isNaN(size) ? 20 : size,
    search: search,
  };

  // Use a dedicated method to set the initial state without causing a race condition
  // with the component's own potential filter updates on initialization.
  contractSearch.setInitialFilters(initialFilters);
};
