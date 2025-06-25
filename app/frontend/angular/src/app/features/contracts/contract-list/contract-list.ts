import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ContractApi } from '../contract.api';

@Component({
  selector: 'hgb-contract-list',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './contract-list.html',
  styleUrl: './contract-list.scss',
})
export class ContractList implements OnInit {
  private contractApi = inject(ContractApi);

  // Expose the state signal directly to the template
  public readonly apiState = this.contractApi.state;

  // Pagination state
  currentPage = 1;
  pageSize = 10;

  ngOnInit(): void {
    this.fetchContracts();
  }

  fetchContracts(): void {
    this.contractApi.getContracts({ page: this.currentPage, size: this.pageSize });
  }

  onPageChange(newPage: number): void {
    if (newPage > 0 && newPage <= this.apiState().totalPages) {
      this.currentPage = newPage;
      this.fetchContracts();
    }
  }

  onPageSizeChange(newSize: number): void {
    this.pageSize = newSize;
    this.currentPage = 1; // Reset to first page
    this.fetchContracts();
  }
}
