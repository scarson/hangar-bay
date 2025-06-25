import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ContractBrowsePage } from './contract-browse-page';

describe('ContractBrowsePage', () => {
  let component: ContractBrowsePage;
  let fixture: ComponentFixture<ContractBrowsePage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ContractBrowsePage]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ContractBrowsePage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
