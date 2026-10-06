import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { Meter } from '../../shared/charts/meter';
import { MonthColumns, MonthValue } from '../../shared/charts/month-columns';
import DriverStatsPage from '../stats/stats-views';
import { PassengerHistoryItem } from './history-items';
import RatePage from './rate-page';
import { DriverStats, PendingRating, RatingsApi, monthLabels } from './ratings.api';

async function settle(): Promise<void> {
  for (let i = 0; i < 10; i++) await Promise.resolve();
}

function text(element: HTMLElement): string {
  return element.textContent?.replace(/\s+/g, ' ') ?? '';
}

const PENDING: PendingRating = {
  trip_id: 't1',
  departs_at: '2026-10-06T12:00:00Z',
  origin: 'Ciudad Universitaria',
  destination: 'Terminal',
  target_id: 'd1',
  target_name: 'Carlos Ruiz',
  target_role: 'driver',
  criteria: ['punctuality', 'safe_driving', 'courtesy', 'cleanliness'],
  closes_at: '2026-10-13T12:10:00Z',
};

describe('RatePage', () => {
  it('pide todos los criterios, envia la calificacion y quita la tarjeta', async () => {
    const api = {
      pending: vi.fn().mockResolvedValue([PENDING, { ...PENDING, trip_id: 't2' }]),
      rate: vi.fn().mockResolvedValue({}),
    };
    TestBed.configureTestingModule({
      imports: [RatePage, getTranslocoTestingModule()],
      providers: [provideRouter([]), { provide: RatingsApi, useValue: api }],
    });
    const fixture = TestBed.createComponent(RatePage);
    fixture.componentRef.setInput('tripId', 't1');
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    // Solo el viaje pedido.
    expect(element.querySelectorAll('form')).toHaveLength(1);
    expect(text(element)).toContain('Conductor: Carlos Ruiz');
    expect(text(element)).toContain('Conducción segura');

    const form = element.querySelector('form') as HTMLFormElement;
    form.dispatchEvent(new Event('submit'));
    fixture.detectChanges();
    expect(text(element)).toContain('Califica todos los criterios');
    expect(api.rate).not.toHaveBeenCalled();

    // Cinco estrellas en cada criterio salvo limpieza, con cuatro.
    for (const group of Array.from(element.querySelectorAll('[role=radiogroup]'))) {
      const stars = group.querySelectorAll('[role=radio]');
      const label = group.textContent ?? '';
      (stars[label.includes('Limpieza') ? 3 : 4] as HTMLButtonElement).click();
    }
    fixture.detectChanges();
    form.dispatchEvent(new Event('submit'));
    await settle();
    fixture.detectChanges();
    expect(api.rate).toHaveBeenCalledWith('t1', {
      target_id: 'd1',
      scores: { punctuality: 5, safe_driving: 5, courtesy: 5, cleanliness: 4 },
      comment: null,
    });
    expect(element.querySelector('form')).toBeNull();
    expect(text(element)).toContain('Listo, calificaste todo');
  });
});

describe('graficos', () => {
  it('las columnas por mes son accesibles, rotulan el maximo y tienen tabla', () => {
    TestBed.configureTestingModule({ imports: [MonthColumns, getTranslocoTestingModule()] });
    const fixture = TestBed.createComponent(MonthColumns);
    const items: MonthValue[] = ['2026-08', '2026-09', '2026-10'].map((month, i) => ({
      ...monthLabels(month, 'es'),
      value: [1, 4, 2][i],
      display: `${[1, 4, 2][i]} viajes`,
    }));
    fixture.componentRef.setInput('title', 'Viajes por mes');
    fixture.componentRef.setInput('valueLabel', 'Viajes');
    fixture.componentRef.setInput('items', items);
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    const bars = element.querySelectorAll('button');
    expect(Array.from(bars).map((b) => b.getAttribute('aria-label'))).toEqual([
      'agosto de 2026: 1 viajes',
      'septiembre de 2026: 4 viajes',
      'octubre de 2026: 2 viajes',
    ]);
    // Solo el maximo lleva etiqueta directa.
    expect(Array.from(bars).map((b) => b.textContent?.trim())).toEqual(['', '4 viajes', '']);
    bars[2].dispatchEvent(new Event('focus'));
    fixture.detectChanges();
    expect(element.querySelector('[role=status]')?.textContent).toContain('2 viajes');
    expect(element.querySelectorAll('tbody tr')).toHaveLength(3);
  });

  it('el medidor expone su valor como texto', () => {
    TestBed.configureTestingModule({ imports: [Meter] });
    const fixture = TestBed.createComponent(Meter);
    fixture.componentRef.setInput('label', 'Puntualidad');
    fixture.componentRef.setInput('value', 4.5);
    fixture.componentRef.setInput('max', 5);
    fixture.componentRef.setInput('display', '4,5 / 5');
    fixture.detectChanges();
    const meter = fixture.nativeElement.querySelector('[role=meter]') as HTMLElement;
    expect(meter.getAttribute('aria-valuetext')).toBe('4,5 / 5');
    expect((meter.firstElementChild as HTMLElement).style.width).toBe('90%');
  });
});

describe('historial y estadisticas', () => {
  it('el historial del pasajero muestra el ticket y la accion de calificar', () => {
    TestBed.configureTestingModule({
      imports: [PassengerHistoryItem, getTranslocoTestingModule()],
      providers: [provideRouter([])],
    });
    const fixture = TestBed.createComponent(PassengerHistoryItem);
    fixture.componentRef.setInput('entry', {
      booking_id: 'b1',
      trip_id: 't1',
      departs_at: '2026-10-06T12:00:00Z',
      origin: 'Ciudad Universitaria',
      destination: 'Terminal',
      driver_name: 'Carlos Ruiz',
      trip_status: 'completed',
      booking_status: 'completed',
      seats: 1,
      amount: 2000,
      ticket_code: 'CP-ABCD-EFGH',
      paid_confirmed: false,
      rating: 'pending',
      rating_closes_at: '2026-10-13T12:00:00Z',
    });
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(text(element)).toContain('CP-ABCD-EFGH');
    expect(text(element)).toContain('Aporte por confirmar');
    expect(element.querySelector('a[href="/calificar/t1"]')?.textContent).toContain(
      'Calificar al conductor',
    );
  });

  it('las estadisticas del conductor muestran indicadores y ocupacion', async () => {
    const stats: DriverStats = {
      trips: 12,
      passengers: 20,
      occupancy: 0.556,
      contributions: 48000,
      confirmed_contributions: 30000,
      cancellations: 1,
      rating: { average: 4.6, count: 9, criteria: { punctuality: 4.8, safe_driving: 4.5 } },
      by_month: [{ month: '2026-10', trips: 12, passengers: 20 }],
    };
    TestBed.configureTestingModule({
      imports: [DriverStatsPage, getTranslocoTestingModule()],
      providers: [
        { provide: RatingsApi, useValue: { driverStats: vi.fn().mockResolvedValue(stats) } },
      ],
    });
    const fixture = TestBed.createComponent(DriverStatsPage);
    fixture.detectChanges();
    await settle();
    fixture.detectChanges();
    const content = text(fixture.nativeElement);
    expect(content).toContain('Viajes cancelados');
    expect(content).toContain('56');
    expect(content).toContain('Calificación 4,6 de 5 (9)');
    expect(fixture.nativeElement.querySelectorAll('[role=meter]').length).toBeGreaterThanOrEqual(4);
  });
});
