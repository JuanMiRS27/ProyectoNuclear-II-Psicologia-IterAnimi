// Cliente HTTP único. Toda llamada a la API pasa por aquí.
//
// URL base: VITE_API_BASE_URL (p. ej. "https://api.universidad.edu.co/api/v1"). Si no se define,
// se usa "/api/v1" en el mismo origen: en desarrollo lo atiende el proxy de Vite y en producción
// el servidor web (proxy inverso) que sirve el frontend.

import { currentToken } from '../auth/session'

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '/api/v1').replace(/\/+$/, '')

export class ApiError extends Error {
  readonly status: number
  readonly body: unknown
  readonly retryAfterSeconds: number | null

  constructor(status: number, message: string, body: unknown = null, retryAfterSeconds: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
    this.retryAfterSeconds = retryAfterSeconds
  }

  get isNetwork() {
    return this.status === 0
  }
}

type TokenProvider = () => string | null
type UnauthorizedHandler = (error: ApiError) => void

let tokenProvider: TokenProvider = currentToken
let unauthorizedHandler: UnauthorizedHandler = () => {}

/** La capa de autenticación registra qué hacer ante un 401 (y, opcionalmente, otra fuente del token). */
export function configureClient(options: { getToken?: TokenProvider; onUnauthorized: UnauthorizedHandler }) {
  if (options.getToken) tokenProvider = options.getToken
  unauthorizedHandler = options.onUnauthorized
}

const MENSAJES_POR_ESTADO: Record<number, string> = {
  400: 'La solicitud no cumple una regla del sistema.',
  401: 'Tu sesión no es válida o expiró. Vuelve a ingresar.',
  403: 'No tienes permiso para realizar esta acción.',
  404: 'No se encontró el recurso solicitado.',
  409: 'La operación no es posible en el estado actual.',
  422: 'Revisa los datos: hay valores con un formato no válido.',
  429: 'Demasiados intentos. Espera unos minutos antes de volver a intentarlo.',
  500: 'El servidor tuvo un problema. Inténtalo de nuevo más tarde.',
}

/** Extrae un mensaje legible del cuerpo de error del backend ({detail: "..."} o lista de Pydantic). */
export function messageFromBody(status: number, body: unknown): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (Array.isArray(detail) && detail.length > 0) {
      // Errores de validación de FastAPI: los mensajes vienen en inglés; se nombran solo los campos.
      const campos = detail
        .map((d) => (Array.isArray(d?.loc) ? d.loc.filter((x: unknown) => x !== 'body' && x !== 'query').join('.') : ''))
        .filter(Boolean)
      const unicos = [...new Set(campos)]
      return unicos.length
        ? `Revisa los datos de: ${unicos.join(', ')}.`
        : (MENSAJES_POR_ESTADO[422] as string)
    }
  }
  return MENSAJES_POR_ESTADO[status] ?? MENSAJES_POR_ESTADO[500]!
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  body?: unknown
  query?: Record<string, string | number | boolean | null | undefined>
  /** Token explícito (p. ej. justo después del login, antes de guardarlo). */
  token?: string | null
  /** No dispara el cierre de sesión global ante un 401 (pantalla de acceso). */
  skipAuthHandler?: boolean
  signal?: AbortSignal
}

function buildUrl(path: string, query?: RequestOptions['query']) {
  const url = `${API_BASE_URL}${path}`
  if (!query) return url
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
  }
  const qs = params.toString()
  return qs ? `${url}?${qs}` : url
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = options.token !== undefined ? options.token : tokenProvider()
  if (token) headers.Authorization = `Bearer ${token}`
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'

  let response: Response
  try {
    response = await fetch(buildUrl(path, options.query), {
      method: options.method ?? 'GET',
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
      cache: 'no-store',
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new ApiError(0, 'No se pudo conectar con el servidor. Comprueba tu conexión e inténtalo de nuevo.')
  }

  if (!response.ok) {
    let body: unknown = null
    try {
      body = await response.json()
    } catch {
      body = null
    }
    const retry = Number(response.headers.get('Retry-After'))
    const error = new ApiError(
      response.status,
      messageFromBody(response.status, body),
      body,
      Number.isFinite(retry) && retry > 0 ? retry : null,
    )
    if (response.status === 401 && !options.skipAuthHandler) unauthorizedHandler(error)
    throw error
  }
  return response
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await send(path, options)
  if (response.status === 204) return undefined as T
  const text = await response.text()
  return (text ? JSON.parse(text) : undefined) as T
}

/** Descarga un archivo (CSV, JSON) respetando la autenticación y el nombre que propone el servidor. */
export async function download(path: string, fallbackName: string, query?: RequestOptions['query']) {
  const response = await send(path, { query })
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') ?? ''
  const match = /filename="?([^";]+)"?/i.exec(disposition)
  const name = match?.[1] ?? fallbackName
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
