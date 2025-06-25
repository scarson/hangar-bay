import { TestBed } from '@angular/core/testing';

import { ContractSearch } from './contract-search';

describe('ContractSearch', () => {
  let service: ContractSearch;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(ContractSearch);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
