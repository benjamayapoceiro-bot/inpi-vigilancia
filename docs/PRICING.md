# Planes — mapeo a flags existentes (sin pasarela todavía)

| Plan | `limite_marcas` | `puede_conectar_inpi` | `puede_presentar` | `puede_ver_alertas` | `max_usuarios` | Notas |
|---|---|---|---|---|---|---|
| Demo | 1 | false | false | true | 1 | auto-servicio, sin INPI en vivo |
| Básico | 5 | false | false | true | 2 | solo monitoreo |
| Pro | 20 | true | true | true | 5 | todo INPI |
| Premium | 9999 | true | true | true | 99 | sin límites (admin) |

- El admin edita todo desde Admin → Estudios (límite, checks, plan).
- `demo-signup` crea Demo; el admin lo sube de plan a mano.
- Pasarela de pagos: pendiente, no bloquea nada de arriba.
