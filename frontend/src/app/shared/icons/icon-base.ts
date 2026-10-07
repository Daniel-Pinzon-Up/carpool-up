import { Directive, ElementRef, Renderer2, Type, effect, inject, input } from '@angular/core';

/** Un nodo SVG de Lucide: etiqueta y atributos (path, circle, rect, line...). */
export type IconNode = readonly (readonly [string, Readonly<Record<string, string>>])[];

export interface LucideIconData {
  readonly name: string;
  readonly node: IconNode;
}

/** Clase de un icono: se usa en plantillas como <svg lucideSearch> y como valor (iconos dinamicos). */
export type LucideIcon = Type<unknown> & { readonly icon: LucideIconData };

const SVG_NS = 'http://www.w3.org/2000/svg';

/** Atributos de Lucide por defecto; las clases de Tailwind (size-5, text-*) los ajustan. */
const DEFAULT_ATTRIBUTES: Record<string, string> = {
  width: '24',
  height: '24',
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  'stroke-width': '2',
  'stroke-linecap': 'round',
  'stroke-linejoin': 'round',
};

/**
 * Dibuja un icono dentro del <svg> anfitrion. Usa Renderer2 (no innerHTML, que el saneador de
 * Angular vaciaria) y conserva las clases y atributos que ya tenga el elemento.
 */
function paint(
  host: SVGElement,
  renderer: Renderer2,
  icon: LucideIconData,
  previous?: string,
): void {
  for (const [name, value] of Object.entries(DEFAULT_ATTRIBUTES)) {
    if (!host.hasAttribute(name)) renderer.setAttribute(host, name, value);
  }
  if (previous) renderer.removeClass(host, `lucide-${previous}`);
  renderer.addClass(host, 'lucide');
  renderer.addClass(host, `lucide-${icon.name}`);
  while (host.firstChild) renderer.removeChild(host, host.firstChild);
  for (const [tag, attributes] of icon.node) {
    const child = renderer.createElement(tag, SVG_NS) as SVGElement;
    for (const [name, value] of Object.entries(attributes)) {
      if (name !== 'key') renderer.setAttribute(child, name, value);
    }
    renderer.appendChild(host, child);
  }
}

/** Base de cada icono generado en lucide.ts: lee el dibujo de la propiedad estatica "icon". */
@Directive()
export abstract class LucideIconBase {
  constructor() {
    const host = inject<ElementRef<SVGElement>>(ElementRef).nativeElement;
    paint(host, inject(Renderer2), (this.constructor as LucideIcon).icon);
  }
}

/** Icono elegido en tiempo de ejecucion: <svg [lucideIcon]="item.icon">. */
@Directive({ selector: 'svg[lucideIcon]' })
export class LucideDynamicIcon {
  readonly lucideIcon = input.required<LucideIcon>();

  constructor() {
    const host = inject<ElementRef<SVGElement>>(ElementRef).nativeElement;
    const renderer = inject(Renderer2);
    let previous: string | undefined;
    effect(() => {
      const icon = this.lucideIcon().icon;
      paint(host, renderer, icon, previous);
      previous = icon.name;
    });
  }
}
