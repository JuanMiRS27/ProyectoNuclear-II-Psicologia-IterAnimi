// Casos académicos (CU6–CU11): borradores, contenido, rúbrica, validación, publicación y CaseDSL.
import type {
  CasoCreate,
  CasoDetalle,
  CasoResumen,
  CriterioInput,
  CriterioRead,
  EscenarioInput,
  EscenarioRead,
  EstadoCaso,
  OpcionInput,
  OpcionRead,
  Page,
  PreguntaInput,
  PreguntaRead,
  ResultadoValidacion,
  RubricaRead,
  UUID,
} from '../types/api'
import { download, request } from './http-client'

const enc = encodeURIComponent
const base = (id: UUID) => `/cases/${enc(id)}`

export const caseService = {
  list: (q: { estado?: EstadoCaso } = {}) => request<Page<CasoResumen>>('/cases', { query: { limit: 100, ...q } }),
  get: (id: UUID) => request<CasoDetalle>(base(id)),
  create: (data: CasoCreate) => request<CasoDetalle>('/cases', { method: 'POST', body: data }),
  importDsl: (dsl: unknown) => request<CasoDetalle>('/cases/full', { method: 'POST', body: dsl }),
  update: (id: UUID, data: Partial<CasoCreate>) => request<CasoDetalle>(base(id), { method: 'PATCH', body: data }),
  remove: (id: UUID) => request<void>(base(id), { method: 'DELETE' }),
  validate: (id: UUID) => request<ResultadoValidacion>(`${base(id)}/validate`, { method: 'POST' }),
  publish: (id: UUID) => request<CasoDetalle>(`${base(id)}/publish`, { method: 'POST' }),
  archive: (id: UUID) => request<CasoDetalle>(`${base(id)}/archive`, { method: 'POST' }),
  exportDsl: (id: UUID) => download(`${base(id)}/dsl`, `caso_${id.slice(0, 8)}.json`),

  // Escenarios (CU7)
  addScenario: (id: UUID, data: EscenarioInput) => request<EscenarioRead>(`${base(id)}/scenarios`, { method: 'POST', body: data }),
  updateScenario: (id: UUID, sid: UUID, data: EscenarioInput) =>
    request<EscenarioRead>(`${base(id)}/scenarios/${enc(sid)}`, { method: 'PATCH', body: data }),
  removeScenario: (id: UUID, sid: UUID) => request<void>(`${base(id)}/scenarios/${enc(sid)}`, { method: 'DELETE' }),
  reorderScenarios: (id: UUID, ids: UUID[]) =>
    request<EscenarioRead[]>(`${base(id)}/scenarios/order`, { method: 'PUT', body: { ids } }),

  // Preguntas (CU7)
  addQuestion: (id: UUID, sid: UUID, data: PreguntaInput) =>
    request<PreguntaRead>(`${base(id)}/scenarios/${enc(sid)}/questions`, { method: 'POST', body: data }),
  updateQuestion: (id: UUID, qid: UUID, data: PreguntaInput) =>
    request<PreguntaRead>(`${base(id)}/questions/${enc(qid)}`, { method: 'PATCH', body: data }),
  removeQuestion: (id: UUID, qid: UUID) => request<void>(`${base(id)}/questions/${enc(qid)}`, { method: 'DELETE' }),
  reorderQuestions: (id: UUID, sid: UUID, ids: UUID[]) =>
    request<PreguntaRead[]>(`${base(id)}/scenarios/${enc(sid)}/questions/order`, { method: 'PUT', body: { ids } }),

  // Opciones (CU7)
  addOption: (id: UUID, qid: UUID, data: OpcionInput) =>
    request<OpcionRead>(`${base(id)}/questions/${enc(qid)}/options`, { method: 'POST', body: data }),
  updateOption: (id: UUID, qid: UUID, oid: UUID, data: OpcionInput) =>
    request<OpcionRead>(`${base(id)}/questions/${enc(qid)}/options/${enc(oid)}`, { method: 'PATCH', body: data }),
  removeOption: (id: UUID, qid: UUID, oid: UUID) =>
    request<void>(`${base(id)}/questions/${enc(qid)}/options/${enc(oid)}`, { method: 'DELETE' }),

  // Rúbrica (CU8)
  createRubric: (id: UUID, escala_max: string) =>
    request<RubricaRead>(`${base(id)}/rubric`, { method: 'POST', body: { escala_max, criterios: [] } }),
  updateRubric: (id: UUID, escala_max: string) => request<RubricaRead>(`${base(id)}/rubric`, { method: 'PATCH', body: { escala_max } }),
  addCriterion: (id: UUID, data: CriterioInput) => request<CriterioRead>(`${base(id)}/rubric/criteria`, { method: 'POST', body: data }),
  updateCriterion: (id: UUID, cid: UUID, data: CriterioInput) =>
    request<CriterioRead>(`${base(id)}/rubric/criteria/${enc(cid)}`, { method: 'PATCH', body: data }),
  removeCriterion: (id: UUID, cid: UUID) => request<void>(`${base(id)}/rubric/criteria/${enc(cid)}`, { method: 'DELETE' }),
} as const
