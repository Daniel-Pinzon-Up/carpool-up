import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { GlassTabs } from '../../../shared/ui/glass-tabs';
import { PicoPlacaPanel, PlacesPanel, SemestersPanel } from './catalog-panels';
import { AdminsPanel, AuditPanel } from './governance-panels';
import { ParametersPanel } from './parameters-panel';

const SECTIONS = ['parameters', 'semesters', 'places', 'picoPlaca', 'admins', 'audit'] as const;
type Section = (typeof SECTIONS)[number];

/** Configuracion completa del superadmin; cada pestana carga sus datos al abrirse. */
@Component({
  selector: 'cp-admin-settings',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    TranslocoPipe,
    GlassTabs,
    AdminsPanel,
    AuditPanel,
    ParametersPanel,
    PicoPlacaPanel,
    PlacesPanel,
    SemestersPanel,
  ],
  template: `
    <div class="mx-auto flex max-w-5xl flex-col gap-5 py-2">
      <header>
        <h1 class="text-2xl font-bold sm:text-3xl">{{ 'nav.settings' | transloco }}</h1>
        <p class="text-muted">{{ 'admin.settings.subtitle' | transloco }}</p>
      </header>
      <cp-glass-tabs
        #tabsRef
        [tabs]="tabs()"
        [label]="'nav.settings' | transloco"
        [(selected)]="section"
      />
      <section
        [id]="tabsRef.panelId(section())"
        role="tabpanel"
        [attr.aria-labelledby]="tabsRef.tabId(section())"
      >
        @switch (section()) {
          @case ('parameters') {
            <cp-parameters-panel />
          }
          @case ('semesters') {
            <cp-semesters-panel />
          }
          @case ('places') {
            <cp-places-panel />
          }
          @case ('picoPlaca') {
            <cp-pico-placa-panel />
          }
          @case ('admins') {
            <cp-admins-panel />
          }
          @case ('audit') {
            <cp-audit-panel />
          }
        }
      </section>
    </div>
  `,
})
export default class AdminSettings {
  private readonly transloco = inject(TranslocoService);

  protected readonly section = signal<Section>('parameters');
  protected readonly tabs = computed(() => {
    return SECTIONS.map((id) => ({
      id,
      label: this.transloco.translate(`admin.settings.tabs.${id}`),
    }));
  });
}
