import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  signal,
} from '@angular/core';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { DomSanitizer, SafeResourceUrl, SafeUrl } from '@angular/platform-browser';
import { TranslocoPipe, TranslocoService } from '@jsverse/transloco';
import { LucideCheck, LucideInbox, LucideRefreshCw, LucideX } from '@icons';
import { firstValueFrom } from 'rxjs';
import { LoadedFile, SecureFileService } from '../../core/files/secure-file.service';
import { apiErrorMessage } from '../../core/http/api-error-message';
import { Avatar } from '../../shared/ui/avatar';
import { DialogService } from '../../shared/ui/dialog.service';
import { EmptyState } from '../../shared/ui/empty-state';
import { ErrorState } from '../../shared/ui/error-state';
import { GlassButton } from '../../shared/ui/glass-button';
import { GlassCard } from '../../shared/ui/glass-card';
import { GlassSelect, SelectOption } from '../../shared/ui/glass-select';
import { GlassTabs, TabItem } from '../../shared/ui/glass-tabs';
import { Skeleton } from '../../shared/ui/skeleton';
import { ToastService } from '../../shared/ui/toast.service';
import { ApprovalItem, ApprovalType, ApprovalsApi } from './approvals.service';
import { RejectDialog } from './reject-dialog';

/** Cola de aprobacion: lista en orden de llegada, visor del documento y decision. */
@Component({
  selector: 'cp-approvals',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    ReactiveFormsModule,
    TranslocoPipe,
    Avatar,
    EmptyState,
    ErrorState,
    GlassButton,
    GlassCard,
    GlassSelect,
    GlassTabs,
    Skeleton,
    LucideCheck,
    LucideX,
    LucideRefreshCw,
  ],
  templateUrl: './approvals.html',
})
export default class Approvals {
  private readonly api = inject(ApprovalsApi);
  private readonly files = inject(SecureFileService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly transloco = inject(TranslocoService);
  private readonly toasts = inject(ToastService);
  private readonly dialogs = inject(DialogService);

  protected readonly emptyIcon = LucideInbox;
  protected readonly type = signal<ApprovalType>('identity');
  protected readonly items = signal<ApprovalItem[]>([]);
  protected readonly counts = signal<Record<ApprovalType, number>>({ identity: 0, license: 0 });
  protected readonly loading = signal(true);
  protected readonly loadError = signal<string | null>(null);
  protected readonly selectedId = signal<string | null>(null);
  protected readonly selected = computed(
    () => this.items().find((item) => item.id === this.selectedId()) ?? null,
  );
  protected readonly file = signal<LoadedFile | null>(null);
  protected readonly fileLoading = signal(false);
  protected readonly fileError = signal(false);
  protected readonly deciding = signal(false);
  protected readonly sex = new FormControl<string>('', { nonNullable: true });

  protected readonly tabs = computed<TabItem[]>(() => {
    const counts = this.counts();
    return (['identity', 'license'] as const).map((id) => ({
      id,
      label: this.transloco.translate(`approvals.tabs.${id}`, { count: counts[id] }),
    }));
  });
  protected readonly sexOptions = computed<SelectOption[]>(() =>
    ['female', 'male'].map((value) => ({
      value,
      label: this.transloco.translate(`fields.sexOptions.${value}`),
    })),
  );
  protected readonly fileUrl = computed<SafeUrl | SafeResourceUrl | null>(() => {
    const file = this.file();
    if (!file) return null;
    // URL local creada por nosotros a partir del archivo descargado con autenticacion.
    return file.isPdf
      ? this.sanitizer.bypassSecurityTrustResourceUrl(file.url)
      : this.sanitizer.bypassSecurityTrustUrl(file.url);
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => this.files.release(this.file()));
    void this.reload();
  }

  protected setType(type: string): void {
    this.type.set(type as ApprovalType);
    void this.reload();
  }

  protected async reload(): Promise<void> {
    this.loading.set(true);
    this.loadError.set(null);
    try {
      const [page, counts] = await Promise.all([this.api.queue(this.type()), this.api.counts()]);
      this.items.set(page.items);
      this.counts.set(counts);
      await this.select(page.items[0] ?? null);
    } catch (error) {
      this.loadError.set(apiErrorMessage(this.transloco, error));
    } finally {
      this.loading.set(false);
    }
  }

  protected async select(item: ApprovalItem | null): Promise<void> {
    this.files.release(this.file());
    this.file.set(null);
    this.fileError.set(false);
    this.selectedId.set(item?.id ?? null);
    if (!item) return;
    this.sex.setValue(item.applicant.sex);
    this.fileLoading.set(true);
    try {
      const loaded = await this.files.load(this.api.filePath(item.id));
      if (this.selectedId() === item.id) this.file.set(loaded);
      else this.files.release(loaded);
    } catch {
      this.fileError.set(true);
    } finally {
      this.fileLoading.set(false);
    }
  }

  protected async approve(item: ApprovalItem): Promise<void> {
    const sex =
      item.type === 'identity' && this.sex.value !== item.applicant.sex
        ? (this.sex.value as 'female' | 'male')
        : null;
    await this.decide(item, () => this.api.approve(item.id, sex), 'approvals.approved');
  }

  protected async reject(item: ApprovalItem): Promise<void> {
    const ref = this.dialogs.open<string, { name: string }, RejectDialog>(RejectDialog, {
      name: item.applicant.full_name,
    });
    const reason = await firstValueFrom(ref.closed);
    if (!reason) return;
    await this.decide(item, () => this.api.reject(item.id, reason), 'approvals.rejected');
  }

  private async decide(
    item: ApprovalItem,
    action: () => Promise<ApprovalItem>,
    messageKey: string,
  ): Promise<void> {
    this.deciding.set(true);
    try {
      await action();
      this.toasts.show(
        this.transloco.translate(messageKey, { name: item.applicant.full_name }),
        'success',
      );
      const remaining = this.items().filter((i) => i.id !== item.id);
      this.items.set(remaining);
      this.counts.update((c) => ({ ...c, [item.type]: Math.max(0, c[item.type] - 1) }));
      await this.select(remaining[0] ?? null);
      queueMicrotask(() => document.querySelector<HTMLElement>('#approval-detail')?.focus());
    } catch (error) {
      this.toasts.show(apiErrorMessage(this.transloco, error), 'danger');
    } finally {
      this.deciding.set(false);
    }
  }

  protected formatDate(iso: string | null): string {
    if (!iso) return '';
    return new Date(iso).toLocaleString(this.transloco.getActiveLang(), {
      dateStyle: 'medium',
      timeStyle: iso.length > 10 ? 'short' : undefined,
    });
  }
}
