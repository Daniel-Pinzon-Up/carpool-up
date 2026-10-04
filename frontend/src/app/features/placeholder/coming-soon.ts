import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { TranslocoPipe } from '@jsverse/transloco';
import { LucideHammer } from '@lucide/angular';
import { EmptyState } from '../../shared/ui/empty-state';
import { GlassCard } from '../../shared/ui/glass-card';

/** Destino de navegacion aun no construido. Cada paso del plan lo reemplaza por su feature. */
@Component({
  selector: 'cp-coming-soon',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [EmptyState, GlassCard, TranslocoPipe],
  template: `
    <h1 class="mb-6 text-2xl font-bold sm:text-3xl">{{ 'nav.' + section | transloco }}</h1>
    <cp-glass-card>
      <cp-empty-state
        [icon]="icon"
        [title]="'placeholder.title' | transloco"
        [description]="'placeholder.description' | transloco"
      />
    </cp-glass-card>
  `,
})
export default class ComingSoon {
  protected readonly section = inject(ActivatedRoute).snapshot.data['section'] as string;
  protected readonly icon = LucideHammer;
}
