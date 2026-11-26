// Verificacion real del despliegue. Crea datos de demostracion identificados y finaliza su sesion.
// Requiere .env.initial-admin (ignorado por Git); nunca imprime claves, codigos ni tokens.
import assert from 'node:assert/strict'
import { randomBytes } from 'node:crypto'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { optionSignature, sceneSignature } from '../frontend/src/lib/visual/signature.ts'

const root = new URL('../', import.meta.url)
const credentialsFile = new URL('.env.initial-admin', root)
const credentials = Object.fromEntries(readFileSync(credentialsFile, 'utf8').split(/\r?\n/)
  .filter((line) => line && !line.startsWith('#')).map((line) => [line.slice(0, line.indexOf('=')), line.slice(line.indexOf('=') + 1)]))
credentials.TEACHER_EMAIL ??= 'docente.despliegue@example.com'
credentials.TEACHER_PASSWORD ??= `Ia!${randomBytes(24).toString('base64url')}`
credentials.STUDENT_EMAIL ??= 'estudiante.despliegue@example.com'
writeFileSync(credentialsFile, '# Credenciales de Iter Animi. No subir a Git.\n' + Object.entries(credentials).map(([k, v]) => `${k}=${v}`).join('\n') + '\n')

const web = process.env.PUBLIC_WEB_URL ?? 'https://iter-animi-web-5vqr.onrender.com'
const api = process.env.PUBLIC_API_URL ?? 'https://iter-animi-api-5vqr.onrender.com'
const checks = []
const check = (name) => { checks.push(name); console.log(`OK: ${name}`) }

