import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import {
  LucideBackpack,
  LucideCigaretteOff,
  LucideDog,
  LucideMail,
  LucideMusic,
  LucideSearchX,
  LucideTrash2,
  LucideVenus,
} from '@icons';
import { ThemeService } from '../../core/theme/theme.service';
import { Avatar } from '../../shared/ui/avatar';
import { DialogService } from '../../shared/ui/dialog.service';
import { EmptyState } from '../../shared/ui/empty-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassChip } from '../../shared/ui/glass-chip';
import { GlassInput } from '../../shared/ui/glass-input';
import { GlassSelect, SelectOption } from '../../shared/ui/glass-select';
import { GlassTabs, TabItem } from '../../shared/ui/glass-tabs';
import { SeatPicker } from '../../shared/ui/seat-picker';
import { Skeleton } from '../../shared/ui/skeleton';
import { StarRating } from '../../shared/ui/star-rating';
import { StatusBadge } from '../../shared/ui/status-badge';
import { Stepper } from '../../shared/ui/stepper';
import { ToastService } from '../../shared/ui/toast.service';
import { SampleSheet } from './sample-sheet';

interface PreviewVariant {
  key: string;
  classes: string;
}

/** Catalogo visual del sistema de diseno (solo desarrollo). Criterio de aceptacion del paso 0. */
@Component({
  selector: 'cp-catalog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    Avatar,
    EmptyState,
    GlassButton,
    GlassCard,
    GlassChip,
    GlassInput,
    GlassSelect,
    GlassTabs,
    SeatPicker,
    Skeleton,
    StarRating,
    StatusBadge,
    Stepper,
    LucideTrash2,
  ],
  templateUrl: './catalog.html',
})
export default class Catalog {
  protected readonly theme = inject(ThemeService);
  private readonly dialogs = inject(DialogService);
  private readonly toasts = inject(ToastService);
  private readonly transloco = inject(TranslocoService);

  protected readonly icons = {
    mail: LucideMail,
    pets: LucideDog,
    luggage: LucideBackpack,
    smoking: LucideCigaretteOff,
    music: LucideMusic,
    women: LucideVenus,
    empty: LucideSearchX,
  };

  protected readonly previews: PreviewVariant[] = [
    { key: 'light', classes: 'theme-light' },
    { key: 'dark', classes: 'theme-dark' },
    { key: 'lightSolid', classes: 'theme-light reduce-transparency' },
    { key: 'darkSolid', classes: 'theme-dark reduce-transparency' },
  ];

  protected readonly email = new FormControl('', { nonNullable: true });
  protected readonly emailInvalid = new FormControl('juan@gmail.com', { nonNullable: true });
  protected readonly vehicle = new FormControl('car', { nonNullable: true });
  protected readonly seats = new FormControl(1, { nonNullable: true });
  protected readonly rating = new FormControl<number | null>(4);
  protected readonly ratingValue = toSignal(this.rating.valueChanges, {
    initialValue: this.rating.value,
  });

  // selectTranslateObject vuelve a emitir al cambiar de idioma.
  private readonly t = toSignal(
    this.transloco.selectTranslateObject<Record<string, Record<string, string>>>('catalog'),
  );
  protected readonly vehicleOptions = computed<SelectOption[]>(() => [
    { value: 'car', label: this.t()?.['select']?.['car'] ?? '' },
    { value: 'motorcycle', label: this.t()?.['select']?.['motorcycle'] ?? '' },
  ]);
  protected readonly tabs = computed<TabItem[]>(() =>
    ['upcoming', 'inProgress', 'history'].map((id) => ({
      id,
      label: this.t()?.['tabs']?.[id] ?? '',
    })),
  );
  protected readonly selectedTab = signal('upcoming');
  protected readonly pets = signal(true);
  protected readonly luggage = signal(false);
  protected readonly noSmoking = signal(true);
  protected readonly music = signal(false);
  protected readonly womenOnly = signal(false);
  protected readonly loadingButton = signal(false);
  protected readonly step = signal(1);

  protected simulateLoading(): void {
    this.loadingButton.set(true);
    setTimeout(() => this.loadingButton.set(false), 1500);
  }

  protected openModal(): void {
    this.dialogs.open(SampleSheet, { variant: 'modal' }, 'modal');
  }

  protected openSheet(): void {
    this.dialogs.open(SampleSheet, { variant: 'sheet' }, 'sheet');
  }

  protected async confirmDelete(): Promise<void> {
    const t = (key: string) => this.transloco.translate(`catalog.dialogs.${key}`);
    const confirmed = await this.dialogs.confirm({
      title: t('confirmTitle'),
      message: t('confirmMessage'),
      confirmLabel: t('confirmAction'),
      cancelLabel: this.transloco.translate('common.cancel'),
      danger: true,
    });
    this.toasts.show(t(confirmed ? 'confirmed' : 'cancelled'), confirmed ? 'success' : 'info');
  }

  protected toast(tone: 'info' | 'success' | 'warning' | 'danger'): void {
    this.toasts.show(this.transloco.translate(`catalog.toasts.${tone}Message`), tone);
  }
}
