"""Recorta un extracto de OpenStreetMap a una caja, conservando las vias completas.

Uso: python clip.py entrada.osm.pbf salida.osm.pbf min_lon min_lat max_lon max_lat

Se guardan las vias de transito (highway) con al menos un nodo dentro de la caja y todos
sus nodos (BackReferenceWriter), mas las restricciones de giro entre esas vias. Asi OSRM
recibe un grafo pequeno pero completo.
"""

import sys

import osmium


def main() -> None:
    source, target, *box = sys.argv[1:]
    min_lon, min_lat, max_lon, max_lat = map(float, box)

    def inside(lon: float, lat: float) -> bool:
        return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat

    kept_ways: set[int] = set()
    with osmium.BackReferenceWriter(target, ref_src=source, overwrite=True) as writer:
        # Se leen tambien los nodos para que la cache de ubicaciones resuelva cada via.
        processor = osmium.FileProcessor(source, osmium.osm.NODE | osmium.osm.WAY).with_locations()
        for way in processor:
            if not way.is_way() or "highway" not in way.tags:
                continue
            if any(node.location.valid() and inside(node.lon, node.lat) for node in way.nodes):
                writer.add_way(way)
                kept_ways.add(way.id)

        for relation in osmium.FileProcessor(source, osmium.osm.RELATION):
            if relation.tags.get("type") != "restriction":
                continue
            ways = [m.ref for m in relation.members if m.type == "w"]
            if ways and all(ref in kept_ways for ref in ways):
                writer.add_relation(relation)

    print(f"vias conservadas: {len(kept_ways)}")


if __name__ == "__main__":
    main()
