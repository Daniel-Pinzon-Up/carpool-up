import AxeBuilder from '@axe-core/playwright';
import { Browser, BrowserContextOptions, Page, TestInfo, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

export type Role = 'passenger' | 'driver' | 'admin' | 'superadmin';

interface Credentials {
  password: string;
  accounts: Record<Role, string>;
}

/** Generado por "python -m app.cli e2e-users"; ignorado por git. */
export function credentials(): Credentials {
  return JSON.parse(
    readFileSync(join(__dirname, '.auth', 'credentials.json'), 'utf-8'),
  ) as Credentials;
}

export const HOME: Record<Role, RegExp> = {
  passenger: /\/buscar$/,
  driver: /\/inicio$/,
  admin: /\/admin$/,
  superadmin: /\/admin$/,
};

/**
 * Contexto con las opciones del proyecto (telefono o escritorio). Se usa desde beforeAll,
 * donde no hay fixture "page": asi una sola sesion sirve para todas las pruebas de un grupo.
 * El servidor rota el token de refresco y cierra la sesion si se reutiliza uno viejo, por eso
 * no se comparte un storageState guardado entre pruebas.
 */
export async function newPage(browser: Browser, info: TestInfo): Promise<Page> {
  const u = info.project.use;
  const options: BrowserContextOptions = {
    baseURL: u.baseURL,
    viewport: u.viewport,
    deviceScaleFactor: u.deviceScaleFactor,
    isMobile: u.isMobile,
    hasTouch: u.hasTouch,
    userAgent: u.userAgent,
    locale: u.locale,
    ignoreHTTPSErrors: u.ignoreHTTPSErrors,
  };
  const context = await browser.newContext(options);
  return context.newPage();
}

/** Evita el onboarding de la primera visita y fija el tema antes de que arranque Angular. */
export async function prepare(page: Page, theme: 'light' | 'dark' = 'light'): Promise<void> {
  await page.addInitScript((value) => {
    localStorage.setItem('cp.onboarded', 'true');
    localStorage.setItem('cp.theme', value);
  }, theme);
  await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' });
}

export async function setTheme(page: Page, theme: 'light' | 'dark'): Promise<void> {
  await page.evaluate((value) => localStorage.setItem('cp.theme', value), theme);
  await page.emulateMedia({ colorScheme: theme, reducedMotion: 'reduce' });
}

/** Inicio de sesion con la pantalla real. */
export async function login(page: Page, role: Role): Promise<void> {
  const { password, accounts } = credentials();
  await page.goto('/ingresar');
  await page.getByLabel('Correo').fill(accounts[role]);
  await page.getByLabel('Contraseña', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page).toHaveURL(HOME[role]);
}

/** Espera a que la pantalla termine de cargar: sin esqueletos ni peticiones pendientes. */
export async function settle(page: Page): Promise<void> {
  await page.waitForLoadState('networkidle');
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
  await expect(page.locator('cp-skeleton')).toHaveCount(0);
}

/** Violaciones graves o criticas de WCAG 2.2 A y AA segun axe. */
export async function seriousViolations(page: Page): Promise<string[]> {
  const result = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
    // Los mapas los dibuja MapLibre en un canvas: axe no puede medir su contraste.
    .exclude('.maplibregl-map')
    .analyze();
  return result.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map(
      (v) =>
        `${v.id} (${v.impact}): ${v.help}\n` +
        v.nodes
          .slice(0, 5)
          .map(
            (n) => `    ${n.target.join(' ')} | ${n.failureSummary?.split('\n')[1]?.trim() ?? ''}`,
          )
          .join('\n'),
    );
}
