import {
  APIRequestContext,
  Browser,
  BrowserContext,
  Page,
  TestInfo,
  expect,
  request,
  test,
} from '@playwright/test';
import { Role, credentials, prepare } from './support';

/**
 * Recorrido completo de punta a punta con los cuatro roles, sobre la app real:
 * conductor listo para publicar -> publica -> la pasajera pide cupo -> el conductor acepta,
 * inicia, marca el abordaje y finaliza -> la pasajera califica -> ticket y vista del admin.
 * La preparacion (licencia, vehiculo, limpieza de corridas anteriores) va por la API.
 */
test.describe.configure({ mode: 'serial' });

// PNG valido de 1x1: el servidor revisa la firma y lo abre con Pillow.
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  'base64',
);
const PAMPLONA = { latitude: 7.3756, longitude: -72.6475 };

interface Api {
  ctx: APIRequestContext;
  token: string;
  get<T>(path: string): Promise<T>;
  post<T>(path: string, data?: unknown): Promise<T>;
}

async function apiFor(role: Role, info: TestInfo): Promise<Api> {
  const { password, accounts } = credentials();
  const ctx = await request.newContext({
    baseURL: info.project.use.baseURL,
    ignoreHTTPSErrors: true,
  });
  const login = await ctx.post('/api/v1/auth/login', {
    data: { email: accounts[role], password },
  });
  expect(login.ok(), await login.text()).toBe(true);
  const token = (await login.json()).access_token as string;
  const headers = { Authorization: `Bearer ${token}` };
  const check = async (response: Awaited<ReturnType<APIRequestContext['get']>>) => {
    expect(response.ok(), `${response.url()} ${response.status()} ${await response.text()}`).toBe(
      true,
    );
    return response.status() === 204 ? undefined : response.json();
  };
  return {
    ctx,
    token,
    get: async (path) => check(await ctx.get(`/api/v1${path}`, { headers })),
    post: async (path, data = {}) => check(await ctx.post(`/api/v1${path}`, { headers, data })),
  };
}

/** Contexto de navegador con la sesion (cookie de refresco) que dejo el login por la API. */
async function browserFor(
  browser: Browser,
  api: Api,
  info: TestInfo,
  extra: Parameters<Browser['newContext']>[0] = {},
): Promise<BrowserContext> {
  return browser.newContext({
    baseURL: info.project.use.baseURL,
    ignoreHTTPSErrors: true,
    locale: 'es-CO',
    storageState: await api.ctx.storageState(),
    ...extra,
  });
}

