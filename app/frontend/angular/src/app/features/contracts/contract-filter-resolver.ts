import { inject } from '@angular/core';
import {
  ActivatedRouteSnapshot,
  ResolveFn,
  RouterStateSnapshot,
} from '@angular/router';
import { ContractSearch } from './contract-search';
import { ContractSearchFilters } from './contract.models';

export const contractFilterResolver: ResolveFn<boolean> = (
  route: ActivatedRouteSnapshot,
  state: RouterStateSnapshot
) => {
  const contractSearch = inject(ContractSearch);

  // Get and parse query params, providing defaults for invalid or missing values.
  const page = parseInt(route.queryParamMap.get('page') ?? '1', 10);
  const size = parseInt(route.queryParamMap.get('size') ?? '20', 10);
  const search = route.queryParamMap.get('search') ?? undefined;
  const type = route.queryParamMap.get('type') ?? undefined;

  const filters: ContractSearchFilters = {
    page: !isNaN(page) && page > 0 ? page : 1,
    size: !isNaN(size) && size > 0 ? size : 20,
    // Ensure empty string from query params becomes undefined
    search: search || undefined,
    type: type || undefined,
  };

  contractSearch.setInitialFilters(filters);

  return true;
};