async function request(path, { method = 'GET', token, body, expected = 200 } = {}) {
  const response = await fetch(`${api}/api/v1${path}`, {
    method, signal: AbortSignal.timeout(45000),
    headers: { Origin: web, ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  assert.ok([expected].flat().includes(response.status), `${method} ${path}: HTTP ${response.status}, esperado ${expected}`)
  assert.equal(response.headers.get('access-control-allow-origin'), web, 'Origen CORS incorrecto')
  return response.status === 204 ? null : response.json()
}

async function run() {
  const health = await fetch(`${api}/health`, { signal: AbortSignal.timeout(60000) })
  assert.equal(health.status, 200)
  assert.equal((await health.json()).status, 'ok')
  check('API publica saludable')

  for (const path of ['/ingresar', '/admin/usuarios', '/docente/casos']) {
    const response = await fetch(web + path)
    assert.equal(response.status, 200)
    assert.match(response.headers.get('content-type'), /text\/html/)
    const html = await response.text()
    assert.match(html, /id="root"/)
    if (path === '/ingresar') {
      const asset = html.match(/src="(\/assets\/index-[^"]+\.js)"/)
      assert.ok(asset, 'No se encontro el bundle principal')
      const bundle = await fetch(web + asset[1])
      assert.equal(bundle.status, 200)
      assert.ok((await bundle.text()).includes(`${api}/api/v1`), 'El frontend no apunta a la API publica')
    }
  }
  check('Frontend, rutas SPA y URL compilada de la API')
  const library = await (await fetch(`${web}/sprite-library/index.json`)).json()
  assert.ok(library.characters.length)
  const sprite = await fetch(`${web}/sprite-library/${library.characters[0].expressions[0].file}`)
  assert.equal(sprite.status, 200)
  assert.match(sprite.headers.get('content-type'), /image\//)
  check('Biblioteca de sprites accesible')

  const preflight = await fetch(`${api}/api/v1/auth/login`, { method: 'OPTIONS', headers: {
    Origin: web, 'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type,authorization',
  } })
  assert.equal(preflight.status, 200)
  assert.equal(preflight.headers.get('access-control-allow-origin'), web)
  const forbiddenOrigin = await fetch(`${api}/api/v1/auth/login`, { method: 'OPTIONS', headers: {
    Origin: 'https://origen-no-autorizado.example', 'Access-Control-Request-Method': 'POST',
  } })
  assert.equal(forbiddenOrigin.status, 400)
  assert.equal(forbiddenOrigin.headers.get('access-control-allow-origin'), null)
  await request('/auth/me', { expected: 401 })
  check('CORS autorizado y rechazo de acceso anonimo')

  const admin = (await request('/auth/login', { method: 'POST', body: { correo: credentials.ADMIN_EMAIL, clave: credentials.ADMIN_PASSWORD } })).access_token
  assert.equal((await request('/auth/me', { token: admin })).rol, 'ADMINISTRADOR')
  const users = await request('/users?limit=100', { token: admin })
  let teacher = users.items.find((u) => u.correo === credentials.TEACHER_EMAIL)
  teacher ??= await request('/users/teachers', { method: 'POST', token: admin, expected: 201, body: {
    nombre_completo: 'Docente de demostracion', correo: credentials.TEACHER_EMAIL, clave: credentials.TEACHER_PASSWORD,
  } })
  await request(`/users/${teacher.id}/case-permission`, { method: 'PATCH', token: admin, body: { puede_crear_casos: true } })
  if (!users.items.some((u) => u.correo === credentials.STUDENT_EMAIL)) {
    await request('/users/students', { method: 'POST', token: admin, expected: 201, body: {
      nombre_completo: 'Estudiante de demostracion', correo: credentials.STUDENT_EMAIL,
    } })
  }
  const spaces = await request('/academic-spaces', { token: admin })
  const space = spaces.items.find((s) => s.nombre === 'Demostracion de despliegue') ?? await request('/academic-spaces', {
    method: 'POST', token: admin, expected: 201, body: { nombre: 'Demostracion de despliegue', periodo: '2026-2' },
  })
  check('Administracion: acceso, usuarios, permisos y aula')

  const teacherToken = (await request('/auth/login', { method: 'POST', body: { correo: credentials.TEACHER_EMAIL, clave: credentials.TEACHER_PASSWORD } })).access_token
  await request('/users', { token: teacherToken, expected: 403 })
  const dsl = JSON.parse(readFileSync(new URL('docs/ejemplos/caso_conformidad_grupal.casedsl.json', root), 'utf8'))
  dsl.caso.nombre = 'Conformidad grupal - demostracion publica'
  const cases = await request('/cases?limit=100', { token: teacherToken })
  const existingCase = cases.items.find((c) => c.nombre === dsl.caso.nombre && c.estado !== 'ARCHIVADO')
  const academicCase = existingCase ? await request(`/cases/${existingCase.id}`, { token: teacherToken })
    : await request('/cases/full', { method: 'POST', token: teacherToken, body: dsl, expected: 201 })
  if (academicCase.estado === 'BORRADOR') await request(`/cases/${academicCase.id}/publish`, { method: 'POST', token: teacherToken })
  const now = Date.now()
  const sessions = await request('/sessions?limit=100', { token: teacherToken })
  const session = sessions.items.find((s) => s.caso_id === academicCase.id && ['EN_CURSO', 'SIN_INICIAR'].includes(s.estado))
    ?? await request('/sessions', { method: 'POST', token: teacherToken, expected: 201, body: {
    caso_id: academicCase.id, espacio_academico_id: space.id,
    inicio: new Date(now - 60000).toISOString(), fin: new Date(now + 3600000).toISOString(), tiempo_max_min: 10,
    mensaje: 'Datos de demostracion para verificar el despliegue.', estudiantes: [credentials.STUDENT_EMAIL],
  } })
  if (session.estado !== 'EN_CURSO') await request(`/sessions/${session.id}/start`, { method: 'POST', token: teacherToken })
  const convocations = await request(`/sessions/${session.id}/convocations`, { token: teacherToken })
  const code = await request(`/sessions/${session.id}/convocations/${convocations[0].id}/code`, { token: teacherToken })
  check('Docente: importar, publicar, programar y abrir sesion; codigo descifrado')

  const studentToken = (await request('/auth/student/login', { method: 'POST', body: { correo: credentials.STUDENT_EMAIL, codigo: code.codigo_autorizacion } })).access_token
  await request('/users', { token: studentToken, expected: 401 })
  const participation = await request(`/student/sessions/${session.id}/participations`, { method: 'POST', token: studentToken, expected: [200, 201] })
  const questionnaire = await request(`/student/participations/${participation.id}/questionnaire`, { token: studentToken })
  assert.ok(!JSON.stringify(questionnaire).includes('es_correcta'))
  for (const scene of questionnaire.escenarios) {
    for (const question of scene.preguntas) {
      await request(`/student/participations/${participation.id}/answers/${question.id}`, {
        method: 'PUT', token: studentToken, body: { opcion_id: question.opciones[0].id },
      })
    }
  }
  const resumed = await request(`/student/sessions/${session.id}/participations`, { method: 'POST', token: studentToken })
  assert.equal(resumed.id, participation.id)
  assert.equal(resumed.progreso.pendientes, 0)
  await request(`/student/participations/${participation.id}/finish`, { method: 'POST', token: studentToken })
  check('Estudiante: acceso, cuestionario seguro, respuestas, reanudacion y entrega')
  await request(`/sessions/${session.id}/evaluations/process`, { method: 'POST', token: teacherToken })
  await request(`/participations/${participation.id}/feedback`, { method: 'PATCH', token: teacherToken,
    body: { retroalimentacion_general: 'Recorrido de demostracion completado correctamente.' } })
  await request(`/sessions/${session.id}/finish`, { method: 'POST', token: teacherToken })
  const report = await request(`/sessions/${session.id}/reports/summary`, { token: teacherToken })
  assert.ok(report)
  const resultsToken = (await request('/auth/student/results-login', { method: 'POST', body: {
    correo: credentials.STUDENT_EMAIL, codigo: code.codigo_autorizacion,
  } })).access_token
  const result = await request(`/student/results/${participation.id}`, { token: resultsToken })
  assert.ok(result)
  check('Evaluacion, retroalimentacion, reportes y resultados del estudiante')

  // Paquete publico asociado a los ids creados en Neon; solo contiene direccion narrativa.
  const manifest = {
    format: 'iter-animi-paquete-visual', version: 2, case: { id: academicCase.id, nombre: academicCase.nombre },
    character: { name: 'Ines', defaultExpression: 'neutral', library: 'system-young-adult-f-01' },
    expressions: ['neutral', 'preocupado', 'reflexivo'].map((id) => ({ id, label: id, sprite: null })),
    scenes: academicCase.escenarios.map((s) => ({ escenarioId: s.id, signature: sceneSignature(s.titulo), initialExpression: 'neutral' })),
    reactions: academicCase.escenarios.flatMap((s) => s.preguntas.flatMap((p) => p.opciones.map((o, i) => ({
      opcionId: o.id, preguntaId: p.id, escenarioId: s.id, signature: optionSignature(p.enunciado, o.texto),
      expression: ['reflexivo', 'preocupado', null][i % 3], motion: 'fade',
    })))), createdAt: new Date().toISOString(),
  }
  const manifestFolder = new URL(`frontend/public/visual-packages/${academicCase.id}/`, root)
  mkdirSync(manifestFolder, { recursive: true })
  writeFileSync(new URL('manifest.json', manifestFolder), JSON.stringify(manifest, null, 2) + '\n')
  const summary = { api, web, caseId: academicCase.id, sessionId: session.id, participationId: participation.id, checks }
  writeFileSync(new URL('.env.smoke-state', root), JSON.stringify(summary, null, 2) + '\n')
  console.log(`Verificacion completada: ${checks.length} grupos de comprobaciones.`)
  console.log(`Paquete visual preparado: ${fileURLToPath(manifestFolder)}`)
}

run().catch((error) => { console.error(error.message); process.exitCode = 1 })
