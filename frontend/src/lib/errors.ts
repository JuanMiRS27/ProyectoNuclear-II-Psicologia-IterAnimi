import { ApiError } from '../services/http-client'

export function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message
  return 'Ocurrió un error inesperado.'
}
