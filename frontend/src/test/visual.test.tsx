import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, render, renderHook, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { buildPackage, detectImage, PackageError, parsePackage, validateManifest } from '../lib/visual/package'
import { buildRuntime, emptyManifest } from '../lib/visual/runtime'
import { optionSignature, sceneSignature } from '../lib/visual/signature'
import { PACKAGE_FORMAT, PACKAGE_VERSION, type VisualManifest } from '../lib/visual/types'
import { readZip, writeZip, ZipError } from '../lib/visual/zip'
import { SimulatorPlayView } from '../modules/simulator/SimulatorPlayView'
import { CARRY_MS, useStageExpression } from '../modules/simulator/use-stage-expression'
import { SessionProvider } from '../providers/SessionProvider'
import type { Cuestionario } from '../types/api'

// Ids estables con forma de UUID, como los que devuelve la API.
const CASE = '00000000-0000-4000-8000-000000000001'
const E1 = '00000000-0000-4000-8000-0000000000e1'
const E2 = '00000000-0000-4000-8000-0000000000e2'
const Q1 = '00000000-0000-4000-8000-0000000000a1'
const Q2 = '00000000-0000-4000-8000-0000000000a2'
const O1 = '00000000-0000-4000-8000-0000000000b1'
const O2 = '00000000-0000-4000-8000-0000000000b2'
const O3 = '00000000-0000-4000-8000-0000000000b3'
const O4 = '00000000-0000-4000-8000-0000000000b4'
const O5 = '00000000-0000-4000-8000-0000000000b5'

const content = {
  escenarios: [
    {
      id: E1,
      titulo: 'La reunión',
      preguntas: [
        {
          id: Q1,
          enunciado: '¿Qué haces?',
          opciones: [
            { id: O1, texto: 'Escuchar' },
            { id: O2, texto: 'Interrumpir' },
            { id: O3, texto: 'Esperar' },
          ],
        },
      ],
    },
    { id: E2, titulo: 'El pasillo', preguntas: [{ id: Q2, enunciado: '¿Y ahora?', opciones: [{ id: O4, texto: 'Hablar' }, { id: O5, texto: 'Irse' }] }] },
  ],
}

function manifest(): VisualManifest {
  return {
    format: PACKAGE_FORMAT,
    version: PACKAGE_VERSION,
    case: { id: CASE, nombre: 'Caso visual' },
    character: { name: 'Camila', defaultExpression: 'neutral' },
    expressions: [
      { id: 'neutral', label: 'Neutral', sprite: 'sprites/neutral.png' },
      { id: 'inquieto', label: 'Inquieto', sprite: 'sprites/inquieto.png' },
      { id: 'aliviado', label: 'Aliviado', sprite: null },
    ],
    scenes: [{ escenarioId: E1, signature: sceneSignature('La reunión'), initialExpression: 'neutral' }],
    reactions: [
      { opcionId: O1, preguntaId: Q1, escenarioId: E1, signature: optionSignature('¿Qué haces?', 'Escuchar'), expression: 'aliviado', motion: 'fade' },
      { opcionId: O2, preguntaId: Q1, escenarioId: E1, signature: optionSignature('¿Qué haces?', 'Interrumpir'), expression: 'inquieto', motion: 'rise' },
    ],
    createdAt: '2026-11-19T00:00:00.000Z',
  }
}

const PNG = new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0, 0, 0, 13, 73, 72, 68, 82])
const enc = new TextEncoder()

