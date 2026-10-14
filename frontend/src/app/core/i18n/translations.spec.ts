import es from '../../../../public/i18n/es.json';

interface Tree {
  [key: string]: string | Tree;
}

function values(tree: Tree, prefix = ''): [string, string][] {
  return Object.entries(tree).flatMap(([key, value]) =>
    typeof value === 'string' ? [[`${prefix}${key}`, value]] : values(value, `${prefix}${key}.`),
  );
}

describe('Textos de la interfaz', () => {
  it('ningun texto esta vacio', () => {
    const empty = values(es as Tree).filter(([, value]) => value.trim() === '');
    expect(empty).toEqual([]);
  });
});
