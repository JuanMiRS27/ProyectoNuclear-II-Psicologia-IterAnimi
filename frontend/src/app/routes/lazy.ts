import type { ComponentType } from 'react'
import type { RouteObject } from 'react-router'

/**
 * Carga diferida de una vista de módulo: cada portal descarga solo su código.
 * `name` es el export con nombre del módulo (todas las vistas usan exports con nombre).
 */
export function view<M extends Record<string, unknown>>(importer: () => Promise<M>, name: keyof M & string): Pick<RouteObject, 'lazy'> {
  return {
    lazy: async () => ({ Component: (await importer())[name] as ComponentType }),
  }
}
