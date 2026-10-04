import { TestBed } from '@angular/core/testing';
import { ToastService } from './toast.service';

describe('ToastService', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('muestra y descarta avisos automaticamente', () => {
    const service = TestBed.inject(ToastService);
    service.show('Hola', 'success', 1000);
    expect(service.toasts()).toHaveLength(1);
    vi.advanceTimersByTime(1000);
    expect(service.toasts()).toHaveLength(0);
  });

  it('mantiene como maximo tres avisos visibles', () => {
    const service = TestBed.inject(ToastService);
    ['a', 'b', 'c', 'd'].forEach((message) => service.show(message, 'info', 0));
    expect(service.toasts().map((toast) => toast.message)).toEqual(['b', 'c', 'd']);
  });

  it('permite descartar un aviso', () => {
    const service = TestBed.inject(ToastService);
    const id = service.show('Hola', 'info', 0);
    service.dismiss(id);
    expect(service.toasts()).toHaveLength(0);
  });
});
