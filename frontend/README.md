# Iter Animi — Frontend

Interfaz web del simulador de casos de psicología social. React 19 + TypeScript + Vite, con React Router y TanStack Query.
Consume la API real del backend (`backend/`, FastAPI, prefijo `/api/v1`); no hay datos simulados.

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
npm run build        # build de producción en dist/
npm run preview      # sirve dist/ localmente (con el mismo proxy)
npm run check        # tipos + lint + pruebas + build
```

## Variables de entorno

Copie `.env.example` como `.env.local`. Ninguna es secreta: todo lo que empieza por `VITE_` queda en el JavaScript público.

| Variable | Uso | Por defecto |
|---|---|---|
| `VITE_API_BASE_URL` | URL base de la API **incluyendo** `/api/v1`. Se fija al compilar. | `/api/v1` (mismo origen) |
| `VITE_DEV_API_TARGET` | Solo `dev`/`preview`: a dónde reenvía Vite las peticiones `/api`. | `http://127.0.0.1:8000` |

El código de producción no contiene ninguna dirección `localhost`: si `VITE_API_BASE_URL` no se define, usa rutas relativas.

## Despliegue

El build (`npm run build`) genera una SPA estática en `dist/`. Hay dos formas de conectarla con la API:

**A. Mismo origen (recomendada, sin CORS).** Un servidor web sirve `dist/` y reenvía `/api/` al backend.
`deploy/nginx.conf` es un ejemplo listo para usar. Compile sin `VITE_API_BASE_URL`.

**B. Orígenes distintos.** Compile con `VITE_API_BASE_URL=https://api.ejemplo.edu.co/api/v1` y, en el backend, defina
`CORS_ALLOWED_ORIGINS=https://simulador.ejemplo.edu.co` (lista separada por comas; nunca `*`). La autenticación viaja en la
cabecera `Authorization` (no hay cookies), por eso el backend no habilita credenciales en CORS.

**Rutas internas de la SPA.** Abrir o refrescar `/sesiones/...` debe devolver `index.html`:

- Nginx: `try_files $uri $uri/ /index.html;` (incluido en `deploy/nginx.conf`).
- Netlify / Cloudflare Pages: `public/_redirects` ya se copia a `dist/`.
- Otros: configure la “reescritura de SPA” equivalente.

Además, en el backend conviene fijar `SIMULATOR_ACCESS_URL` con la URL pública del frontend (la usan los correos de
convocatoria) y `ENVIRONMENT=production`.

## Estructura

```text
src/
├── api/          client.ts (fetch único, errores, token), endpoints.ts (rutas reales), types.ts (esquemas del OpenAPI)
├── auth/         sesión (3 tipos de token), contexto, guardas de ruta por zona
├── components/   AppShell, estados (carga/vacío/error/denegado), diálogos, estado con círculo, silueta de escena
├── features/
│   ├── login/    acceso único (contraseña o código)
│   ├── teacher/  inicio, aulas, asignar caso, sesión (convocados/resultados/seguimiento), evaluación, casos
│   ├── admin/    usuarios y aulas
│   ├── student/  inicio del estudiante, simulador (novela visual), cierre del intento
│   └── results/  resultados y retroalimentación del estudiante
├── lib/          formato (es-CO), etiquetas, reglas de presentación
└── styles.css    sistema visual completo (tokens, componentes, simulador)
```

## Cómo se corresponde con el backend

| En la interfaz | En la API |
|---|---|
| Aula | Espacio académico (`/academic-spaces`). Lo crea la administración; es compartido entre docentes. |
| Asignar un caso a un aula | Programar una sesión (`POST /sessions`) con caso publicado, ventana, tiempo y convocados por correo. |
| Abrir / finalizar sesión | `POST /sessions/{id}/start` · `/finish` |
| Código de acceso | Código de convocatoria (`GET …/convocations/{cid}/code`). |
| Iniciar / continuar caso | `POST /student/sessions/{id}/participations` (201 crea, 200 recupera el intento en curso). |
| Confirmar respuesta | `PUT /student/participations/{id}/answers/{pregunta}` |
| Entregar caso | `POST /student/participations/{id}/finish` |
| Evaluar intentos | `POST /sessions/{id}/evaluations/process` |
| Ver resultado (estudiante) | `POST /auth/student/results-login` + `GET /student/results/{id}` (solo con la sesión finalizada). |