function localDay(iso: string): { date: string; weekday: number } {
  const date = new Date(iso).toLocaleDateString('en-CA', { timeZone: 'America/Bogota' });
  const [y, m, d] = date.split('-').map(Number);
  return { date, weekday: (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7 };
}

interface Rule {
  vehicle_type: string;
  weekday: number;
  restricted_digits: number[];
  valid_from: string;
  valid_to: string | null;
  is_active: boolean;
}
interface Vehicle {
  id: string;
  type: string;
  plate: string;
  is_active: boolean;
}

test('recorrido completo: publicar, reservar, viajar, calificar y auditar', async ({
  browser,
}, info) => {
  test.skip(info.project.name !== 'desktop', 'el recorrido corre una vez, en escritorio');
  test.setTimeout(240_000);
  const driver = await apiFor('driver', info);
  const admin = await apiFor('admin', info);
  const superadmin = await apiFor('superadmin', info);
  const passenger = await apiFor('passenger', info);
  const driverMe = await driver.get<{ id: string; can_publish: boolean }>('/users/me');

  // --- Limpieza de corridas anteriores: viajes del conductor que sigan abiertos -----------
  const upcoming = await driver.get<{ items: { id: string; status: string }[] }>(
    '/trips/mine?scope=upcoming&limit=50',
  );
  for (const trip of upcoming.items) {
    if (trip.status === 'scheduled') {
      await driver.post(`/trips/${trip.id}/cancel`, { reason: 'Limpieza de la prueba E2E' });
    } else if (trip.status === 'in_progress') {
      const bookings = await driver.get<{ id: string; status: string }[]>(
        `/trips/${trip.id}/bookings`,
      );
      for (const b of bookings.filter((x) => x.status === 'accepted')) {
        await driver.post(`/bookings/${b.id}/boarded`);
      }
      await driver.post(`/trips/${trip.id}/finish`);
    }
  }

  // --- Conductor listo: licencia aprobada y vehiculo sin pico y placa ese dia -----------
  const departsAt = new Date(Date.now() + 20 * 60_000).toISOString();
  if (!driverMe.can_publish) {
    const license = await driver.get<{ status: string } | null>('/users/me/license');
    if (license?.status !== 'approved') {
      const expires = new Date(Date.now() + 365 * 86_400_000).toISOString().slice(0, 10);
      const upload = await driver.ctx.put('/api/v1/users/me/license', {
        headers: { Authorization: `Bearer ${driver.token}` },
        multipart: {
          expires_on: expires,
          document: { name: 'licencia.png', mimeType: 'image/png', buffer: PNG },
        },
      });
      expect(upload.ok(), await upload.text()).toBe(true);
      const queue = await admin.get<{ items: { id: string; applicant: { id: string } }[] }>(
        '/admin/approvals?type=license',
      );
      const item = queue.items.find((i) => i.applicant.id === driverMe.id);
      expect(item, 'la licencia del conductor E2E esta en la cola').toBeTruthy();
      await admin.post(`/admin/approvals/${item!.id}/approve`);
    }
  }
  const { date, weekday } = localDay(departsAt);
  const rules = await superadmin.get<Rule[]>('/admin/pico-placa');
  const restricted = new Set(
    rules
      .filter(
        (r) =>
          r.is_active &&
          r.vehicle_type === 'car' &&
          r.weekday === weekday &&
          r.valid_from <= date &&
          (!r.valid_to || r.valid_to >= date),
      )
      .flatMap((r) => r.restricted_digits),
  );
  const vehicles = await driver.get<Vehicle[]>('/vehicles');
  let vehicle = vehicles.find(
    (v) => v.is_active && v.type === 'car' && !restricted.has(Number(v.plate.at(-1))),
  );
  if (!vehicle) {
    const digit = [...Array(10).keys()].find((d) => !restricted.has(d))!;
    const plate = `EEZ${String(Math.floor(Math.random() * 90) + 10)}${digit}`;
    vehicle = await driver.post<Vehicle>('/vehicles', {
      type: 'car',
      plate,
      brand: 'Renault',
      model: 'Logan',
      color: 'Gris',
      year: 2020,
      capacity: 5,
    });
  }

  // --- Publicar ---------------------------------------------------------------------------
  const places = await driver.get<{ id: string; kind: string }[]>('/places');
  const origin = places.find((p) => p.kind === 'sector') ?? places[0];
  const destination = places.find((p) => p.kind === 'campus' && p.id !== origin.id)!;
  const trip = await driver.post<{ id: string }>('/trips', {
    place_ids: [origin.id, destination.id],
    departs_at: departsAt,
    vehicle_id: vehicle.id,
    seats: 3,
    price_per_seat: 2000,
    rules: [],
  });

  // --- Pasajera: pide cupo desde el detalle del viaje ------------------------------------
  const riderContext = await browserFor(browser, passenger, info);
  const rider: Page = await riderContext.newPage();
  await prepare(rider);
  // El mapa dibuja en un worker aparte: si no carga, el mapa queda gris sin dar otro error.
  const mapErrors: string[] = [];
  rider.on('console', (m) => {
    if (m.type() === 'error' && /worker/i.test(m.text())) mapErrors.push(m.text());
  });
  const mapWorker = rider.waitForResponse((r) => r.url().endsWith('/maplibre-gl-worker.mjs'));
  await rider.goto(`/viajes/${trip.id}`);
  expect((await mapWorker).headers()['content-type']).toContain('javascript');
  await rider.getByRole('button', { name: 'Solicitar cupo' }).click();
  await expect(rider.getByText('Solicitada').first()).toBeVisible();
  expect(mapErrors).toEqual([]);

  // --- Conductor: acepta, inicia, marca el abordaje y finaliza ---------------------------
  const driverContext = await browserFor(browser, driver, info, {
    permissions: ['geolocation'],
    geolocation: PAMPLONA,
  });
  const wheel: Page = await driverContext.newPage();
  await prepare(wheel);
  await wheel.goto('/solicitudes');
  await wheel.getByRole('button', { name: 'Aceptar' }).first().click();
  await expect(wheel.getByText('Reserva aceptada.')).toBeVisible();

  await wheel.goto(`/viajes/${trip.id}`);
  await wheel.getByRole('button', { name: 'Iniciar viaje' }).click();
  await expect(wheel.getByText('Viaje iniciado. Tus pasajeros ya ven tu ubicación.')).toBeVisible();
  await wheel.getByRole('button', { name: 'Abordó' }).click();
  await expect(wheel.getByText('Pasajero a bordo.')).toBeVisible();
  await wheel.getByRole('button', { name: 'Finalizar viaje' }).first().click();
  await wheel.getByRole('dialog').getByRole('button', { name: 'Finalizar viaje' }).click();
  await expect(wheel.getByText('Viaje finalizado. Se emitieron los tickets.')).toBeVisible();

  // --- Pasajera: califica al conductor ---------------------------------------------------
  await rider.goto(`/calificar/${trip.id}`);
  const stars = rider.getByRole('radio', { name: '5 de 5 estrellas' });
  await expect(stars.first()).toBeVisible();
  for (const star of await stars.all()) await star.click();
  await rider.getByRole('button', { name: 'Enviar calificación' }).click();
  await expect(rider.getByText('Gracias por calificar.')).toBeVisible();

  // --- Ticket emitido y viaje visible para el administrador ------------------------------
  const history = await passenger.get<{
    items: { trip_id: string; ticket_code: string | null; rating: string }[];
  }>('/history/passenger?limit=5');
  const entry = history.items.find((i) => i.trip_id === trip.id);
  expect(entry?.ticket_code).toMatch(/^CP-[A-Z0-9]{4}-[A-Z0-9]{4}$/);
  expect(entry?.rating).toBe('done');

  const adminContext = await browserFor(browser, admin, info);
  const desk: Page = await adminContext.newPage();
  await prepare(desk);
  await desk.goto(`/admin/viajes/${trip.id}`);
  await expect(desk.getByText('Finalizado').first()).toBeVisible();

  await Promise.all([riderContext.close(), driverContext.close(), adminContext.close()]);
  await Promise.all([driver, admin, superadmin, passenger].map((a) => a.ctx.dispose()));
});
