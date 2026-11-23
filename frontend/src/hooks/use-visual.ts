// Paquete visual: estático para el estudiante y borrador local (IndexedDB) para el docente.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { loadLibrary } from '../lib/visual/library'
import { publishAvailable } from '../lib/visual/publish'
import { loadStaticPackage, loadStaticPackageByCaseName } from '../lib/visual/static-packages'
import { draftKey, visualStorage } from '../lib/visual/storage'
import type { VisualDraft } from '../lib/visual/types'
import { useSession } from './use-session'

/** Paquete instalado en el frontend servido para las escenas de un cuestionario (null si no hay). */
export function useStaticVisualPackage(escenarioIds: string[]) {
  return useQuery({
    queryKey: ['visual-package', escenarioIds.join(',')],
    queryFn: () => loadStaticPackage(escenarioIds),
    enabled: escenarioIds.length > 0,
    // Se relee al abrir el simulador: un paquete recién publicado por el docente se ve sin recargar toda la app.
    staleTime: 0,
    retry: false,
  })
}

/** Paquete instalado de un caso por su nombre (inicio del estudiante, donde no hay id de caso ni escenas). */
export function useStaticVisualPackageByCaseName(caseName: string | undefined) {
  return useQuery({
    queryKey: ['visual-package-by-name', caseName ?? ''],
    queryFn: () => loadStaticPackageByCaseName(caseName ?? ''),
    enabled: Boolean(caseName),
    staleTime: 0,
    retry: false,
  })
}

/** Catálogo de personajes del sistema servido por el frontend (null si falta: solo quedan los sprites propios). */
export function useSpriteLibrary() {
  return useQuery({ queryKey: ['sprite-library'], queryFn: loadLibrary, staleTime: Infinity, retry: false })
}

/** ¿El servidor del frontend acepta la publicación automática del paquete visual? */
export function usePublishAvailable() {
  return useQuery({ queryKey: ['visual-publish'], queryFn: publishAvailable, staleTime: 60_000, retry: false })
}

function useDraftKey(caseId: string) {
  const { session } = useSession()
  // La identidad estable del docente es el id de su cuenta; sin ella no se separan borradores.
  return session?.kind === 'staff' ? draftKey(session.user.id, caseId) : null
}

export function useVisualDraft(caseId: string) {
  const key = useDraftKey(caseId)
  return useQuery({
    queryKey: ['visual-draft', key],
    queryFn: async () => (await visualStorage.get(key!)) ?? null,
    enabled: Boolean(key),
    staleTime: Infinity,
    gcTime: 0,
  })
}

export function useSaveVisualDraft(caseId: string) {
  const key = useDraftKey(caseId)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (draft: VisualDraft) => {
      if (!key) throw new Error('Se necesita una sesión de docente para guardar el borrador.')
      const saved = { ...draft, savedAt: new Date().toISOString() }
      await visualStorage.put(key, saved)
      return saved
    },
    onSuccess: (saved) => qc.setQueryData(['visual-draft', key], saved),
  })
}

export function useDeleteVisualDraft(caseId: string) {
  const key = useDraftKey(caseId)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      if (key) await visualStorage.remove(key)
    },
    onSuccess: () => qc.setQueryData(['visual-draft', key], null),
  })
}
