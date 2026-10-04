import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { StarRating } from './star-rating';

@Component({
  imports: [StarRating, ReactiveFormsModule],
  template: `<cp-star-rating label="Puntualidad" [formControl]="control" />`,
})
class Host {
  control = new FormControl<number | null>(null);
}

function setup() {
  TestBed.configureTestingModule({ imports: [Host, getTranslocoTestingModule()] });
  const fixture = TestBed.createComponent(Host);
  fixture.detectChanges();
  const radios = () =>
    Array.from(fixture.nativeElement.querySelectorAll('[role="radio"]')) as HTMLButtonElement[];
  return { fixture, radios };
}

describe('StarRating', () => {
  it('expone un grupo de radio con cinco opciones etiquetadas', () => {
    const { fixture, radios } = setup();
    expect(fixture.nativeElement.querySelector('[role="radiogroup"]')).toBeTruthy();
    expect(radios()).toHaveLength(5);
    expect(radios()[2].getAttribute('aria-label')).toBe('3 de 5 estrellas');
  });

  it('actualiza el formulario al hacer clic', () => {
    const { fixture, radios } = setup();
    radios()[3].click();
    fixture.detectChanges();
    expect(fixture.componentInstance.control.value).toBe(4);
    expect(radios()[3].getAttribute('aria-checked')).toBe('true');
  });

  it('se maneja con las flechas del teclado', () => {
    const { fixture, radios } = setup();
    radios()[0].click();
    radios()[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight' }));
    fixture.detectChanges();
    expect(fixture.componentInstance.control.value).toBe(2);
    radios()[1].dispatchEvent(new KeyboardEvent('keydown', { key: 'End' }));
    fixture.detectChanges();
    expect(fixture.componentInstance.control.value).toBe(5);
  });

  it('solo una estrella es tabulable', () => {
    const { radios } = setup();
    expect(radios().filter((radio) => radio.tabIndex === 0)).toHaveLength(1);
  });
});