describe('paquete visual', () => {
  it('ZIP: lo escrito se lee igual y una alteración se detecta', async () => {
    const zip = writeZip([
      { name: 'a.txt', data: enc.encode('hola') },
      { name: 'sprites/x.png', data: PNG },
    ])
    const back = await readZip(zip, { maxEntries: 10, maxTotalBytes: 1e6 })
    expect(back.map((e) => e.name)).toEqual(['a.txt', 'sprites/x.png'])
    expect(new TextDecoder().decode(back[0]!.data)).toBe('hola')
    const broken = zip.slice()
    broken[broken.indexOf(0x68)] ^= 0xff // cambia un byte del contenido de a.txt
    await expect(readZip(broken, { maxEntries: 10, maxTotalBytes: 1e6 })).rejects.toBeInstanceOf(ZipError)
  })

  it('exportar e importar conserva el manifiesto y las imágenes', async () => {
    const m = manifest()
    const bytes = await buildPackage(m, { neutral: new Blob([PNG]), inquieto: new Blob([PNG]) })
    const parsed = await parsePackage(bytes)
    expect(parsed.manifest.case.id).toBe(CASE)
    expect(parsed.manifest.reactions).toHaveLength(2)
    expect(Object.keys(parsed.files).sort()).toEqual(['sprites/inquieto.png', 'sprites/neutral.png'])
    expect(detectImage(parsed.files['sprites/neutral.png']!)).toBe('png')
  })

  it('rechaza rutas externas y saltos de directorio en el manifiesto', () => {
    for (const sprite of ['../secreto.png', '/etc/x.png', 'https://cdn.example.com/a.png', 'sprites/../../a.png', 'sprites/a.gif']) {
      const m = manifest()
      m.expressions[0]!.sprite = sprite
      expect(() => validateManifest(m)).toThrow(PackageError)
    }
    expect(() => validateManifest({ ...manifest(), version: 99 })).toThrow(PackageError)
    expect(() => validateManifest({ ...manifest(), format: 'otro' })).toThrow(PackageError)
  })

  it('rechaza entradas ZIP con salto de directorio o imágenes que no son PNG/WebP', async () => {
    const json = enc.encode(JSON.stringify({ ...manifest(), expressions: manifest().expressions.map((e) => ({ ...e, sprite: null })) }))
    const traversal = writeZip([
      { name: 'manifest.json', data: json },
      { name: '../fuera.png', data: PNG },
    ])
    await expect(parsePackage(traversal)).rejects.toBeInstanceOf(PackageError)
    const m = manifest()
    const fake = writeZip([
      { name: 'manifest.json', data: enc.encode(JSON.stringify(m)) },
      { name: 'sprites/neutral.png', data: enc.encode('<svg/>') },
      { name: 'sprites/inquieto.png', data: PNG },
    ])
    await expect(parsePackage(fake)).rejects.toBeInstanceOf(PackageError)
  })

  it('no incluye claves ni datos de evaluación: solo dirección narrativa', async () => {
    const parsed = await parsePackage(await buildPackage(manifest(), { neutral: new Blob([PNG]), inquieto: new Blob([PNG]) }))
    const text = JSON.stringify(parsed.manifest)
    for (const word of ['correct', 'es_correcta', 'rubrica', 'puntaje', 'justificacion']) expect(text).not.toContain(word)
  })
})

describe('asociaciones con el caso', () => {
  it('usa los ids estables y no la letra; una opción cuyo texto cambió queda pendiente y no reacciona', () => {
    const r = buildRuntime(manifest(), content)
    expect(r.initialFor(E1)).toBe('neutral')
    expect(r.initialFor(E2)).toBe('neutral') // sin expresión inicial propia → la por defecto
    expect(r.reactionFor(O2)).toEqual({ expression: 'inquieto', motion: 'rise' })
    expect(r.reactionFor(O3)).toBeNull() // «Sin cambio»

    const edited = structuredClone(content)
    edited.escenarios[0]!.preguntas[0]!.opciones[1]!.texto = 'Interrumpir con calma'
    // Reordenar las opciones no rompe nada: la letra cambia, el id no.
    edited.escenarios[0]!.preguntas[0]!.opciones.reverse()
    const r2 = buildRuntime(manifest(), edited)
    expect(r2.reactionFor(O2)).toBeNull()
    expect(r2.reactionFor(O1)).toEqual({ expression: 'aliviado', motion: 'fade' })
    expect(r2.issues).toEqual([{ kind: 'opcion-cambiada', id: O2 }])
  })

  it('una opción o escena eliminada del caso se marca y se ignora', () => {
    const r = buildRuntime(manifest(), { escenarios: [{ ...content.escenarios[1]!, titulo: 'El pasillo' }] })
    expect(r.issues.map((i) => i.kind).sort()).toEqual(['escena-inexistente', 'opcion-inexistente', 'opcion-inexistente'])
    expect(r.reactionFor(O1)).toBeNull()
  })

  it('el borrador nuevo parte de las cinco expresiones editables y sin reacciones', () => {
    const m = emptyManifest({ id: CASE, nombre: 'Caso', ...content })
    expect(m.expressions.map((e) => e.label)).toEqual(['Neutral', 'Inquieto', 'Incómodo', 'Reflexivo', 'Aliviado'])
    expect(m.reactions).toEqual([])
  })
})

describe('expresión en escena', () => {
  it('cambia solo al llamar a react; si la siguiente decisión es de otra escena, la reacción se ve un instante', () => {
    vi.useFakeTimers()
    const runtime = buildRuntime(manifest(), content)
    const { result, rerender } = renderHook(({ scene }) => useStageExpression(runtime, scene), { initialProps: { scene: E1 } })
    expect(result.current.shown?.expression).toBe('neutral')

    act(() => result.current.react(O3, E1, E1)) // «Sin cambio»
    expect(result.current.shown?.expression).toBe('neutral')

    act(() => result.current.react(O2, E1, E2))
    rerender({ scene: E2 })
    expect(result.current.shown).toEqual({ expression: 'inquieto', motion: 'rise' })
    act(() => vi.advanceTimersByTime(CARRY_MS + 10))
    expect(result.current.shown?.expression).toBe('neutral')

    act(() => result.current.reset())
    expect(result.current.shown?.expression).toBe('neutral')
    vi.useRealTimers()
  })
})

