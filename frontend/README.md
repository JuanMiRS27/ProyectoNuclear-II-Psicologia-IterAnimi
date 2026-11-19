# Iter Animi — Frontend

Interfaz web del simulador de casos de psicología social. React 19 + TypeScript + Vite, React Router y TanStack Query.
Consume la API real del backend (`backend/`, FastAPI, prefijo `/api/v1`); no hay datos simulados.

- Matriz de requisitos (CU1–CU36 del plan PT-DCP-01): [`docs/MATRIZ_REQUISITOS.md`](docs/MATRIZ_REQUISITOS.md)
- Estructura tomada de Ágora y qué cambió: [`docs/AGORA_A_ITER_ANIMI.md`](docs/AGORA_A_ITER_ANIMI.md)
- Capturas de verificación (cuentas de prueba, sin contraseñas ni códigos): [`docs/capturas/`](docs/capturas)

## Requisitos

- Node.js 20 o superior (probado con Node 26 y npm 11).
- El backend en marcha (ver `README.md` de la raíz: PostgreSQL, `.env`, `alembic upgrade head`, `uvicorn`).

## Comandos

Desde `frontend/`:

```bash
npm install          # dependencias
npm run dev          # desarrollo en http://localhost:5173 (proxy /api → backend)
npm run typecheck    # chequeo de tipos
npm run lint         # oxlint
npm run test         # pruebas (Vitest + Testing Library)
npm run build        # build de producción en dist/ (cada portal en su propio fragmento)
npm run preview      # sirve dist/ localmente (con el mismo proxy)
npm run check        # tipos + lint + pruebas + build
```

## Variables de entorno

Copie `.env.example` como `.env.local`. Ninguna es secreta: todo lo que empieza por `VITE_` queda en el JavaScript público.

| Variable | Uso | Por defecto |
|---|---|---|
| `VITE_API_BASE_URL` | URL base de la API **incluyendo** `/api/v1`. Se fija al compilar. | `/api/v1` (mismo origen) |
| `VITE_DEV_API_TARGET` | Solo `dev`/`preview`: a dónde reenvía Vite las peticiones `/api`. | `http://127.0.0.1:8000` |

El código de producción no contiene direcciones `localhost` de la API: sin `VITE_API_BASE_URL` usa rutas relativas.
Cada petición tiene un tiempo límite de 20 s: si la API no responde, la interfaz lo explica en lugar de quedarse esperando.

## Despliegue

`npm run build` genera una SPA estática en `dist/`. Dos formas de conectarla con la API:

**A. Mismo origen (recomendada, sin CORS).** Un servidor web sirve `dist/` y reenvía `/api/` al backend.
`deploy/nginx.conf` es un ejemplo listo para usar. Compile sin `VITE_API_BASE_URL`.

**B. Orígenes distintos.** Compile con `VITE_API_BASE_URL=https://api.ejemplo.edu.co/api/v1` y, en el backend, defina
`CORS_ALLOWED_ORIGINS=https://simulador.ejemplo.edu.co` (orígenes separados por comas; nunca `*`). La autenticación viaja en la
cabecera `Authorization` (sin cookies), por eso el backend no habilita credenciales en CORS.

**Rutas internas.** Abrir o refrescar `/docente/sesiones/...` debe devolver `index.html`:

- Nginx: `try_files $uri $uri/ /index.html;` (incluido en `deploy/nginx.conf`).
- Netlify / Cloudflare Pages: `public/_redirects` ya se copia a `dist/`.

En el backend conviene fijar `SIMULATOR_ACCESS_URL` con la URL pública del frontend (la usan los correos de convocatoria) y
`ENVIRONMENT=production`. Los avisos internos y los correos los genera el worker de notificaciones
(`python -m app.workers.notifications --intervalo 30`); sin él, la sección Avisos queda vacía.

## Estructura (equivalente a la de Ágora)

```text
src/
├── app/                 router.tsx y routes/{auth,student,teacher,admin}.tsx (grupos (auth) y (platform)); vistas con carga diferida
├── layouts/             AuthLayout, PlatformLayout (guarda + barra lateral agrupada + menú móvil), SimulatorLayout (guarda, sin barra)
├── providers/           AppProviders (TanStack Query) y SessionProvider (arranque de sesión, expiración, limpieza al cambiar de identidad)
├── modules/
│   ├── auth/            acceso único y Mi cuenta (cambio de contraseña)
│   ├── student/         inicio, mi aula, mi sesión, resultados, retroalimentación, avisos
│   ├── academic/        aulas del docente, detalle del aula, programar sesión, agenda
│   ├── teacher/         panel docente, sesiones, detalle de sesión (convocados, resultados, seguimiento), cola de evaluación
│   ├── cases/           listado, creación (en blanco o CaseDSL), detalle y editor (escenas, decisiones, opciones, rúbrica)
│   ├── evaluation/      desglose de resultado, evaluación del intento y comentario del docente
│   ├── simulator/       vista de juego + escenario, panel narrativo, decisiones, acciones, revisión y cierre
│   └── admin/           inicio, usuarios, aulas y entregas de correo
├── components/ui/       Button, campos, Dialog, Tabs, Icon (iconos propios)
├── components/design-system/  Page, PageHeader, Section, DataTable, estados (carga, vacío, error, sin acceso), Status
├── services/            http-client.ts y un servicio por dominio (auth, user, space, case, session, evaluation, report, student, notification, delivery)
├── hooks/               consultas y mutaciones por dominio (use-academic, use-cases, use-student, use-admin), use-session, use-countdown
├── lib/                 navigation.ts, query-keys.ts, query-invalidation.ts, student-session-adapters.ts, formato, etiquetas, reglas de presentación
└── types/api.ts         DTO de la API (tomados del OpenAPI)
```

