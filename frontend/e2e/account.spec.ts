import { APIRequestContext, expect, request, test } from '@playwright/test';
import { randomBytes } from 'node:crypto';
import { credentials, prepare } from './support';

/**
 * Ciclo de vida de una cuenta, de punta a punta: registro en cuatro pasos con documento, codigo
 * por correo (leido en Mailpit), aprobacion del administrador y eliminacion desde el perfil
 * (Ley 1581). Usa una cuenta desechable nueva en cada corrida.
 */
const MAILPIT = process.env['E2E_MAILPIT_URL'] ?? 'http://localhost:8025';
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  'base64',
);

async function codeFor(mail: APIRequestContext, email: string): Promise<string> {
  for (let attempt = 0; attempt < 20; attempt++) {
    const search = await mail.get(`${MAILPIT}/api/v1/search`, {
      params: { query: `to:"${email}"` },
    });
    const found = (await search.json()).messages as { ID: string }[];
    if (found.length) {
      const message = await (await mail.get(`${MAILPIT}/api/v1/message/${found[0].ID}`)).json();
      const code = /\b(\d{6})\b/.exec(message.Text as string)?.[1];
      if (code) return code;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`No llego el codigo a ${email}`);
}

test('registro, verificacion, aprobacion y eliminacion de la cuenta', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop', 'corre una vez, en escritorio');
  test.setTimeout(120_000);
  const stamp = Date.now();
  const email = `e2e.registro.${stamp}@unipamplona.edu.co`;
  const password = randomBytes(18).toString('base64url');

  // --- Registro en cuatro pasos ----------------------------------------------------------
  await prepare(page);
  await page.goto('/registro');
  await page.getByRole('textbox', { name: 'Nombre completo' }).fill('Valentina Registro Prueba');
  await page.getByRole('textbox', { name: 'Correo institucional' }).fill(email);
  await page.getByRole('textbox', { name: 'Contraseña', exact: true }).fill(password);
  await page.getByRole('textbox', { name: 'Repite la contraseña' }).fill(password);
  await page.getByRole('combobox', { name: 'Sexo' }).selectOption({ label: 'Mujer' });
  await page.getByRole('button', { name: 'Continuar' }).click();
  await page.getByText('Pasajero', { exact: true }).click();
  await page.getByRole('button', { name: 'Continuar' }).click();
  await page.getByText('Carnet estudiantil', { exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: 'carnet.png',
    mimeType: 'image/png',
    buffer: PNG,
  });
  await page.getByRole('button', { name: 'Continuar' }).click();
  await page.getByRole('checkbox').nth(0).check();
  await page.getByRole('checkbox').nth(1).check();
  await page.getByRole('button', { name: 'Crear cuenta' }).click();

  // --- Codigo por correo -------------------------------------------------------------------
  await expect(page).toHaveURL(/\/verificar$/);
  const mail = await request.newContext();
  await page.getByRole('textbox', { name: 'Código de 6 números' }).fill(await codeFor(mail, email));
  await page.getByRole('button', { name: 'Verificar' }).click();
  await expect(page).toHaveURL(/\/cuenta\/estado$/);

  // --- El administrador aprueba el carnet ---------------------------------------------------
  const { accounts, password: adminPassword } = credentials();
  const api = await request.newContext({
    baseURL: info.project.use.baseURL,
    ignoreHTTPSErrors: true,
  });
  const login = await api.post('/api/v1/auth/login', {
    data: { email: accounts.admin, password: adminPassword },
  });
  const headers = { Authorization: `Bearer ${(await login.json()).access_token}` };
  const users = await (
    await api.get('/api/v1/admin/users', { headers, params: { q: email } })
  ).json();
  const userId = users.items[0].id as string;
  const queue = await (
    await api.get('/api/v1/admin/approvals', { headers, params: { type: 'identity', limit: 50 } })
  ).json();
  const item = (queue.items as { id: string; applicant: { id: string } }[]).find(
    (i) => i.applicant.id === userId,
  );
  expect(item, 'el carnet nuevo esta en la cola de aprobaciones').toBeTruthy();
  const approved = await api.post(`/api/v1/admin/approvals/${item!.id}/approve`, {
    headers,
    data: {},
  });
  expect(approved.ok(), await approved.text()).toBe(true);

  // --- Ya activa: elimina su cuenta desde el perfil -----------------------------------------
  await page.goto('/perfil');
  await page.getByRole('button', { name: 'Eliminar cuenta' }).click();
  const dialog = page.getByRole('dialog');
  const confirm = dialog.getByRole('button', { name: 'Eliminar definitivamente' });
  await expect(confirm).toBeDisabled();
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('textbox', { name: 'Contraseña' }).fill(password);
  await confirm.click();
  await expect(page.getByText('Tu cuenta fue eliminada.')).toBeVisible();
  await expect(page).toHaveURL(/\/ingresar$/);

  // Con la cuenta borrada ya no se puede entrar.
  const again = await api.post('/api/v1/auth/login', { data: { email, password } });
  expect(again.status()).toBe(401);
  const gone = await (
    await api.get('/api/v1/admin/users', { headers, params: { q: email } })
  ).json();
  expect(gone.items).toHaveLength(0);

  await Promise.all([api.dispose(), mail.dispose()]);
});
