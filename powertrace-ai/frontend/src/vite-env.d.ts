/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Absolute origin of the PowerTrace AI API, for deployments that serve the
   * frontend and backend from different hosts (e.g. "https://api.example.com").
   * Leave unset when a reverse proxy puts both on one origin — that is the
   * preferred shape.
   */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
