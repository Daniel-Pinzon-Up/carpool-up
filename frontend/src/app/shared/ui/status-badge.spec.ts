import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { StatusBadge } from './status-badge';

@Component({
  imports: [StatusBadge],
  template: `<cp-status-badge variant="danger">Rechazada</cp-status-badge>`,
})
class Host {}

describe('StatusBadge', () => {
  it('muestra icono y texto, no solo color', () => {
    const fixture = TestBed.createComponent(Host);
    fixture.detectChanges();
    const badge: HTMLElement = fixture.nativeElement.querySelector('cp-status-badge');
    expect(badge.textContent?.trim()).toBe('Rechazada');
    expect(badge.querySelector('svg[aria-hidden="true"]')).toBeTruthy();
    expect(badge.className).toContain('text-danger');
  });
});
