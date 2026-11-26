// Borradores visuales en IndexedDB, separados por cuenta docente y caso.
// Las imágenes se guardan como Blob (nunca en localStorage). Nada de esto se publica: vive en este navegador.
import type { VisualDraft } from './types.ts'

const DB = 'iter-animi-visual'
const STORE = 'borradores'

function openVersion(version?: number): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = version ? indexedDB.open(DB, version) : indexedDB.open(DB)
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) req.result.createObjectStore(STORE)
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error ?? new Error('No se pudo abrir el almacenamiento del navegador.'))
  })
}

/**
 * Abre la base de borradores. Si existe sin su almacén (p. ej. la creó otra herramienta o quedó a medias), la sube de
 * versión para crearlo en lugar de fallar: el editor nunca queda bloqueado por un IndexedDB incompleto.
 */
async function open(): Promise<IDBDatabase> {
  const db = await openVersion()
  if (db.objectStoreNames.contains(STORE)) return db
  const next = db.version + 1
  db.close()
  return openVersion(next)
}

function tx<T>(mode: IDBTransactionMode, run: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return open().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const t = db.transaction(STORE, mode)
        const req = run(t.objectStore(STORE))
        t.oncomplete = () => {
          db.close()
          resolve(req.result)
        }
        t.onerror = () => {
          db.close()
          reject(t.error ?? new Error('No se pudo guardar en el navegador.'))
        }
      }),
  )
}

export const draftKey = (userId: string, caseId: string) => `${userId}:${caseId}`

export const visualStorage = {
  get: (key: string) => tx<VisualDraft | undefined>('readonly', (s) => s.get(key) as IDBRequest<VisualDraft | undefined>),
  put: (key: string, draft: VisualDraft) => tx('readwrite', (s) => s.put(draft, key)),
  remove: (key: string) => tx('readwrite', (s) => s.delete(key)),
}
