import { useEffect, useMemo, useRef, useState } from 'react'
import { Notice } from '../../../components/design-system/layout'
import { InlineError, LoadingState } from '../../../components/design-system/states'
import { Button } from '../../../components/ui/Button'
import { ConfirmDialog } from '../../../components/ui/Dialog'
import { useDeleteVisualDraft, useSaveVisualDraft, useSpriteLibrary, useVisualDraft } from '../../../hooks/use-visual'
import { formatDateTime } from '../../../lib/format'
import { libraryUrls, remapToExpressions, systemExpressions, type LibraryCharacter, type RemapReport } from '../../../lib/visual/library'
import { buildPackage, parsePackage, PackageError } from '../../../lib/visual/package'
import { buildRuntime, emptyManifest } from '../../../lib/visual/runtime'
import { DEFAULT_EXPRESSIONS, type VisualDraft, type VisualManifest } from '../../../lib/visual/types'
import type { CasoDetalle } from '../../../types/api'
import { ScenePreview } from '../../simulator/ScenePreview'
import { CharacterPanel } from './CharacterPanel'
import { ReactionsPanel } from './ReactionsPanel'

type Zone = 'personaje' | 'reacciones' | 'vista'

function download(bytes: Uint8Array, name: string) {
  const url = URL.createObjectURL(new Blob([bytes as BlobPart], { type: 'application/zip' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Pestaña «Personaje y reacciones» del caso. Lo editado aquí vive en este navegador hasta exportarlo. */
export function VisualEditor({ caso }: { caso: CasoDetalle }) {
  const stored = useVisualDraft(caso.id)
  if (stored.isPending) return <LoadingState label="Cargando el borrador visual…" />
  if (stored.isError) return <InlineError error={stored.error} />
  return <Editor key={caso.id} caso={caso} initial={stored.data ?? null} />
}

function Editor({ caso, initial }: { caso: CasoDetalle; initial: VisualDraft | null }) {
  const save = useSaveVisualDraft(caso.id)
  const remove = useDeleteVisualDraft(caso.id)
  const [manifest, setManifest] = useState<VisualManifest>(() => initial?.manifest ?? emptyManifest(caso))
  const [images, setImages] = useState<Record<string, Blob>>(() => initial?.images ?? {})
  const [dirty, setDirty] = useState(false)
  const [zone, setZone] = useState<Zone>('personaje')
  const [notice, setNotice] = useState<{ tone: 'ok' | 'error' | 'info' | 'warn'; text: string } | null>(null)
  const [confirmImport, setConfirmImport] = useState<{ manifest: VisualManifest; images: Record<string, Blob> } | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const [savedAt, setSavedAt] = useState<string | null>(initial?.savedAt ?? null)
  const [stash, setStash] = useState<VisualDraft['stash']>(initial?.stash ?? null)
  const library = useSpriteLibrary()
  const systemId = manifest.character.library ?? null

  // URLs temporales de las imágenes del borrador. Se crean y liberan en el mismo efecto para que el doble
  // montaje de StrictMode no deje URLs ya revocadas.
  const [objectUrls, setUrls] = useState<Record<string, string>>({})
  useEffect(() => {
    const created = Object.fromEntries(Object.entries(images).map(([k, b]) => [k, URL.createObjectURL(b)]))
    // Sincroniza con un recurso externo (URLs de objeto del navegador) que debe crearse y liberarse en pareja.
    // oxlint-disable-next-line react/set-state-in-effect
    setUrls(created)
    return () => Object.values(created).forEach((u) => URL.revokeObjectURL(u))
  }, [images])

  // Personaje del sistema: URLs de la biblioteca estática. Sprites propios: URLs temporales de los Blob del borrador.
  const urls = useMemo<Record<string, string | null>>(
    () => (systemId ? libraryUrls(library.data ?? null, manifest) : objectUrls),
    [systemId, library.data, manifest, objectUrls],
  )
  const runtime = useMemo(() => buildRuntime(manifest, caso), [manifest, caso])
  const orphans = runtime.issues.filter((i) => i.kind === 'opcion-inexistente' || i.kind === 'escena-inexistente')
  const changed = runtime.issues.filter((i) => i.kind === 'opcion-cambiada' || i.kind === 'escena-cambiada')

  const change = (next: VisualManifest, img?: { set?: Record<string, Blob>; remove?: string[] }) => {
    setManifest(next)
    if (img) {
      setImages((prev) => {
        const copy = { ...prev, ...(img.set ?? {}) }
        for (const id of img.remove ?? []) delete copy[id]
        // Las imágenes de expresiones eliminadas no se conservan.
        for (const id of Object.keys(copy)) if (!next.expressions.some((e) => e.id === id)) delete copy[id]
        return copy
      })
    }
    setDirty(true)
    setNotice(null)
  }

  const describe = (r: RemapReport, next: VisualManifest) => {
    const all = [...next.expressions, ...manifest.expressions, ...DEFAULT_EXPRESSIONS]
    const label = (id: string) => all.find((e) => e.id === id)?.label ?? id
    const parts: string[] = []
    if (r.remapped.length) parts.push(`Equivalencias aplicadas: ${r.remapped.map(([a, b]) => `${label(a)} → ${label(b)}`).join(', ')}.`)
    if (r.dropped.length) parts.push(`Sin equivalente (vuelven a «Sin cambio» o a la expresión por defecto): ${r.dropped.map(label).join(', ')}.`)
    return parts.join(' ')
  }

  const applySystem = (ch: LibraryCharacter) => {
    // Los sprites propios se apartan para poder volver a ellos; los del sistema no se copian al borrador.
    if (!systemId) setStash({ expressions: manifest.expressions, images, defaultExpression: manifest.character.defaultExpression })
    const keepDefault = ch.expressions.some((e) => e.id === manifest.character.defaultExpression)
    const { manifest: next, report } = remapToExpressions(manifest, systemExpressions(ch), keepDefault ? manifest.character.defaultExpression : ch.defaultExpression, ch.id)
    // El nombre sigue al personaje salvo que el docente haya escrito uno propio.
    const current = manifest.character.name.trim()
    const previousName = library.data?.characters.find((c) => c.id === systemId)?.name
    const name = !current || current === previousName ? ch.name : manifest.character.name
    setManifest({ ...next, character: { ...next.character, name } })
    setImages({})
    setDirty(true)
    setNotice({ tone: 'ok', text: `Personaje del sistema: ${ch.name}. Se conservaron las asociaciones compatibles. ${describe(report, next)}`.trim() })
  }

  const applyCustom = () => {
    const expressions = stash?.expressions ?? DEFAULT_EXPRESSIONS.map((e) => ({ ...e, sprite: null }))
    const { manifest: next, report } = remapToExpressions(manifest, expressions, stash?.defaultExpression ?? 'neutral', null)
    setManifest(next)
    setImages(stash?.images ?? {})
    setStash(null)
    setDirty(true)
    setNotice({ tone: 'ok', text: `De vuelta a tus sprites propios. ${describe(report, next)}`.trim() })
  }

  const onSave = () =>
    save.mutate(
      { manifest, images: systemId ? {} : images, stash },
      {
        onSuccess: (saved) => {
          setDirty(false)
          setSavedAt(saved.savedAt ?? null)
          setNotice({ tone: 'ok', text: 'Borrador visual guardado en este navegador.' })
        },
      },
    )

  const onExport = async () => {
    setNotice(null)
    try {
      const bytes = await buildPackage(manifest, images)
      download(bytes, `paquete-visual-${caso.id}.zip`)
      setNotice({
        tone: 'info',
        text: 'Paquete exportado. Para que lo vean los estudiantes hay que instalarlo en el frontend antes de desplegar (ver la guía de paquetes visuales).',
      })
    } catch (err) {
      setNotice({ tone: 'error', text: err instanceof PackageError ? err.message : 'No se pudo exportar el paquete.' })
    }
  }

  const onImport = async (file: File | undefined) => {
    setNotice(null)
    if (!file) return
    try {
      const parsed = await parsePackage(new Uint8Array(await file.arrayBuffer()))
      if (parsed.manifest.case.id !== caso.id)
        throw new PackageError(`Este paquete es del caso «${parsed.manifest.case.nombre}», no de este. No se importó.`)
      if (parsed.manifest.character.library && library.data && !library.data.characters.some((c) => c.id === parsed.manifest.character.library))
        setNotice({ tone: 'warn', text: `El paquete usa el personaje del sistema «${parsed.manifest.character.library}», que no está en esta versión de la biblioteca. Se mostrará el personaje sin rostro hasta instalarlo.` })
      const imgs: Record<string, Blob> = {}
      for (const e of parsed.manifest.expressions)
        if (e.sprite) imgs[e.id] = new Blob([parsed.files[e.sprite]! as BlobPart], { type: e.sprite.endsWith('.png') ? 'image/png' : 'image/webp' })
      setConfirmImport({ manifest: parsed.manifest, images: imgs })
    } catch (err) {
      setNotice({ tone: 'error', text: err instanceof PackageError ? err.message : 'No se pudo leer el paquete.' })
    }
  }

  const dropOrphans = () => {
    const bad = new Set(orphans.map((o) => o.id))
    change({ ...manifest, reactions: manifest.reactions.filter((r) => !bad.has(r.opcionId)), scenes: manifest.scenes.filter((s) => !bad.has(s.escenarioId)) })
  }

  return (
    <div className="visual-editor">
      <div className="visual-bar">
        <div className="visual-status" role="status">
          {dirty ? (
            <span className="status-dot pending">Cambios sin guardar</span>
          ) : savedAt ? (
            <span className="status-dot saved">Guardado en este navegador el {formatDateTime(savedAt)}</span>
          ) : (
            <span className="status-dot">Aún no hay un borrador guardado</span>
          )}
        </div>
        <div className="btn-row">
          <Button variant="primary" onClick={onSave} pending={save.isPending} pendingLabel="Guardando…" disabled={!dirty && Boolean(savedAt)}>
            Guardar borrador
          </Button>
          <Button icon="download" onClick={() => void onExport()}>
            Exportar paquete visual
          </Button>
          <Button icon="upload" onClick={() => fileRef.current?.click()}>
            Importar paquete visual
          </Button>
          <input ref={fileRef} type="file" accept=".zip,application/zip" className="visually-hidden" aria-label="Archivo del paquete visual" onChange={(e) => {
            void onImport(e.target.files?.[0])
            e.target.value = ''
          }} />
          {savedAt && (
            <Button variant="quiet" icon="trash" onClick={() => setConfirmDelete(true)}>
              Descartar borrador
            </Button>
          )}
        </div>
      </div>

      {notice && <Notice tone={notice.tone}>{notice.text}</Notice>}
      <InlineError error={save.error} />
      <Notice tone="info" title="Qué se guarda y qué se distribuye">
        «Guardar borrador» lo conserva solo en este navegador. Para que lo vean los estudiantes: exporta el paquete, instálalo en el frontend con{' '}
        <code>npm run visual:install</code> y despliega. Publicar el caso no publica su paquete visual.
      </Notice>
      {orphans.length > 0 && (
        <Notice tone="warn" title={`Hay ${orphans.length} asociaciones que ya no existen en el caso.`}>
          Se ignoran en el simulador (se usa la expresión inicial).{' '}
          <button type="button" className="link-btn" onClick={dropOrphans}>
            Quitarlas del borrador
          </button>
        </Notice>
      )}
      {changed.length > 0 && (
        <Notice tone="warn" title={`${changed.length} reacciones pendientes de revisión.`}>
          El texto del caso cambió después de asignarlas. Hasta que las confirmes, el simulador mostrará la expresión inicial.
        </Notice>
      )}

      <div className="segmented visual-tabs" role="tablist" aria-label="Zonas del editor">
        {(
          [
            ['personaje', 'Personaje'],
            ['reacciones', 'Reacciones'],
            ['vista', 'Vista previa'],
          ] as const
        ).map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={zone === id} className={zone === id ? 'is-active' : undefined} onClick={() => setZone(id)}>
            {label}
          </button>
        ))}
      </div>

      <div className="visual-layout" data-zone={zone}>
        <div className="visual-config">
          <div className="zone-personaje">
            <CharacterPanel
              manifest={manifest}
              urls={objectUrls}
              onChange={change}
              catalog={library.data}
              catalogLoading={library.isPending}
              onUseSystem={applySystem}
              onUseCustom={applyCustom}
              hasStash={Boolean(stash)}
            />
          </div>
          <div className="zone-reacciones">
            <ReactionsPanel caso={caso} manifest={manifest} runtime={runtime} onChange={(m) => change(m)} />
          </div>
        </div>
        <aside className="visual-preview zone-vista" aria-labelledby="h-vista">
          <h3 id="h-vista">Vista previa jugable</h3>
          <ScenePreview caso={caso} runtime={runtime} spriteUrls={urls} />
        </aside>
      </div>

      <ConfirmDialog
        open={Boolean(confirmImport)}
        title="¿Reemplazar el borrador con el paquete?"
        confirmLabel="Importar"
        onConfirm={() => {
          if (!confirmImport) return
          setManifest(confirmImport.manifest)
          setImages(confirmImport.images)
          setStash(null)
          setDirty(true)
          setConfirmImport(null)
          setNotice((prev) =>
            prev?.tone === 'warn' ? prev : { tone: 'ok', text: 'Paquete importado. Revisa las asociaciones y guarda el borrador para conservarlo.' },
          )
        }}
        onClose={() => setConfirmImport(null)}
      >
        <p>Se reemplazarán el personaje, las imágenes y las reacciones que tienes ahora en pantalla.</p>
      </ConfirmDialog>
      <ConfirmDialog
        open={confirmDelete}
        title="¿Descartar el borrador visual?"
        confirmLabel="Descartar"
        danger
        pending={remove.isPending}
        onConfirm={() =>
          remove.mutate(undefined, {
            onSuccess: () => {
              setConfirmDelete(false)
              setManifest(emptyManifest(caso))
              setImages({})
              setStash(null)
              setSavedAt(null)
              setDirty(false)
              setNotice({ tone: 'info', text: 'Borrador visual descartado de este navegador.' })
            },
          })
        }
        onClose={() => setConfirmDelete(false)}
      >
        <p>Se borrará de este navegador. No afecta al caso ni a paquetes ya instalados en el frontend.</p>
      </ConfirmDialog>
    </div>
  )
}
