// Genera src/app/shared/icons/lucide.ts con SOLO los iconos de Lucide que usa la app.
//
// El paquete @lucide/angular define cada icono como un componente con campos estaticos que
// el empaquetador no puede descartar, asi que los ~1.600 iconos terminaban en la carga inicial
// (unos 435 kB). Aqui se copian los dibujos de los iconos usados a directivas propias.
//
// Uso: npm run icons   (despues de usar un icono nuevo: importalo desde '@icons')
import { readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const src = join(root, 'src');
const target = join(src, 'app/shared/icons/lucide.ts');
const API = new Set(['LucideIcon', 'LucideIconData', 'LucideDynamicIcon', 'LucideIconBase']);

function* files(dir) {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) yield* files(path);
    else if (path.endsWith('.ts') && path !== target) yield path;
  }
}

// Nombres importados desde '@icons' (o desde el paquete, antes de migrar) en todo src.
const used = new Set();
const importPattern = /import\s*\{([^}]*)\}\s*from\s*'(?:@icons|@lucide\/angular)'/g;
for (const file of files(src)) {
  for (const match of readFileSync(file, 'utf-8').matchAll(importPattern)) {
    for (const raw of match[1].split(',')) {
      const name = raw.trim().replace(/^type\s+/, '');
      if (/^Lucide[A-Z]\w*$/.test(name) && !API.has(name)) used.add(name);
    }
  }
}

await import('@angular/compiler'); // el paquete esta compilado parcialmente
const lucide = await import('@lucide/angular');
const names = [...used].sort();
const missing = names.filter((name) => !lucide[name]?.icon);
if (missing.length) {
  console.error(`Iconos que no existen en Lucide: ${missing.join(', ')}`);
  process.exit(1);
}

const selector = (name) => `svg[lucide${name.slice('Lucide'.length)}]`;
const blocks = names.map((name) => {
  const { name: slug, node } = lucide[name].icon;
  const clean = node.map(([tag, attrs]) => {
    const { key: _key, ...rest } = attrs;
    return [tag, rest];
  });
  return [
    `@Directive({ selector: '${selector(name)}' })`,
    `export class ${name} extends LucideIconBase {`,
    `  static readonly icon: LucideIconData = { name: '${slug}', node: ${JSON.stringify(clean)} };`,
    `}`,
  ].join('\n');
});

const header = `// GENERADO por scripts/generate-icons.mjs (npm run icons). No editar a mano.
// ${names.length} iconos de Lucide (ISC) usados por la app.
import { Directive } from '@angular/core';
import { LucideIconBase, LucideIconData } from './icon-base';

export { LucideDynamicIcon } from './icon-base';
export type { LucideIcon, LucideIconData } from './icon-base';
`;
writeFileSync(target, `${header}\n${blocks.join('\n\n')}\n`, 'utf-8');
console.log(`${names.length} iconos -> ${relative(root, target)}`);
