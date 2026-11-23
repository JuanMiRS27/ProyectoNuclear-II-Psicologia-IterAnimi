import { describe, expect, it } from 'vitest'
import { libraryUrls, remapToExpressions, systemExpressions, validateCatalog, type LibraryCatalog } from '../lib/visual/library'
import { buildPackage, PackageError, parsePackage, validateManifest } from '../lib/visual/package'
import { PACKAGE_FORMAT, type VisualManifest } from '../lib/visual/types'
import shipped from '../../public/sprite-library/index.json'

const CASE = '00000000-0000-4000-8000-000000000001'
const E1 = '00000000-0000-4000-8000-0000000000e1'
const Q1 = '00000000-0000-4000-8000-0000000000a1'
const O1 = '00000000-0000-4000-8000-0000000000b1'
const O2 = '00000000-0000-4000-8000-0000000000b2'
const O3 = '00000000-0000-4000-8000-0000000000b3'

// El catálogo real que se despliega con el frontend.
const catalog = validateCatalog(shipped) as LibraryCatalog
const REQUIRED = ['neutral', 'feliz', 'triste', 'enojado', 'preocupado', 'sorprendido', 'incomodo', 'reflexivo']

function customManifest(): VisualManifest {
  return {
    format: PACKAGE_FORMAT,
    version: 1,
    case: { id: CASE, nombre: 'Caso' },
    character: { name: 'Camila', defaultExpression: 'neutral' },
    expressions: [
      { id: 'neutral', label: 'Neutral', sprite: null },
      { id: 'inquieto', label: 'Inquieto', sprite: null },
      { id: 'aliviado', label: 'Aliviado', sprite: null },
      { id: 'pensativa', label: 'Pensativa', sprite: null },
    ],
    scenes: [{ escenarioId: E1, signature: 'aaaaaaaa', initialExpression: 'inquieto' }],
    reactions: [
      { opcionId: O1, preguntaId: Q1, escenarioId: E1, signature: 'bbbbbbbb', expression: 'inquieto', motion: 'fade' },
      { opcionId: O2, preguntaId: Q1, escenarioId: E1, signature: 'cccccccc', expression: 'aliviado', motion: 'rise' },
      { opcionId: O3, preguntaId: Q1, escenarioId: E1, signature: 'dddddddd', expression: 'pensativa', motion: 'fade' },
    ],
    createdAt: '2026-11-20T00:00:00.000Z',
  }
}

describe('biblioteca de personajes del sistema', () => {
  it('el catálogo desplegado tiene seis perfiles con ids estables y las ocho expresiones mínimas', () => {
    expect(catalog.characters.map((c) => c.id)).toEqual([
      'system-young-adult-m-01',
      'system-young-adult-f-01',
      'system-adult-m-01',
      'system-adult-f-01',
      'system-older-m-01',
      'system-older-f-01',
    ])
    for (const c of catalog.characters) {
      expect(c.expressions.map((e) => e.id)).toEqual(REQUIRED)
      // Cada expresión es un archivo dentro de la carpeta del mismo personaje.
      for (const e of c.expressions) expect(e.file.startsWith(`${c.id}/`)).toBe(true)
    }
  })

  it('el catálogo rechaza rutas externas o fuera de la carpeta del personaje', () => {
    const bad = validateCatalog({
      version: 1,
      characters: [
        {
          id: 'system-x-01',
          name: 'X',
          expressions: [
            { id: 'neutral', label: 'N', file: 'https://cdn.example.com/a.png' },
            { id: 'feliz', label: 'F', file: '../secreto.png' },
            { id: 'triste', label: 'T', file: 'system-otro-01/triste.png' },
          ],
        },
      ],
    })
    expect(bad?.characters).toEqual([])
  })

  it('elegir un personaje del sistema conserva lo compatible, remapea equivalencias y no copia imágenes', async () => {
    const ines = catalog.characters.find((c) => c.id === 'system-young-adult-f-01')!
    const { manifest, report } = remapToExpressions(customManifest(), systemExpressions(ines), 'neutral', ines.id)
    expect(manifest.character.library).toBe(ines.id)
    expect(manifest.reactions.map((r) => r.expression)).toEqual(['preocupado', 'feliz'])
    expect(manifest.scenes[0]!.initialExpression).toBe('preocupado')
    expect(report).toEqual({ remapped: [['inquieto', 'preocupado'], ['aliviado', 'feliz']], dropped: ['pensativa'] })

    // El paquete exportado solo lleva la referencia: versión 2, sin sprites ni archivos de imagen.
    const parsed = await parsePackage(await buildPackage(manifest, { neutral: new Blob([new Uint8Array([1, 2, 3])]) }))
    expect(parsed.manifest.version).toBe(2)
    expect(parsed.manifest.character.library).toBe(ines.id)
    expect(parsed.manifest.expressions.every((e) => e.sprite === null)).toBe(true)
    expect(Object.keys(parsed.files)).toEqual([])
  })

  it('las URLs salen de la biblioteca estática; un personaje o expresión ausente cae en el personaje sin rostro', () => {
    const ines = catalog.characters.find((c) => c.id === 'system-young-adult-f-01')!
    const { manifest } = remapToExpressions(customManifest(), systemExpressions(ines), 'neutral', ines.id)
    const urls = libraryUrls(catalog, manifest)
    expect(urls.preocupado).toMatch(/\/sprite-library\/system-young-adult-f-01\/preocupado\.svg$/)
    expect(libraryUrls(catalog, { ...manifest, character: { ...manifest.character, library: 'system-missing-01' } }).neutral).toBeNull()
    expect(libraryUrls(null, manifest).neutral).toBeNull()
  })

  it('valida la referencia: id de sistema bien formado, solo en versión 2 y sin imágenes propias', () => {
    const base = { ...customManifest(), version: 2 as const }
    expect(() => validateManifest({ ...base, character: { ...base.character, library: '../../etc' } })).toThrow(PackageError)
    expect(() => validateManifest({ ...base, version: 1, character: { ...base.character, library: 'system-young-adult-f-01' } })).toThrow(PackageError)
    const withSprite = { ...base, character: { ...base.character, library: 'system-young-adult-f-01' }, expressions: [{ id: 'neutral', label: 'N', sprite: 'sprites/neutral.png' }] }
    expect(() => validateManifest(withSprite)).toThrow(PackageError)
    // Los paquetes de la versión 1 siguen siendo válidos.
    expect(validateManifest(customManifest()).version).toBe(1)
  })
})
