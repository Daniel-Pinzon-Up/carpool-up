import { TestBed } from '@angular/core/testing';
import { SecureFileService } from '../../core/files/secure-file.service';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import Approvals from './approvals';
import { ApprovalItem, ApprovalsApi } from './approvals.service';

function item(id: string, name: string, sex: 'female' | 'male' = 'female'): ApprovalItem {
  return {
    id,
    type: 'identity',
    doc_kind: 'student_card',
    status: 'pending',
    submitted_at: '2026-10-01T12:00:00Z',
    reviewed_at: null,
    rejection_reason: null,
    semester: '2026-2',
    license_expires_on: null,
    applicant: {
      id: `u-${id}`,
      full_name: name,
      program: null,
      role: 'passenger',
      sex,
      status: 'pending_approval',
    },
  };
}

async function settle(): Promise<void> {
  for (let i = 0; i < 5; i++) await Promise.resolve();
}

describe('Approvals', () => {
  let api: {
    queue: ReturnType<typeof vi.fn>;
    counts: ReturnType<typeof vi.fn>;
    approve: ReturnType<typeof vi.fn>;
    reject: ReturnType<typeof vi.fn>;
    filePath: (id: string) => string;
  };

  beforeEach(() => {
    api = {
      queue: vi
        .fn()
        .mockResolvedValue({
          items: [item('a', 'Laura Gomez', 'male'), item('b', 'Andres Rojas')],
          next_cursor: null,
        }),
      counts: vi.fn().mockResolvedValue({ identity: 2, license: 0 }),
      approve: vi.fn().mockResolvedValue(item('a', 'Laura Gomez')),
      reject: vi.fn(),
      filePath: (id: string) => `/api/v1/admin/files/${id}`,
    };
    TestBed.configureTestingModule({
      imports: [Approvals, getTranslocoTestingModule()],
      providers: [
        { provide: ApprovalsApi, useValue: api },
        {
          provide: SecureFileService,
          useValue: {
            load: vi.fn().mockResolvedValue({ url: 'blob:x', type: 'image/png', isPdf: false }),
            release: vi.fn(),
          },
        },
      ],
    });
  });

  it('muestra la cola y abre el primer documento', async () => {
    const fixture = TestBed.createComponent(Approvals);
    await settle();
    fixture.detectChanges();
    const text = fixture.nativeElement.textContent as string;
    expect(text).toContain('Laura Gomez');
    expect(text).toContain('Andres Rojas');
    expect(fixture.nativeElement.querySelector('#approval-name').textContent).toContain(
      'Laura Gomez',
    );
    expect(fixture.nativeElement.querySelector('img')).toBeTruthy();
  });

  it('al aprobar envia la correccion de sexo y pasa al siguiente', async () => {
    const fixture = TestBed.createComponent(Approvals);
    await settle();
    fixture.detectChanges();
    const select = fixture.nativeElement.querySelector(
      'cp-glass-select select',
    ) as HTMLSelectElement;
    select.value = 'female';
    select.dispatchEvent(new Event('change'));

    const approve = Array.from(fixture.nativeElement.querySelectorAll('button')).find((b) =>
      (b as HTMLElement).textContent?.includes('Aprobar'),
    ) as HTMLButtonElement;
    approve.click();
    await settle();
    fixture.detectChanges();

    expect(api.approve).toHaveBeenCalledWith('a', 'female');
    expect(fixture.nativeElement.querySelector('#approval-name').textContent).toContain(
      'Andres Rojas',
    );
  });

  it('no envia sexo si coincide con el declarado', async () => {
    const fixture = TestBed.createComponent(Approvals);
    await settle();
    fixture.detectChanges();
    const approve = Array.from(fixture.nativeElement.querySelectorAll('button')).find((b) =>
      (b as HTMLElement).textContent?.includes('Aprobar'),
    ) as HTMLButtonElement;
    approve.click();
    await settle();
    expect(api.approve).toHaveBeenCalledWith('a', null);
  });
});
