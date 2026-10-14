# Documentación de Carpool UP

## Estructura

```
docs/
├── README.md                 este índice
├── DESPLIEGUE.md             arrancar desde cero, producción, certificados, correo real, respaldos y actualización
├── GUIA_ADMINISTRACION.md    uso del panel: aprobaciones, usuarios, sanciones, emergencias, moderación y parámetros
├── API.md                    endpoints, códigos de error, límites de peticiones y autorización por rol
├── CASOS_DE_USO.md           20 recorridos completos de prueba manual con datos y resultados esperados
├── COMO_FUNCIONA.md          paso a paso por dentro: códigos por correo, idioma, tema, tiempo real y más
├── DECISIONES.md             cada decisión técnica del proyecto, paso por paso, con su motivo
├── DIAGRAMA_ER.md            modelo de datos: 35 tablas, relaciones y todas las columnas (Mermaid)
├── diagrama-er/              el diagrama general y las 5 vistas por módulo en PNG
└── mockups/                  bosquejos de todas las pantallas → mockups/README.md
    ├── mockups.html · mockups-pc.html   fuentes editables (celular y PC)
    ├── png/ · png-pc/                   una imagen por pantalla
    └── *.pdf                            los dos juegos en PDF
```

## ¿Qué leer según lo que necesitas?

| Necesito… | Documento |
|-----------|-----------|
| Entender el proyecto y levantarlo | [README raíz](../README.md) |
| Ponerlo en un servidor | [DESPLIEGUE.md](DESPLIEGUE.md) |
| Administrar la plataforma | [GUIA_ADMINISTRACION.md](GUIA_ADMINISTRACION.md) |
| Llamar a la API | [API.md](API.md) y `/api/v1/docs` con la app levantada |
| Probar a mano de punta a punta | [CASOS_DE_USO.md](CASOS_DE_USO.md) |
| Explicar cómo funciona una parte | [COMO_FUNCIONA.md](COMO_FUNCIONA.md) |
| Saber por qué se hizo algo de cierta forma | [DECISIONES.md](DECISIONES.md) |
| Ver las tablas y sus relaciones | [DIAGRAMA_ER.md](DIAGRAMA_ER.md) y las imágenes de `diagrama-er/` |
| Ver las pantallas | [mockups/README.md](mockups/README.md) |

Cada carpeta del código tiene además su README: [backend](../backend/README.md), [frontend](../frontend/README.md) e [infraestructura](../infra/README.md).
