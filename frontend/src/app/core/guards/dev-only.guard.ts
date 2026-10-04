import { isDevMode } from '@angular/core';
import { CanMatchFn } from '@angular/router';

/** El catalogo de componentes solo existe en desarrollo. */
export const devOnlyGuard: CanMatchFn = () => isDevMode();
