# Despliegue de Iter Animi

## Despliegue publico verificado

- Frontend: <https://iter-animi-web-5vqr.onrender.com>
- API: <https://iter-animi-api-5vqr.onrender.com/health>
- Rama desplegada: `main`, con despliegue automatico al recibir cambios.
- Neon: proyecto `iter-animi`, PostgreSQL 16 en Ohio; migraciones hasta la 0012.
- Credenciales iniciales: archivo local `.env.initial-admin`, ignorado por Git. Incluye la cuenta
  administrativa y el docente de demostracion. Cambia la clave administrativa desde **Mi cuenta**.

Se verificaron por HTTP los tres roles y el recorrido caso → convocatoria → intento → respuestas →
entrega → evaluacion → retroalimentacion → resultados. El caso **Conformidad grupal - demostracion publica**
incluye un paquete visual asociado a los ids reales de Neon. La sesion de comprobacion queda finalizada;
el docente puede programar otra sesion con el mismo caso para probar el simulador.

`node deploy/smoke-public.mjs` repite esta verificacion usando `.env.initial-admin`, crea o reutiliza
usuarios ficticios de demostracion y finaliza su sesion. Prepara un manifiesto visual local que debe
incorporarse al siguiente build del frontend. Nunca imprime claves, codigos ni tokens.

El envio de correo sigue desactivado en el plan gratuito; los codigos se consultan desde el portal
docente. La publicacion de cambios de sprites conserva el flujo exportar → instalar paquete → desplegar.

Hay dos configuraciones: Docker Compose para ejecutar y verificar el sistema completo en el equipo,
y un Blueprint de Render para una demo gratuita con PostgreSQL en Neon.
Dockerizar el frontend es útil para servirlo con Nginx, pero Render Static Site no necesita Docker.

## Docker: sistema completo en local

Requisitos: Docker Desktop con contenedores Linux y Node.js 24+ para generar las claves.
Desde la raíz del repositorio:

```powershell
node deploy/init-env.mjs
docker compose --env-file .env.docker up --build -d
docker compose --env-file .env.docker ps -a
```

Abrir <http://localhost:8080>. Nginx sirve el build y reenvía `/api/` al backend por la red interna:
el navegador no necesita CORS ni conoce el nombre Docker `backend`.
La API y PostgreSQL no publican puertos en el equipo. Se usa una base nueva y aislada; no se lee
`backend/.env`, no se migra la base que ya tengas en tu equipo ni se copian sus usuarios.
Puedes cambiar `FRONTEND_PORT` en `.env.docker` si 8080 está ocupado.

Compose inicia PostgreSQL, espera que esté disponible, aplica Alembic y arranca la API y los tres
workers: avisos internos, expiración de intentos y cierre de sesiones. Las migraciones son un servicio
separado y los workers no arrancan hasta que terminen. Los correos reales están desactivados;
el docente puede consultar y entregar los códigos de convocatoria.

Crear el primer administrador (pide la contraseña sin mostrarla):

```powershell
docker compose --env-file .env.docker exec backend python -m app.scripts.create_admin --nombre "Administrador" --correo admin@universidad.edu.co
```

Diagnóstico y parada:

```powershell
docker compose --env-file .env.docker logs --tail 60 backend notifications participation-expiration session-expiration
docker compose --env-file .env.docker down
```

`down` conserva el volumen `postgres_data`. No uses `down -v` si quieres conservar los datos.
Conserva también `.env.docker`: cambiar la clave de cifrado impide recuperar los códigos existentes;
cambiar POSTGRES_PASSWORD no cambia automáticamente la contraseña de un volumen ya inicializado.
El generador no sobrescribe el archivo. Los archivos `.env` y dependencias locales quedan fuera
de los contextos de construcción y las credenciales se inyectan al ejecutar, nunca en las imágenes.

### Solo la imagen del frontend

```powershell
docker build -t iter-animi-frontend ./frontend
docker run --rm -p 8080:8080 -e BACKEND_UPSTREAM=http://host.docker.internal:8000 iter-animi-frontend
```

