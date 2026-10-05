import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { SecureFileService } from './secure-file.service';

describe('SecureFileService', () => {
  it('descarga con HttpClient, expone un object URL y lo libera', async () => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    const service = TestBed.inject(SecureFileService);
    const http = TestBed.inject(HttpTestingController);
    const create = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:local-1');
    const revoke = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);

    const loading = service.load('/api/v1/admin/files/abc');
    const request = http.expectOne('/api/v1/admin/files/abc');
    expect(request.request.responseType).toBe('blob');
    request.flush(new Blob(['%PDF-1.7'], { type: 'application/pdf' }));

    const file = await loading;
    expect(file).toEqual({ url: 'blob:local-1', type: 'application/pdf', isPdf: true });
    expect(create).toHaveBeenCalledOnce();

    service.release(file);
    expect(revoke).toHaveBeenCalledWith('blob:local-1');
    service.release(null);
    expect(revoke).toHaveBeenCalledOnce();
  });
});
