// Publicación automática del paquete visual en el frontend servido (plugin vite-plugins/visual-publish.ts).
// Al guardar o exportar, el editor envía el ZIP al servidor del frontend, que lo instala en public/visual-packages/:
// los estudiantes lo cargan desde ahí al abrir o recargar el caso. Sin backend ni almacenamiento externo.
// Si el frontend se sirve como archivos estáticos (sin el plugin), publishAvailable() es false y queda el flujo manual.

const BASE = `${(import.meta.env.BASE_URL ?? '/').replace(/\/?$/, '/')}__iter-animi/visual-packages`

export interface PublishResult {
  caseId: string
  nombre: string
  library: string | null
  images: number
  warnings: string[]
}

export class PublishError extends Error {}

/** true si el servidor que sirve este frontend acepta publicaciones (responde JSON, no el index.html de la SPA). */
export async function publishAvailable(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/status`, { cache: 'no-store' })
    if (!res.ok || !(res.headers.get('content-type') ?? '').includes('json')) return false
    const body = (await res.json()) as { enabled?: boolean }
    return body.enabled === true
  } catch {
    return false
  }
}

export async function publishPackage(bytes: Uint8Array): Promise<PublishResult> {
  let res: Response
  try {
    res = await fetch(`${BASE}/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/zip', 'X-Iter-Animi-Publish': '1' },
      body: bytes as BodyInit,
    })
  } catch {
    throw new PublishError('No se pudo contactar con el servidor del frontend para publicar.')
  }
  const body = (await res.json().catch(() => null)) as (PublishResult & { detail?: string }) | null
  if (!res.ok || !body) throw new PublishError(body?.detail ?? 'El servidor no pudo publicar el paquete.')
  return body
}
