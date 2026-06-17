import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ItemsComponent } from './items.component';

describe('Items', () => {
  let component: ItemsComponent;
  let fixture: ComponentFixture<ItemsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ItemsComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(ItemsComponent);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
