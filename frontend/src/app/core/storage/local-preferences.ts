/** Acceso a localStorage tolerante a fallos (modo privado, cookies bloqueadas). */
export function readPref(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writePref(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Sin almacenamiento la preferencia dura solo esta sesion.
  }
}