Roles y acceso:

- **Docente / administración**: correo + contraseña (`/auth/login`); el rol lo da `/auth/me`.
- **Estudiante**: correo + código (`/auth/student/login`). Si el servidor responde que la sesión ya no admite ingresos (403),
  la interfaz prueba el mismo código en `/auth/student/results-login`: si la sesión está finalizada entra a sus resultados;
  si no, muestra el motivo original del servidor.
- Las guardas de ruta solo ordenan la navegación; los permisos los aplica siempre el backend.

## Limitaciones que impone el backend

- **El estudiante no tiene “Mis aulas”.** No tiene contraseña ni cuenta navegable: su token cubre **una** convocatoria y su
  sesión. Por eso su inicio muestra esa sesión (caso, ventana, intentos) y no un listado de aulas. Tampoco existe un endpoint
  que le devuelva el nombre del aula.
- **Resultados solo con la sesión finalizada.** Mientras la sesión sigue en curso, el estudiante ve el estado de su intento,
  no la nota; después debe volver a ingresar con el mismo código (token de solo lectura, 60 min por defecto).
- **Edición de casos por CaseDSL.** La interfaz importa, valida, publica, archiva, elimina borradores, exporta y edita la
  información general. El backend también permite editar escenarios, preguntas, opciones y rúbrica pieza a pieza; esa
  edición granular no tiene pantalla todavía (se hace exportando, editando el JSON e importando un borrador nuevo).
- **Nota consolidada entre intentos:** el backend no la define; se muestra cada intento por separado.
- **Correos:** si `NOTIFICATIONS_EMAIL_ENABLED=false`, los códigos no se envían; el docente los entrega con «Ver código».
- No hay personajes ni nombres de interlocutor en el contenido del caso: la escena usa una silueta genérica
  (`components/SceneCharacter.tsx`, reemplazable por un sprite).

## Recorrido para la sustentación

Con el backend y el frontend en marcha (`npm run dev`) y la base migrada:

1. **Administración.** Cree el administrador inicial (`python -m app.scripts.create_admin …`, ver README raíz) e ingrese con
   contraseña. En **Usuarios**: cree un docente, pulse «Permitir crear casos» y cree un estudiante. En **Aulas**: cree un aula.
2. **Docente: caso.** Ingrese como docente. **Mis casos → Importar caso**: cargue
   `docs/ejemplos/caso_conformidad_grupal.casedsl.json` (tomado de la colección Postman del proyecto), **Validar** y **Publicar**.
3. **Docente: asignar.** **Mis aulas → Asignar caso**: elija el caso, deje el inicio en la hora actual, un tiempo (p. ej. 20 min)
   y el correo del estudiante. **Crear sesión** → **Abrir sesión** → en **Convocados**, «Ver código».
4. **Estudiante.** Cierre sesión, elija «Con código de acceso», ingrese correo y código. **Iniciar caso** → lea el prólogo →
   elija una opción y **Confirmar respuesta** en cada decisión → **Entregar caso**. Puede recargar a mitad del caso para mostrar
   que se retoma donde quedó.
5. **Docente: cierre.** En la sesión: **Finalizar sesión** → pestaña **Resultados** → **Evaluar intentos cerrados** →
   **Ver detalle** → escriba un comentario. La pestaña **Seguimiento** muestra los indicadores y permite descargar CSV.
6. **Estudiante: resultado.** Ingrese de nuevo con el mismo correo y código: la interfaz abre **Mis resultados** con la nota,
   el desglose por criterio, la retroalimentación por decisión y el comentario del docente.

## Pruebas incluidas

`src/test/units.test.ts` (orden de escenas, reanudación, avance, mensajes de error, fechas con zona, reglas de navegación) y
`src/test/flows.test.tsx` (validación del acceso, paso automático a resultados con sesión finalizada, motivo del servidor,
simulador: sin doble envío, selección conservada ante error y avance solo tras la confirmación del servidor).
