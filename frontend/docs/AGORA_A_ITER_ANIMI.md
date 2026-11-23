# De Ágora a Iter Animi

Ágora (Next.js) se usó como referencia de **estructura, navegación y lógica de interfaz**. No se copiaron su stack, endpoints,
DTO, permisos, reglas de evaluación, dependencias, activos, modelos Live2D/Rive ni branding.

## Estructura replicada

| En Ágora | En Iter Animi | Notas |
|---|---|---|
| Grupos `app/(auth)` y `app/(platform)` | `src/app/routes/{auth,student,teacher,admin}.tsx` + `app/router.tsx` | Rutas anidadas de React Router con layouts; las vistas se cargan bajo demanda (`routes/lazy.ts`) |
| `app/(platform)/dashboard/page.tsx` → `modules/shared/components/dashboard-view.tsx` | Cada ruta apunta a la vista de su módulo (`modules/*/…View.tsx`) | Las «páginas» no contienen lógica |
| `layouts/platform-layout.tsx`, `app-shell.tsx`, `sidebar.tsx` | `layouts/PlatformLayout.tsx`, `Sidebar.tsx` | Guarda + barra lateral agrupada por secciones + menú móvil |
| `layouts/auth-layout.tsx` | `layouts/AuthLayout.tsx` | Presentación y formulario |
| Vista de juego dentro del shell | `layouts/SimulatorLayout.tsx` | Sin barra lateral, pero con la misma guarda del portal |
| `lib/navigation.ts` (`getNavigationForRole`, `groupNavigationBySection`) | `lib/navigation.ts` (`navigationFor`, `groupBySection`, `homePathFor`, `pathBelongsTo`) | Navegación y destino inicial centralizados |
| `hooks/use-role-guard.ts`, `lib/auth.ts` | `layouts/guards.tsx` (`RequireZone`) | La zona se deduce del tipo de token y del rol del servidor |
| `providers/app-providers.tsx` + `AuthSessionSync` | `providers/AppProviders.tsx` + `providers/SessionProvider.tsx` | Revalida el perfil sin vaciar la caché; la limpia al cambiar de identidad |
| `services/http-client.ts` | `services/http-client.ts` | Cliente único con errores en español y tiempo límite |
| `services/*-service.ts` | `services/{auth,user,space,case,session,evaluation,report,student,notification,delivery}-service.ts` | Un servicio por dominio de Iter Animi |
| `lib/query-keys.ts`, `lib/query-invalidation.ts` | Mismos nombres | Invalidación por efecto de negocio |
| `hooks/use-data.ts` | `hooks/use-academic.ts`, `use-cases.ts`, `use-student.ts`, `use-admin.ts` | Separados por dominio en lugar de un único archivo |
| `lib/student-session-adapters.ts` | `lib/student-session-adapters.ts` | DTO → modelo de vista del portal estudiantil |
| `components/ui/*`, `components/design-system/*` | `components/ui/*`, `components/design-system/*` | Primitivas propias en CSS, sin shadcn/Tailwind |
| `modules/simulator/components/{narrative-scene,decision-panel,simulator-toolbar}` | `modules/simulator/{SimulatorStage,NarrativePanel,DecisionPanel,SimulatorHeader,SimulatorActions,ReviewPanel}.tsx` | Mismas responsabilidades separadas |

## Qué cambió y por qué

| Aspecto de Ágora | En Iter Animi | Motivo |
|---|---|---|
| Next.js, Tailwind, shadcn, framer-motion, lucide | React + Vite, CSS propio, iconos SVG propios | Se conserva el stack de Iter Animi y no se copian dependencias |
| Store de Zustand para sesión y simulador | `SessionProvider` con almacenamiento propio; estado del simulador local a su vista | Tres tipos de token (personal, estudiante, resultados) y una sola estrategia de estado remoto (TanStack Query) |
| Estudiante con cuenta y cursos matriculados | Estudiante con token de una convocatoria; «Mi aula» = aula de esa sesión | El backend no tiene matrícula; el responsable decidió no cambiar la identidad |
| Catálogo de casos para el estudiante | No existe | El estudiante solo resuelve el caso de su convocatoria |
| Avatares clínicos, Live2D/Rive, emociones, consecuencias | Monigote SVG blanco sin rostro sobre escenario azul grisáceo | Dominio distinto; el personaje es reemplazable (`SceneCharacter.tsx`) |
| Opciones que se envían al hacer clic | Seleccionar ≠ confirmar, sin doble envío, reanudación | Dinámica de Iter Animi: el servidor guarda cada respuesta y decide tiempo y cierre |
| Temporizador local con pausa | Cuenta atrás de solo lectura sincronizada con el servidor | El tiempo lo controla el backend (CU21) |
| Administración con acceso al panel docente y a notas | Administración sin casos, sesiones ni notas | Permisos de Iter Animi (CP-056, CU36) |
| Calificaciones, métricas y RDA propios | Resultados, seguimiento y CSV del módulo 7 | Endpoints y reglas de Iter Animi |
| Editor de casos por escenas de Ágora | Editor propio sobre los endpoints de CU7 y CU8 | No se importó; se construyó porque CU7 y CU8 lo exigen |