// --- Simulador del estudiante con un paquete instalado -------------------------------------------------

type Reply = { status: number; body?: unknown }

function cuestionario(): Cuestionario {
  return {
    participacion_id: 'p1',
    estado: 'EN_PROGRESO',
    fecha_limite: '2026-11-19T10:00:00Z',
    tiempo_restante_segundos: 1200,
    caso: { nombre: 'Caso visual', desarrollo_situacional: null, historia: null },
    progreso: { total_preguntas: 2, respondidas: 0, pendientes: 2, porcentaje: 0 },
    escenarios: content.escenarios.map((e, i) => ({
      id: e.id,
      orden: i + 1,
      titulo: e.titulo,
      contexto: `Contexto ${i + 1}`,
      preguntas: e.preguntas.map((p, j) => ({
        id: p.id,
        orden: j + 1,
        enunciado: p.enunciado,
        opcion_seleccionada_id: null,
        opciones: p.opciones.map((o, k) => ({ id: o.id, orden: k + 1, texto: o.texto })),
      })),
    })),
  }
}

function mockFetch(handler: (url: string, init: RequestInit) => Reply | Promise<Reply> | undefined) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const r = (await handler(String(input), init)) ?? { status: 404, body: { detail: 'no mock' } }
      return new Response(r.body === undefined ? null : JSON.stringify(r.body), { status: r.status, headers: { 'Content-Type': 'application/json' } })
    }),
  )
}

function renderSimulator() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter([{ path: '/estudiante/caso/:participationId', element: <SimulatorPlayView /> }], { initialEntries: ['/estudiante/caso/p1'] })
  render(
    <QueryClientProvider client={qc}>
      <SessionProvider>
        <RouterProvider router={router} />
      </SessionProvider>
    </QueryClientProvider>,
  )
}

const spriteAlt = () => screen.getByRole('img', { name: /^Camila:/ }).getAttribute('alt')

describe('novela visual del estudiante', () => {
  beforeEach(() => {
    localStorage.setItem(
      'iter-animi.session',
      JSON.stringify({ kind: 'student', token: 'tok', expiresAt: Date.now() + 3_600_000, sesionId: 's1', convocatoriaId: 'c1', correo: 'e@u.co' }),
    )
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('seleccionar no reacciona, un error conserva la expresión y la reacción llega solo con la confirmación del servidor', async () => {
    let release: (r: Reply) => void = () => {}
    mockFetch((url, init) => {
      if (url.endsWith('/visual-packages/index.json')) return { status: 200, body: { version: 1, packages: [{ caseId: CASE, path: `${CASE}/manifest.json`, escenarioIds: [E1] }] } }
      if (url.endsWith(`/visual-packages/${CASE}/manifest.json`)) return { status: 200, body: manifest() }
      if (url.endsWith('/questionnaire')) return { status: 200, body: cuestionario() }
      if (init.method === 'PUT') return new Promise<Reply>((resolve) => (release = resolve))
    })
    renderSimulator()

    await waitFor(() => expect(spriteAlt()).toBe('Camila: Neutral'))
    await userEvent.click(screen.getByLabelText(/Opción B/))
    expect(spriteAlt()).toBe('Camila: Neutral')

    await userEvent.click(screen.getByRole('button', { name: 'Confirmar respuesta' }))
    release({ status: 500, body: null })
    expect(await screen.findByRole('alert')).toHaveTextContent('Tu selección se conservó')
    expect(spriteAlt()).toBe('Camila: Neutral')
    expect(screen.getByLabelText(/Opción B/)).toBeChecked()

    await userEvent.click(screen.getByRole('button', { name: 'Confirmar respuesta' }))
    release({ status: 200, body: { pregunta_id: Q1, opcion_id: O2, respondida_en: 'x', actualizada_en: 'x' } })
    await waitFor(() => expect(spriteAlt()).toBe('Camila: Inquieto'))
    expect(screen.getByText('¿Y ahora?')).toBeInTheDocument() // la siguiente decisión aparece sin esperar
  })

  it('sin paquete instalado el caso se juega con el personaje sin imagen', async () => {
    mockFetch((url) => {
      if (url.endsWith('/visual-packages/index.json')) return { status: 404, body: null }
      if (url.endsWith('/questionnaire')) return { status: 200, body: cuestionario() }
    })
    renderSimulator()
    expect(await screen.findByRole('button', { name: 'Confirmar respuesta' })).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /^Camila:/ })).toBeNull()
    // El monigote blanco ocupa el mismo hueco del personaje (decorativo, sin texto alternativo).
    expect(document.querySelector('.sim-character-slot .sim-sprite-fallback svg')).not.toBeNull()
  })
})
