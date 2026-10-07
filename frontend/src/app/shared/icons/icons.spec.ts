import { Component, signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { LucideDynamicIcon, LucideIcon, LucideSearch, LucideStar } from '@icons';

@Component({
  imports: [LucideSearch, LucideDynamicIcon],
  template: `
    <svg lucideSearch class="size-5 text-primary" aria-hidden="true"></svg>
    <svg [lucideIcon]="dynamic()" class="size-4" aria-hidden="true"></svg>
  `,
})
class Host {
  readonly dynamic = signal<LucideIcon>(LucideSearch);
}

describe('Iconos', () => {
  it('dibujan su SVG y conservan las clases de la plantilla', () => {
    const fixture = TestBed.createComponent(Host);
    fixture.detectChanges();
    const [fixed] = fixture.nativeElement.querySelectorAll('svg') as NodeListOf<SVGElement>;

    expect(fixed.getAttribute('viewBox')).toBe('0 0 24 24');
    expect(fixed.getAttribute('stroke')).toBe('currentColor');
    expect(fixed.classList).toContain('size-5');
    expect(fixed.classList).toContain('lucide-search');
    expect(fixed.querySelectorAll('path, circle')).toHaveLength(2);
    expect(fixed.firstElementChild?.namespaceURI).toBe('http://www.w3.org/2000/svg');
    expect(fixed.querySelector('[key]')).toBeNull();
  });

  it('el icono dinamico cambia de dibujo sin dejar restos del anterior', () => {
    const fixture = TestBed.createComponent(Host);
    fixture.detectChanges();
    const dynamic = (fixture.nativeElement.querySelectorAll('svg') as NodeListOf<SVGElement>)[1];
    expect(dynamic.classList).toContain('lucide-search');

    fixture.componentInstance.dynamic.set(LucideStar);
    fixture.detectChanges();
    expect(dynamic.classList).toContain('lucide-star');
    expect(dynamic.classList).not.toContain('lucide-search');
    expect(dynamic.querySelectorAll('circle')).toHaveLength(0);
    expect(dynamic.classList).toContain('size-4');
  });
});
