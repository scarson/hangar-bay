import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { MatSortModule } from '@angular/material/sort';
import { MatPaginatorModule } from '@angular/material/paginator';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { Isk } from '../../../shared/pipes/isk';
import { TimeLeft } from '../../../shared/pipes/time-left';


import { Sort } from '@angular/material/sort';
import { PageEvent } from '@angular/material/paginator';
import { MatSelectChange } from '@angular/material/select';
import { Contract } from '../contract.models';

import { ContractSearch } from '../contract-search';

@Component({
  selector: 'hgb-contract-browse-page',
  standalone: true,
  imports: [
    CommonModule,
    Isk,
    TimeLeft,
    MatTableModule,
    MatSortModule,
    MatPaginatorModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
  ],
  templateUrl: './contract-browse-page.html',
  styleUrl: './contract-browse-page.scss',
})
export class ContractBrowsePage {
  private contractSearch = inject(ContractSearch);

  // Expose state signals to the template
  readonly loading = this.contractSearch.loading;
  readonly error = this.contractSearch.error;
  readonly data = this.contractSearch.data;
  readonly filters = this.contractSearch.filters;

  // Material Table properties
  readonly displayedColumns: string[] = ['type', 'issuer_name', 'start_location_name', 'price', 'date_expired'];

  onSearch(event: Event): void {
    const searchTerm = (event.target as HTMLInputElement).value;
    this.contractSearch.updateFilters({ search: searchTerm, page: 1 });
  }

  onTypeChange(event: MatSelectChange): void {
    const value = event.value as 'item_exchange' | 'auction' | '';
    // An empty string for the value means 'All Types', so we pass undefined to clear the filter.
    this.contractSearch.updateFilters({ type: value || undefined, page: 1 });
  }

  // This will be triggered by the MatPaginator
  handlePageEvent(event: PageEvent): void {
    this.contractSearch.updateFilters({ page: event.pageIndex + 1, size: event.pageSize });
  }

  // This will be triggered by the MatSort
  handleSortChange(sortState: Sort): void {
    // The API expects `sort_by` and `sort_order` to be undefined if sorting is cleared.
    const sortBy = sortState.direction ? (sortState.active as 'price' | 'date_expired') : undefined;
    const sortOrder = sortState.direction ? sortState.direction : undefined;

    this.contractSearch.updateFilters({
      sort_by: sortBy,
      sort_order: sortOrder,
      page: 1, // Reset to first page on sort
    });
  }
}
