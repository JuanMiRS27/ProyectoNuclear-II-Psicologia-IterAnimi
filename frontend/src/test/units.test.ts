import { describe, expect, it } from 'vitest'
import { messageFromBody } from '../services/http-client'
import type { AppSession } from '../lib/auth-storage'
import { homePathFor, pathBelongsTo } from '../lib/navigation'
import { buildSteps, initialStepIndex, nextStepIndex, savedFromQuestionnaire } from '../modules/simulator/steps'
import { localInputToIso, parseEmails } from '../lib/format'
import { canOpenNow } from '../lib/session-rules'
import { questionnaire } from './fixtures'

describe('pasos del simulador', () => {
  it('respeta el orden del servidor: prólogo, una decisión por paso y revisión final', () => {
    const steps = buildSteps(questionnaire())
    expect(steps.map((s) => (s.kind === 'decision' ? s.pregunta.id : s.kind))).toEqual(['prologue', 'q1', 'q2', 'q3', 'review'])
  })

  it('omite el prólogo si el caso no tiene textos introductorios', () => {
    const steps = buildSteps(questionnaire({ caso: { nombre: 'X', desarrollo_situacional: null, historia: '  ' } }))
    expect(steps[0]!.kind).toBe('decision')
  })

  it('retoma en la primera decisión sin respuesta guardada', () => {
    const c = questionnaire()
    c.escenarios[1]!.preguntas[1]!.opcion_seleccionada_id = 'o1' // q1 respondida
    const steps = buildSteps(c)
    const saved = savedFromQuestionnaire(c)
    expect(saved).toEqual({ q1: 'o1' })
    expect(initialStepIndex(steps, saved)).toBe(2) // q2
    expect(initialStepIndex(steps, {})).toBe(0)
    expect(initialStepIndex(steps, { q1: 'o1', q2: 'o3', q3: 'o5' })).toBe(steps.length - 1)
  })

  it('tras confirmar avanza a la siguiente decisión pendiente o a la revisión', () => {
    const steps = buildSteps(questionnaire())
    expect(nextStepIndex(steps, 1, { q1: 'o1' })).toBe(2)
    expect(nextStepIndex(steps, 1, { q1: 'o1', q2: 'o3' })).toBe(3)
    expect(nextStepIndex(steps, 3, { q1: 'o1', q3: 'o5' })).toBe(4)
  })
})

describe('cliente de API', () => {
  it('usa el detalle del servidor cuando existe', () => {
    expect(messageFromBody(409, { detail: 'El tiempo de la participación terminó.' })).toBe('El tiempo de la participación terminó.')
  })
  it('no muestra mensajes en inglés de Pydantic, solo los campos', () => {
    expect(messageFromBody(422, { detail: [{ loc: ['body', 'correo'], msg: 'value is not a valid email' }] })).toBe(
      'Revisa los datos de: correo.',
    )
  })
  it('da un mensaje en español cuando no hay cuerpo', () => {
    expect(messageFromBody(500, null)).toMatch(/servidor/)
  })
})

describe('formato y reglas de presentación', () => {
  it('convierte la hora local a ISO con desplazamiento explícito', () => {
    const iso = localInputToIso('2026-11-18T08:30')!
    expect(iso).toMatch(/^2026-11-18T08:30:00[+-]\d{2}:\d{2}$/)
    expect(new Date(iso).getTime()).toBe(new Date('2026-11-18T08:30').getTime())
  })
  it('separa correos y elimina duplicados', () => {
    expect(parseEmails('A@x.edu, b@x.edu\n a@x.edu;c@x.edu')).toEqual(['a@x.edu', 'b@x.edu', 'c@x.edu'])
  })
  it('solo permite abrir una sesión dentro de su ventana', () => {
    const s = { estado: 'SIN_INICIAR', inicio: '2026-11-18T08:00:00Z', fin: '2026-11-18T10:00:00Z' }
    expect(canOpenNow(s, Date.parse('2026-11-18T07:59:00Z'))).toBe(false)
    expect(canOpenNow(s, Date.parse('2026-11-18T08:00:00Z'))).toBe(true)
    expect(canOpenNow(s, Date.parse('2026-11-18T10:00:00Z'))).toBe(false)
    expect(canOpenNow({ ...s, estado: 'EN_CURSO' }, Date.parse('2026-11-18T09:00:00Z'))).toBe(false)
  })
  it('solo vuelve a una ruta de la zona del rol que determinó el servidor', () => {
    const docente = { kind: 'staff', token: 't', expiresAt: 0, user: { rol: 'DOCENTE' } } as AppSession
    const estudiante = { kind: 'student', token: 't', expiresAt: 0, sesionId: 's', convocatoriaId: 'c', correo: 'e' } as AppSession
    expect(pathBelongsTo(docente, '/docente/sesiones/1')).toBe(true)
    expect(pathBelongsTo(docente, '/admin/usuarios')).toBe(false)
    expect(pathBelongsTo(estudiante, '/estudiante/caso/1')).toBe(true)
    expect(pathBelongsTo(estudiante, '/docente/aulas')).toBe(false)
    expect(homePathFor(docente)).toBe('/docente')
    expect(homePathFor(estudiante)).toBe('/estudiante')
    const resultados = { ...estudiante, kind: 'results' } as AppSession
    expect(homePathFor(resultados)).toBe('/estudiante')
    const admin = { kind: 'staff', token: 't', expiresAt: 0, user: { rol: 'ADMINISTRADOR' } } as AppSession
    expect(homePathFor(admin)).toBe('/admin')
  })
})
