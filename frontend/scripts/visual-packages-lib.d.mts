// Tipos de scripts/visual-packages-lib.mjs (lo importa el plugin del servidor del frontend desde vite.config.ts).
export declare const PUBLIC_PACKAGES: string
export interface InstallResult {
  manifest: { case: { id: string; nombre: string }; character: { name: string; library?: string | null } }
  images: number
  warnings: string[]
  installed: number
}
export declare function libraryWarnings(manifest: unknown): Promise<string[]>
export declare function installPackage(bytes: Uint8Array, root?: string): Promise<InstallResult>
export declare function rebuildIndex(root?: string, log?: (message: string) => void): Promise<number>
export declare function removePackage(caseId: string, root?: string): Promise<number>
