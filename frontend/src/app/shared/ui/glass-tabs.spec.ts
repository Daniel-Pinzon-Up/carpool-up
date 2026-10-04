import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { GlassTabs, TabItem } from './glass-tabs';

@Component({
  imports: [GlassTabs],
  template: `<cp-glass-tabs label="Viajes" [tabs]="tabs" [(selected)]="selected" />`,
})
class Host {
  tabs: TabItem[] = [
    { id: 'a', label: 'Proximos' },
    { id: 'b', label: 'En curso' },
    { id: 'c', label: 'Historial' },
  ];
  selected = signal('a');
}

describe('GlassTabs', () => {
  function setup() {
    const fixture = TestBed.createComponent(Host);
    fixture.detectChanges();
    const tabs = () =>
      Array.from(fixture.nativeElement.querySelectorAll('[role="tab"]')) as HTMLButtonElement[];
    return { fixture, tabs };
  }

  it('marca la pestana activa con aria-selected', () => {
    const { tabs } = setup();
    expect(tabs().map((tab) => tab.getAttribute('aria-selected'))).toEqual([
      'true',
      'false',
      'false',
    ]);
  });

  it('cicla con las flechas y mueve el foco', () => {
    const { fixture, tabs } = setup();
    tabs()[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft' }));
    fixture.detectChanges();
    expect(fixture.componentInstance.selected()).toBe('c');
    expect(document.activeElement).toBe(tabs()[2]);
  });

  it('Inicio y Fin van a los extremos', () => {
    const { fixture, tabs } = setup();
    tabs()[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'End' }));
    fixture.detectChanges();
    expect(fixture.componentInstance.selected()).toBe('c');
    tabs()[2].dispatchEvent(new KeyboardEvent('keydown', { key: 'Home' }));
    fixture.detectChanges();
    expect(fixture.componentInstance.selected()).toBe('a');
  });
});
