import { expect, test } from '@playwright/test';
import { login, prepare } from './support';

/**
 * Criterio de aceptacion del paso 13: idioma, tema y transparencia cambian sin recargar la
 * pagina. Una marca en window sobrevive solo si no hubo recarga.
 */
type Marked = Window & { marker?: string };

test.describe('Preferencias sin recargar', () => {
  test('cambiar el idioma traduce la pantalla al instante', async ({ page }) => {
    await prepare(page);
    await page.goto('/ingresar');
    await page.evaluate(() => ((window as Marked).marker = 'sin-recarga'));
    const title = page.getByRole('heading', { level: 1 });
    await expect(title).toHaveText('Iniciar sesión');

    for (const [lang, text] of [
      ['en', 'Sign in'],
      ['pt', 'Entrar'],
      ['fr', 'Connexion'],
      ['es', 'Iniciar sesión'],
    ]) {
      await page.getByRole('combobox').selectOption(lang);
      await expect(page.locator('html')).toHaveAttribute('lang', lang);
      await expect(title).toHaveText(text);
    }
    expect(await page.evaluate(() => (window as Marked).marker)).toBe('sin-recarga');
  });

  test('cambiar el tema se aplica al instante', async ({ page }) => {
    await prepare(page, 'light');
    await page.goto('/ingresar');
    await page.evaluate(() => ((window as Marked).marker = 'sin-recarga'));
    const html = page.locator('html');
    const toggle = page.getByRole('button', { name: /^Tema:/ });
    const background = () => page.evaluate(() => getComputedStyle(document.body).backgroundColor);

    // Orden del boton: claro -> oscuro -> sistema (el sistema emulado es claro).
    await expect(toggle).toHaveAccessibleName('Tema: Claro');
    const light = await background();
    await toggle.click();
    await expect(html).toHaveClass(/\bdark\b/);
    await expect.poll(background).not.toBe(light);
    await toggle.click();
    await expect(html).not.toHaveClass(/\bdark\b/);
    await expect.poll(background).toBe(light);

    expect(await page.evaluate(() => (window as Marked).marker)).toBe('sin-recarga');
  });

  test('el perfil cambia idioma y transparencia sin recargar', async ({ page }) => {
    await prepare(page, 'light');
    await login(page, 'passenger');
    await page.getByRole('link', { name: 'Perfil' }).first().click();
    await expect(page).toHaveURL(/\/perfil$/);
    await page.evaluate(() => ((window as Marked).marker = 'sin-recarga'));
    const html = page.locator('html');

    await page.getByLabel('Reducir transparencia').check();
    await expect(html).toHaveClass(/reduce-transparency/);
    await page.getByLabel('Reducir transparencia').uncheck();
    await expect(html).not.toHaveClass(/reduce-transparency/);

    await page.getByRole('combobox', { name: 'Idioma' }).first().selectOption('en');
    await expect(page.getByRole('heading', { name: 'Preferences' })).toBeVisible();
    await page.getByRole('combobox', { name: 'Language' }).first().selectOption('es');
    await expect(page.getByRole('heading', { name: 'Preferencias' })).toBeVisible();

    expect(await page.evaluate(() => (window as Marked).marker)).toBe('sin-recarga');
  });
});
