import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';

import { ContractSearch } from '../contract-search';

@Component({
  selector: 'hgb-contract-browse-page',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './contract-browse-page.html',
  styleUrl: './contract-browse-page.scss',
})
export class ContractBrowsePage {
  private contractSearch = inject(ContractSearch);

  // Expose the state signals to the template.
  readonly loading = this.contractSearch.loading;
  readonly error = this.contractSearch.error;
  readonly data = this.contractSearch.data;
  readonly filters = this.contractSearch.filters;

  onSearch(searchTerm: string): void {
    // Reset to page 1 when starting a new search to avoid confusion.
    this.contractSearch.updateFilters({ search: searchTerm, page: 1 });
  }

  changePage(newPage: number): void {
    this.contractSearch.updateFilters({ page: newPage });
  }

  calculateTotalPages(total: number, size: number): number {
    if (size === 0) {
      return 1; // Avoid division by zero
    }
    return Math.ceil(total / size);
  }
}