En Docker Desktop, `host.docker.internal` apunta al equipo anfitrión: para este ejemplo debe haber una API
escuchando en un puerto accesible desde Docker. Compose evita esa dependencia.
La imagen tiene dos etapas: Node 24 compila e instala con `npm ci`; Nginx sirve solo `dist/`.
`PORT` (8080 por defecto) y `BACKEND_UPSTREAM` se sustituyen al arrancar en la plantilla Nginx.
No uses `localhost:8000` para apuntar a otro contenedor.

Por defecto `VITE_API_BASE_URL=/api/v1`. Para una API en otro dominio, la URL se fija **al construir**:

```powershell
docker build --build-arg VITE_API_BASE_URL=https://TU-API.onrender.com/api/v1 -t iter-animi-frontend ./frontend
```

En ese caso configura también `BACKEND_UPSTREAM` con una dirección resoluble al arrancar Nginx,
y `CORS_ALLOWED_ORIGINS` en la API. Una variable `VITE_` pasada a `docker run` no cambia el build.

## Render + Neon: demo gratuita

El archivo raíz `render.yaml` describe un frontend estático y una API Docker gratuitos.
No crea bases de datos de Render ni servicios de pago. La base de datos es externa en Neon.
Esta configuración no equivale a un sistema con procesos continuos: revisa las limitaciones abajo.

1. Crea un proyecto **Free** en Neon. Copia la conexión **directa, sin pooler**, con TLS.
   Este backend utiliza opciones de conexión de PostgreSQL; la conexión directa evita
   incompatibilidades de parámetros de sesión con PgBouncer.
2. En la URL, cambia únicamente el esquema `postgresql://` a `postgresql+psycopg://` y conserva
   usuario, contraseña codificada, host, base y `?sslmode=require` (y otros parámetros de TLS).
   Esa será `DATABASE_URL`; nunca la pongas en variables `VITE_`.
3. Genera una clave AES **nueva para la base nueva**. No reutilices `.env.docker` para producción:

   ```powershell
   python -c "import base64, secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
   ```

4. Revisa y sube tus cambios al repositorio Git que conectarás con Render. La configuración
   incluye las migraciones hasta la 0012, también verificada en la base aislada de Docker.
5. En Render, crea un **Blueprint** desde ese repositorio. Revisa que la API use **Free** y el
   frontend **Static Site**. Los nombres pueden ajustarse si ya están ocupados.
6. Completa los valores que Render solicita:

   | Servicio | Variable | Valor |
   |---|---|---|
   | API | `DATABASE_URL` | URL directa Neon con `postgresql+psycopg://` y TLS |
   | API | `CONVOCATION_CODE_ENCRYPTION_KEY` | Clave AES del paso 3 |
   | API | `CORS_ALLOWED_ORIGINS` | `https://TU-FRONTEND.onrender.com` sin ruta |
   | API | `SIMULATOR_ACCESS_URL` | `https://TU-FRONTEND.onrender.com/ingresar` |
   | Frontend | `VITE_API_BASE_URL` | `https://TU-API.onrender.com/api/v1` |

   Render genera `JWT_SECRET_KEY`. Confirma las URLs reales asignadas y corrige las variables
   si los nombres finales difieren; reconstruye el frontend al cambiar la URL de la API.
   No cambies las claves después de crear datos sin un plan de rotación.
7. Antes de arrancar, la API ejecuta `alembic upgrade head`. En Free no se usa `preDeployCommand`.
   Si una migración falla, el despliegue falla; comprueba los logs antes de repetirlo.
   El comando `python -m app.scripts.start_server` aplica las migraciones y reemplaza el proceso por
   Uvicorn, evitando diferencias de interpretacion de comillas entre Docker y Render.
8. Crea el administrador desde tu equipo, en un contenedor temporal con las **mismas** variables
   de la API en un archivo local ignorado por Git (por ejemplo `backend/.env.render`):

   ```powershell
   docker build -t iter-animi-backend ./backend
   docker run --rm -it --env-file backend/.env.render iter-animi-backend python -m app.scripts.create_admin --nombre "Administrador" --correo admin@universidad.edu.co
   ```

   El archivo debe contener `ENVIRONMENT`, `DATABASE_URL`, `JWT_SECRET_KEY` y
   `CONVOCATION_CODE_ENCRYPTION_KEY` con los valores de Render. No los pongas en el historial.
   Render Free no proporciona una shell remota ni ejecuciones puntuales de jobs.
