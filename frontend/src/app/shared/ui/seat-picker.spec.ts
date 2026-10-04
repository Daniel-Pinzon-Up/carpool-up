import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { SeatPicker } from './seat-picker';

@Component({
  imports: [SeatPicker, ReactiveFormsModule],
  template: `<cp-seat-picker label="Puestos" [formControl]="control" [min]="1" [max]="2" />`,
})
class Host {
  control = new FormControl(1, { nonNullable: true });
}

describe('SeatPicker', () => {
  it('respeta el minimo y el maximo', () => {
    TestBed.configureTestingModule({ imports: [Host, getTranslocoTestingModule()] });
    const fixture = TestBed.createComponent(Host);
    fixture.detectChanges();
    const [decrease, increase] = Array.from(
      fixture.nativeElement.querySelectorAll('button'),
    ) as HTMLButtonElement[];

    expect(decrease.disabled).toBe(true);
    increase.click();
    fixture.detectChanges();
    expect(fixture.componentInstance.control.value).toBe(2);
    expect(increase.disabled).toBe(true);
    expect(increase.getAttribute('aria-label')).toBe('Agregar un puesto');
  });
});
