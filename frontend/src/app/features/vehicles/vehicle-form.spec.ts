import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { AuthService } from '../../core/auth/auth.service';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import VehicleForm from './vehicle-form';
import { VehiclesApi, normalizePlate } from './vehicles.api';

async function settle(): Promise<void> {
  for (let i = 0; i < 5; i++) await Promise.resolve();
}

describe('normalizePlate', () => {
  it('quita espacios y guiones y pasa a mayusculas', () => {
    expect(normalizePlate(' abc-12 3 ')).toBe('ABC123');
  });
});

describe('VehicleForm', () => {
  let api: {
    create: ReturnType<typeof vi.fn>;
    update: ReturnType<typeof vi.fn>;
    uploadPhoto: ReturnType<typeof vi.fn>;
    list: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    api = {
      create: vi.fn().mockResolvedValue({ id: 'v1' }),
      update: vi.fn(),
      uploadPhoto: vi.fn(),
      list: vi.fn().mockResolvedValue([]),
    };
    TestBed.configureTestingModule({
      imports: [VehicleForm, getTranslocoTestingModule()],
      providers: [
        provideRouter([]),
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: VehiclesApi, useValue: api },
      ],
    });
    vi.spyOn(TestBed.inject(AuthService), 'reloadMe').mockResolvedValue({} as never);
    vi.spyOn(TestBed.inject(Router), 'navigateByUrl').mockResolvedValue(true);
  });

  function fill(
    fixture: ReturnType<typeof TestBed.createComponent<VehicleForm>>,
    values: Record<string, string>,
  ) {
    for (const [label, value] of Object.entries(values)) {
      const input = Array.from(fixture.nativeElement.querySelectorAll('cp-glass-input')).find(
        (el) => (el as HTMLElement).querySelector('label')?.textContent?.includes(label),
      ) as HTMLElement;
      const field = input.querySelector('input') as HTMLInputElement;
      field.value = value;
      field.dispatchEvent(new Event('input'));
    }
  }

  function submit(fixture: ReturnType<typeof TestBed.createComponent<VehicleForm>>) {
    (fixture.nativeElement.querySelector('form') as HTMLFormElement).dispatchEvent(
      new Event('submit'),
    );
  }

  it('valida la placa segun el tipo y no envia si es invalida', async () => {
    const fixture = TestBed.createComponent(VehicleForm);
    fixture.detectChanges();
    fill(fixture, { Placa: 'ABC12D', Marca: 'Chevrolet', Modelo: 'Spark', Color: 'Gris' });
    submit(fixture);
    await settle();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('tres letras y tres números');
    expect(api.create).not.toHaveBeenCalled();
  });

  it('crea el vehiculo con la placa normalizada', async () => {
    const fixture = TestBed.createComponent(VehicleForm);
    fixture.detectChanges();
    fill(fixture, { Placa: 'abc 123', Marca: 'Chevrolet', Modelo: 'Spark', Color: 'Gris' });
    submit(fixture);
    await settle();
    expect(api.create).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'car', plate: 'ABC123', brand: 'Chevrolet', capacity: 5 }),
    );
  });
});