Regla de capas: **ruta → vista del módulo → hook (consulta o mutación) → servicio de dominio → cliente HTTP**. Ningún
componente visual hace peticiones. La caché se invalida por efecto de negocio (crear sesión, convocar, evaluar, comentar) y
solo se vacía entera al cambiar de identidad.

## Rutas por rol

| Portal | Rutas |
|---|---|
| Acceso | `/ingresar` |
| Estudiante | `/estudiante`, `/estudiante/aula`, `/estudiante/sesion`, `/estudiante/resultados[/:id]`, `/estudiante/retroalimentacion`, `/estudiante/avisos`, `/estudiante/caso/:id` (simulador), `/estudiante/caso/:id/cierre` |
| Docente | `/docente`, `/docente/aulas[/:id[/programar]]`, `/docente/sesiones[/:id[/intentos/:pid]]`, `/docente/casos[/nuevo|/:id]`, `/docente/evaluacion`, `/docente/cuenta` |
| Administración | `/admin`, `/admin/usuarios`, `/admin/aulas`, `/admin/entregas`, `/admin/cuenta` |

El destino inicial lo decide el tipo de token y el rol que devuelve el servidor (`lib/navigation.ts`). Las guardas solo
ordenan la navegación; los permisos los aplica la API.

## Limitaciones que impone el backend

- **El estudiante ve una convocatoria.** No tiene contraseña: entra con correo + código y su token cubre una sola
  convocatoria y su sesión (decisión mantenida a propósito; ver la matriz). «Mi aula» es el aula de esa sesión, no una
  matrícula, que el backend no registra.
- **Resultados solo con la sesión finalizada.** Con la sesión en curso, Resultados y Retroalimentación explican cuándo
  estarán disponibles; después, el mismo código abre un acceso de solo lectura.
- **Nota consolidada entre intentos:** el backend no la define; cada intento se muestra por separado.
- **Correos:** con `NOTIFICATIONS_EMAIL_ENABLED=false` no se envían; el docente entrega el código con «Ver código».

## Guion breve de sustentación (unos 10 minutos)

Con PostgreSQL, el backend (`uvicorn`) y el frontend (`npm run dev`) en marcha y la base migrada:

1. **Administración** (`create_admin` del README raíz). Inicio: conteos reales. **Usuarios**: crear un docente y «Permitir
   crear casos»; crear dos estudiantes. **Aulas**: crear un aula. Mostrar que la administración no ve casos ni sesiones.
2. **Docente — casos.** **Casos → Nuevo caso → Importar CaseDSL** con `docs/ejemplos/caso_conformidad_grupal.casedsl.json`,
   **Validar**, **Publicar**. Opcional: «Empezar en blanco» para enseñar el editor (escena, decisión, opciones, rúbrica) y
   cómo la validación del servidor señala lo que falta.
3. **Docente — sesión.** **Aulas → (aula) → Programar sesión**: caso, inicio ahora, 20–30 min, los dos correos. **Abrir
   sesión** → **Convocados → Ver código**.
4. **Estudiante 1** («Con código de acceso»). El inicio destaca la sesión y la agenda. **Iniciar caso** → prólogo → elegir y
   **Confirmar respuesta** → «Volver al inicio» a mitad del caso → **Continuar caso** (se retoma en la misma decisión) →
   **Entregar caso**.
5. **Privacidad y roles.** Con la cuenta del estudiante, escribir `/docente` en la barra: «No tienes acceso». El estudiante 2
   no puede ver el intento del estudiante 1 (la API responde 404).
6. **Docente — evaluación.** Sesión → **Resultados → Evaluar intentos cerrados** → **Ver detalle** → escribir el comentario →
   **Finalizar sesión**. **Seguimiento**: indicadores y CSV.
7. **Estudiante 1 de nuevo** con el mismo código: entra a su portal en modo resultados → **Resultados** (nota, desglose) y
   **Retroalimentación** (comentario del docente, distinto del resumen automático).

## Pruebas incluidas

`src/test/units.test.ts`: orden de escenas, reanudación, avance, mensajes de error, fechas con zona, navegación por rol.
`src/test/flows.test.tsx`: validación del acceso, paso automático a resultados con la sesión finalizada, motivo del servidor,
simulador (sin doble envío, selección conservada ante error, avance solo tras la confirmación), guardas por rol, y
Resultados (sin petición con la sesión en curso; evaluados frente a en revisión).
