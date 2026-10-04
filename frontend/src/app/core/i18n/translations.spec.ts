import en from '../../../../public/i18n/en.json';
import es from '../../../../public/i18n/es.json';
import fr from '../../../../public/i18n/fr.json';
import pt from '../../../../public/i18n/pt.json';

interface Tree {
  [key: string]: string | Tree;
}

function flatten(tree: Tree, prefix = ''): string[] {
  return Object.entries(tree).flatMap(([key, value]) =>
    typeof value === 'string' ? [`${prefix}${key}`] : flatten(value, `${prefix}${key}.`),
  );
}

describe('Traducciones', () => {
  const base = flatten(es).sort();

  it.each([
    ['en', en],
    ['pt', pt],
    ['fr', fr],
  ])('%s tiene exactamente las mismas claves que es', (_, translation) => {
    expect(flatten(translation as Tree).sort()).toEqual(base);
  });

  it('ningun texto esta vacio', () => {
    for (const translation of [es, en, pt, fr]) {
      const empty = flatten(translation as Tree).filter((key) => {
        const value = key
          .split('.')
          .reduce<unknown>((node, part) => (node as Tree)[part], translation);
        return typeof value === 'string' && value.trim() === '';
      });
      expect(empty).toEqual([]);
    }
  });
});
