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
  const queryParams = route.queryParamMap;

  // Get and parse query params, providing defaults for invalid or missing values.
  const page = parseInt(queryParams.get('page') ?? '1', 10);
  const size = parseInt(queryParams.get('size') ?? '20', 10);
  const search = queryParams.get('search') ?? undefined;
  const typeParam = queryParams.get('type');
  const type =
    typeParam === 'item_exchange' || typeParam === 'auction'
      ? typeParam
      : undefined;

  const sortByParam = queryParams.get('sort_by');
  const sort_by =
    sortByParam === 'price' ||
    sortByParam === 'date_issued' ||
    sortByParam === 'date_expired'
      ? sortByParam
      : undefined;

  const sortOrderParam = queryParams.get('sort_order');
  const sort_order =
    sortOrderParam === 'asc' || sortOrderParam === 'desc'
      ? sortOrderParam
      : undefined;

  const filters: ContractSearchFilters = {
    page: !isNaN(page) && page > 0 ? page : 1,
    size: !isNaN(size) && size > 0 ? size : 20,
    // Ensure empty string from query params becomes undefined
    search: search || undefined,
    type: type,
    sort_by: sort_by,
    sort_order: sort_order,
  };

  contractSearch.setInitialFilters(filters);

  return true;
};
