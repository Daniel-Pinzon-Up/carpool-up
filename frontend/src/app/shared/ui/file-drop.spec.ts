import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { FormControl, ReactiveFormsModule } from '@angular/forms';
import { getTranslocoTestingModule } from '../../../testing/transloco-testing';
import { FileDrop } from './file-drop';

@Component({
  imports: [FileDrop, ReactiveFormsModule],
  template: `<cp-file-drop
    label="Documento"
    [formControl]="control"
    [maxMb]="1"
    typeError="tipo invalido"
    sizeError="muy grande"
  />`,
})
class Host {
  control = new FormControl<File | null>(null);
}

function setup() {
  TestBed.configureTestingModule({ imports: [Host, getTranslocoTestingModule()] });
  const fixture = TestBed.createComponent(Host);
  fixture.detectChanges();
  const drop = fixture.debugElement.children[0].componentInstance as FileDrop;
  return { fixture, drop };
}

describe('FileDrop', () => {
  it('acepta un PDF dentro del limite', () => {
    const { fixture, drop } = setup();
    const file = new File(['%PDF-1.7'], 'carnet.pdf', { type: 'application/pdf' });
    drop.select(file);
    fixture.detectChanges();
    expect(fixture.componentInstance.control.value).toBe(file);
    expect(fixture.nativeElement.textContent).toContain('carnet.pdf');
  });

  it('rechaza tipos no permitidos con un mensaje anunciado', () => {
    const { fixture, drop } = setup();
    drop.select(new File(['x'], 'virus.exe', { type: 'application/x-msdownload' }));
    fixture.detectChanges();
    expect(fixture.componentInstance.control.value).toBeNull();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain(
      'tipo invalido',
    );
  });

  it('rechaza archivos demasiado grandes', () => {
    const { fixture, drop } = setup();
    const big = new File([new Uint8Array(1024 * 1024 + 1)], 'grande.jpg', { type: 'image/jpeg' });
    drop.select(big);
    fixture.detectChanges();
    expect(fixture.componentInstance.control.value).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('muy grande');
  });
});
