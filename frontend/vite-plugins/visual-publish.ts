// Publicación local de paquetes visuales desde el editor («Guardar y publicar»).
//
// El borrador del docente vive en su navegador (IndexedDB); los estudiantes cargan los paquetes desde la carpeta
// estática public/visual-packages/ del frontend servido. Este plugin del servidor del frontend (Vite: `npm run dev` y
// `npm run preview`) recibe el ZIP exportado por el editor y lo instala con la misma validación que
// `npm run visual:install`, así que el estudiante ve el personaje y las reacciones al recargar.
//
// No es el backend ni una API nueva del sistema: solo existe mientras corre el servidor del frontend en el equipo del
// docente o del despliegue de demostración. Un despliegue estático (dist/ en Nginx, Netlify…) no lo tiene y el editor
// vuelve al flujo Exportar → visual:install → build.
import type { IncomingMessage, ServerResponse } from 'node:http'
import { readFile, stat } from 'node:fs/promises'
import { extname, resolve, sep } from 'node:path'
import type { Connect, Plugin, ResolvedConfig } from 'vite'
import { installPackage, PUBLIC_PACKAGES } from '../scripts/visual-packages-lib.mjs'

export const PUBLISH_PATH = '/__iter-animi/visual-packages'
const MAX_BYTES = 20 * 1024 * 1024 + 64 * 1024

const json = (res: ServerResponse, status: number, body: unknown) => {
  res.statusCode = status
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.setHeader('Cache-Control', 'no-store')
  res.end(JSON.stringify(body))
}

const isLoopback = (addr: string | undefined) => addr === '127.0.0.1' || addr === '::1' || addr === '::ffff:127.0.0.1'

/** Solo peticiones del propio equipo, del mismo origen y con la cabecera del editor (obliga a preflight CORS). */
function allowed(req: IncomingMessage) {
  if (!isLoopback(req.socket.remoteAddress)) return 'Solo se puede publicar desde este mismo equipo.'
  if (req.headers['x-iter-animi-publish'] !== '1') return 'Petición no reconocida.'
  const origin = req.headers.origin
  if (origin) {
    try {
      if (new URL(origin).host !== req.headers.host) return 'Origen no permitido.'
    } catch {
      return 'Origen no permitido.'
    }
  }
  return null
}

function readBody(req: IncomingMessage): Promise<Uint8Array> {
  return new Promise((ok, fail) => {
    const chunks: Buffer[] = []
    let size = 0
    req.on('data', (c: Buffer) => {
      size += c.length
      if (size > MAX_BYTES) {
        fail(new Error('El paquete supera los 20 MB permitidos.'))
        req.destroy()
      } else chunks.push(c)
    })
    req.on('end', () => ok(new Uint8Array(Buffer.concat(chunks))))
    req.on('error', fail)
  })
}

function handler(roots: () => string[]): Connect.NextHandleFunction {
  return async (req, res, next) => {
    const url = req.url ?? '/'
    if (req.method === 'GET' && url.startsWith('/status')) return json(res, 200, { enabled: true })
    if (req.method !== 'POST' || !url.startsWith('/publish')) return next()
    const denied = allowed(req)
    if (denied) return json(res, 403, { detail: denied })
    try {
      const bytes = await readBody(req)
      let result = null
      for (const root of roots()) result = await installPackage(bytes, root)
      const r = result!
      return json(res, 200, { caseId: r.manifest.case.id, nombre: r.manifest.case.nombre, library: r.manifest.character.library ?? null, images: r.images, warnings: r.warnings })
    } catch (err) {
      // Errores de validación del paquete (PackageError) o de tamaño: mensaje legible para el editor.
      return json(res, 400, { detail: err instanceof Error ? err.message : 'No se pudo publicar el paquete.' })
    }
  }
}

const TYPES: Record<string, string> = { '.json': 'application/json', '.png': 'image/png', '.webp': 'image/webp' }

/** En `vite preview` los archivos de dist/ se indexan al arrancar: los paquetes publicados después se sirven aquí. */
function serveLivePackages(root: string): Connect.NextHandleFunction {
  return async (req, res, next) => {
    const rel = decodeURIComponent((req.url ?? '/').split('?')[0]!).replace(/^\/+/, '')
    const file = resolve(root, rel)
    if (!file.startsWith(root + sep) || !TYPES[extname(file)]) return next()
    try {
      if (!(await stat(file)).isFile()) return next()
      res.setHeader('Content-Type', TYPES[extname(file)]!)
      res.setHeader('Cache-Control', 'no-cache')
      res.end(await readFile(file))
    } catch {
      next()
    }
  }
}

export function visualPublish(): Plugin {
  let config: ResolvedConfig
  return {
    name: 'iter-animi-visual-publish',
    configResolved(c) {
      config = c
    },
    // Desarrollo: public/ se sirve directamente desde el disco.
    configureServer(server) {
      server.middlewares.use(PUBLISH_PATH, handler(() => [PUBLIC_PACKAGES]))
    },
    // Vista previa del build: se instala en public/ (para el próximo build) y en dist/ (para servirlo ya).
    configurePreviewServer(server) {
      const dist = resolve(config.root, config.build.outDir, 'visual-packages')
      server.middlewares.use(PUBLISH_PATH, handler(() => [PUBLIC_PACKAGES, dist]))
      server.middlewares.use('/visual-packages', serveLivePackages(dist))
    },
  }
}
