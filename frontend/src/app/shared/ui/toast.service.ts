import { Injectable, signal } from '@angular/core';

export type ToastTone = 'info' | 'success' | 'warning' | 'danger';

export interface Toast {
  id: number;
  tone: ToastTone;
  message: string;
}

const DEFAULT_DURATION_MS = 5000;

@Injectable({ providedIn: 'root' })
export class ToastService {
  private nextId = 0;
  private readonly items = signal<Toast[]>([]);
  readonly toasts = this.items.asReadonly();

  show(message: string, tone: ToastTone = 'info', durationMs = DEFAULT_DURATION_MS): number {
    const id = ++this.nextId;
    this.items.update((list) => [...list.slice(-2), { id, tone, message }]);
    if (durationMs > 0) setTimeout(() => this.dismiss(id), durationMs);
    return id;
  }

  dismiss(id: number): void {
    this.items.update((list) => list.filter((toast) => toast.id !== id));
  }
}
