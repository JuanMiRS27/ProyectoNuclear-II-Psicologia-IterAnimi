// Evaluación y retroalimentación del docente (CU22–CU24).
import type { EvaluacionDetalle, ProcesoEvaluacion, ResultadosSesion, UUID } from '../types/api'
import { request } from './http-client'

const enc = encodeURIComponent

export const evaluationService = {
  process: (sessionId: UUID) => request<ProcesoEvaluacion>(`/sessions/${enc(sessionId)}/evaluations/process`, { method: 'POST' }),
  bySession: (sessionId: UUID) => request<ResultadosSesion>(`/sessions/${enc(sessionId)}/evaluations`),
  detail: (participationId: UUID) => request<EvaluacionDetalle>(`/participations/${enc(participationId)}/evaluation`),
  recalculate: (participationId: UUID) =>
    request<EvaluacionDetalle>(`/participations/${enc(participationId)}/evaluation/recalculate`, { method: 'POST' }),
  saveFeedback: (participationId: UUID, retroalimentacion_general: string | null) =>
    request<{ participacion_id: UUID; retroalimentacion_general: string | null }>(
      `/participations/${enc(participationId)}/feedback`,
      { method: 'PATCH', body: { retroalimentacion_general } },
    ),
} as const