9. Abre `/health` de la API, espera que responda, y prueba acceso, crear un caso/sesión, ingresar
   como estudiante y confirmar una respuesta. Recarga una ruta interna del portal para verificar la SPA.

### Límites que afectan a esta arquitectura

- La API gratuita duerme tras 15 minutos sin tráfico y puede tardar cerca de un minuto en despertar.
  El cliente actual cancela las peticiones a los 20 segundos: abre `/health` y espera su respuesta
  antes de comenzar una sustentación; si un acceso agota el tiempo, reinténtalo cuando despierte.
- El Blueprint habilita los tres workers integrados en la API: notificaciones cada 30 segundos,
  expiracion de intentos cada 60 y cierre de sesiones cada 300. Se detienen al apagar la API y
  recuperan el trabajo pendiente al arrancar. No necesitan procesos adicionales en tu PC.
  Para una ejecucion externa opcional, usa las mismas variables remotas:

  ```powershell
  docker run --rm --env-file backend/.env.render iter-animi-backend python -m app.workers.participation_expiration --intervalo 60
  docker run --rm --env-file backend/.env.render iter-animi-backend python -m app.workers.session_expiration --intervalo 300
  ```

  Cada comando ocupa una terminal y deja de trabajar al cerrarla; no es necesario para la demo.
  Para trabajo continuo incluso mientras la API duerme se necesita un entorno donde esos procesos
  puedan mantenerse activos; Render Background Workers es de pago.
  Los workers consultan PostgreSQL periódicamente y pueden impedir que Neon suspenda su cómputo:
  ejecútalos durante las pruebas, no indefinidamente si debes respetar la cuota gratuita.
- El envío SMTP está desactivado. Render Free bloquea los puertos 25, 465 y 587. Para correos reales
  hace falta adaptar el envío a una API HTTPS o elegir alojamiento que permita tu SMTP.
- Los datos persistentes van en Neon, nunca en el disco efímero del contenedor. Su plan Free tiene
  cuotas de almacenamiento y cómputo; no es una garantía de funcionamiento ilimitado.

## Sprites y publicación de paquetes

Nginx y Render Static Site sirven archivos estáticos. No ejecutan el plugin local de Vite
`/__iter-animi/visual-packages`; el editor conserva el flujo de borrador y exportación.
Para que los estudiantes vean cambios del personaje:

1. Exporta el paquete desde el editor.
2. Desde `frontend/`, ejecuta `npm run visual:install -- RUTA_DEL_PAQUETE.zip`.
3. Para Render, incluye `public/visual-packages/` en Git y despliega de nuevo.
   Para Compose, reconstruye con `docker compose --env-file .env.docker up --build -d frontend`.

El build incluye la biblioteca y todos los paquetes ya instalados. Los ids del paquete deben coincidir
con los de los casos en la base desplegada: copiar un paquete no crea el caso ni migra sus ids.
No expongas `npm run dev` o `npm run preview` como servidor público de producción.

## Verificación local realizada (26 de noviembre de 2026)

- `npm run check`: tipos, lint, 39 pruebas y build aprobados.
- Ambas imágenes construidas desde sus Dockerfiles; Nginx validado con `nginx -t`.
- Compose: PostgreSQL, API y frontend saludables; los tres workers ejecutaron pasadas sin errores.
- Base Docker nueva migrada desde cero hasta `0012_bitacora_fechas_trigger`.
- HTTP: salud, acceso, ruta interna y ambos índices visuales responden 200; recursos visuales ausentes
  responden 404; la API a través del proxy rechaza acceso sin token y credenciales inexistentes con 401.
- `.env` y `node_modules` no aparecen en el directorio servido de la imagen frontend;
  el backend tampoco incorpora `.env`.
- `render.yaml` validado contra el JSON Schema oficial de Render.

La base local arranca vacía: falta crear el administrador para hacer el recorrido académico con datos.
Estas comprobaciones no constituyen un despliegue público ni una prueba de los proveedores remotos.

## Referencias oficiales

- [Render: servicios gratuitos y sus límites](https://render.com/docs/free)
- [Render: Blueprint YAML](https://render.com/docs/blueprint-spec)
- [Render: frontend estático](https://render.com/docs/static-sites)
- [Neon: precios y cuotas](https://neon.com/pricing)
- [Docker: construcción en varias etapas](https://docs.docker.com/build/building/multi-stage/)
