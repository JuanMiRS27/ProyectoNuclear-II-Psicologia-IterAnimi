// Genera credenciales solo para la base aislada de Docker. Nunca sobrescribe un archivo existente.
import { randomBytes } from 'node:crypto'
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const target = fileURLToPath(new URL('../.env.docker', import.meta.url))
const aes = randomBytes(32).toString('base64').replaceAll('+', '-').replaceAll('/', '_')
const content = [
  '# Credenciales locales de Docker; no subir a Git ni regenerar con una base existente.',
  `POSTGRES_PASSWORD=${randomBytes(32).toString('hex')}`,
  `JWT_SECRET_KEY=${randomBytes(48).toString('hex')}`,
  `CONVOCATION_CODE_ENCRYPTION_KEY=${aes}`,
  'FRONTEND_PORT=8080',
  '',
].join('\n')

try {
  writeFileSync(target, content, { flag: 'wx', mode: 0o600 })
  console.log('Creado .env.docker con claves aleatorias. Conserva una copia segura.')
} catch (error) {
  if (error.code !== 'EEXIST') throw error
  console.log('.env.docker ya existe; se conserva sin cambios.')
}
