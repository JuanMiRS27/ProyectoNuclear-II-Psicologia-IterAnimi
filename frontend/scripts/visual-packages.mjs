#!/usr/bin/env node
// Instalación de paquetes visuales en el frontend antes de desplegar.
//
//   npm run visual:install -- ruta/paquete-visual-<caso>.zip   valida e instala en public/visual-packages/<caso>/
//   npm run visual:index                                        regenera public/visual-packages/index.json
//   npm run visual:remove -- <id-del-caso>                      retira un paquete instalado
//
// La lógica vive en scripts/visual-packages-lib.mjs (la comparte el botón «Guardar y publicar» del editor a través del
// servidor del frontend). `npm run build` ejecuta `visual:index` antes de compilar (prebuild).
import { readFile } from 'node:fs/promises'
import { installPackage, rebuildIndex, removePackage } from './visual-packages-lib.mjs'

const warn = (m) => console.warn(m)

async function install(zipPath) {
  if (!zipPath) throw new Error('Indica la ruta del paquete .zip exportado desde el editor.')
  const r = await installPackage(new Uint8Array(await readFile(zipPath)))
  r.warnings.forEach((w) => console.warn(`Aviso: ${w}`))
  const origin = r.manifest.character.library ? `personaje del sistema ${r.manifest.character.library}` : `${r.images} imágenes`
  console.log(`Instalado: ${r.manifest.case.nombre} (${r.manifest.case.id}) con ${origin}.`)
  console.log(`Índice de paquetes visuales: ${r.installed} instalado(s).`)
}

async function index() {
  console.log(`Índice de paquetes visuales: ${await rebuildIndex(undefined, warn)} instalado(s).`)
}

async function remove(caseId) {
  const n = await removePackage(caseId)
  console.log(`Paquete retirado: ${caseId}`)
  console.log(`Índice de paquetes visuales: ${n} instalado(s).`)
}

const [cmd, arg] = process.argv.slice(2)
const actions = { install: () => install(arg), index, remove: () => remove(arg) }
if (!actions[cmd]) {
  console.error('Uso: visual-packages.mjs install <paquete.zip> | index | remove <id-del-caso>')
  process.exit(2)
}
actions[cmd]().catch((err) => {
  console.error(`Error: ${err.message}`)
  process.exit(1)
})
