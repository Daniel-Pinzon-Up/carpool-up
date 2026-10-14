import { Page, expect, test } from '@playwright/test';
import { Role, login, newPage, prepare, seriousViolations, settle } from './support';

/**
 * Accesibilidad (paso 13): axe sin violaciones graves ni criticas de WCAG 2.2 AA en las
 * pantallas principales de cada rol. El proyecto "mobile" repite todo con el ancho de un
 * telefono.
 */
const PUBLIC = ['/bienvenida', '/ingresar', '/registro', '/recuperar', '/ayuda', '/legal/terminos'];
const BY_ROLE: Record<Role, string[]> = {
  passenger: ['/buscar', '/mis-viajes', '/mensajes', '/notificaciones', '/perfil', '/ayuda'],
  driver: ['/inicio', '/vehiculos', '/mis-viajes', '/solicitudes', '/estadisticas'],
  admin: [
    '/admin',
    '/admin/aprobaciones',
    '/admin/usuarios',
    '/admin/viajes',
    '/admin/emergencias',
    '/admin/moderacion',
  ],
  superadmin: ['/admin/configuracion'],
};
/**
 * Navega dentro de la app, sin recargar (como al tocar un enlace): una recarga completa
 * renovaria la sesion en cada pantalla.
 */
async function audit(page: Page, path: string): Promise<void> {
  await page.evaluate((target) => {
    history.pushState({}, '', target);
    dispatchEvent(new PopStateEvent('popstate'));
  }, path);
  await page.waitForURL((url) => url.pathname === path);
  await settle(page);
  // Si la sesion se perdiera, la app redirigiria y axe revisaria otra pantalla.
  expect(new URL(page.url()).pathname).toBe(path);
  expect(await seriousViolations(page)).toEqual([]);
}

test.describe('Pantallas publicas', () => {
  for (const path of PUBLIC) {
    test(path, async ({ page }) => {
      await prepare(page);
      if (path === '/bienvenida') {
        await page.addInitScript(() => localStorage.removeItem('cp.onboarded'));
      }
      await page.goto(path);
      await settle(page);
      expect(new URL(page.url()).pathname).toBe(path);
      expect(await seriousViolations(page)).toEqual([]);
    });
  }
});

for (const [role, paths] of Object.entries(BY_ROLE) as [Role, string[]][]) {
  test.describe(`Rol ${role}`, () => {
    test.describe.configure({ mode: 'serial' });
    let page: Page;

    test.beforeAll(async ({ browser }, info) => {
      page = await newPage(browser, info);
      await prepare(page);
      await login(page, role);
    });

    test.afterAll(async () => {
      await page.context().close();
    });

    for (const path of paths) {
      test(path, async () => {
        await audit(page, path);
      });
    }
  });
}
