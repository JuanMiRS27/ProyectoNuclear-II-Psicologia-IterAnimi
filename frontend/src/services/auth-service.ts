// Autenticación: personal (contraseña), estudiante (código de convocatoria) y consulta de resultados.
import type { ResultadosTokenResponse, StudentTokenResponse, TokenResponse, Usuario } from '../types/api'
import { request } from './http-client'

export const authService = {
  login: (correo: string, clave: string) =>
    request<TokenResponse>('/auth/login', { method: 'POST', body: { correo, clave }, token: null, skipAuthHandler: true }),
  me: (token?: string) => request<Usuario>('/auth/me', token ? { token, skipAuthHandler: true } : {}),
  studentLogin: (correo: string, codigo: string) =>
    request<StudentTokenResponse>('/auth/student/login', {
      method: 'POST',
      body: { correo, codigo },
      token: null,
      skipAuthHandler: true,
    }),
  resultsLogin: (correo: string, codigo: string) =>
    request<ResultadosTokenResponse>('/auth/student/results-login', {
      method: 'POST',
      body: { correo, codigo },
      token: null,
      skipAuthHandler: true,
    }),
  /** CU3. El servidor invalida todos los tokens anteriores, incluido el actual. */
  changePassword: (clave_actual: string, clave_nueva: string) =>
    request<void>('/auth/password', { method: 'PATCH', body: { clave_actual, clave_nueva } }),
} as const
