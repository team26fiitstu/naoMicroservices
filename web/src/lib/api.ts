// Base URL of the backend. Empty = same origin, nginx (or the Vite dev proxy) routes requests to the services.
export const API_BASE = import.meta.env.VITE_API_BASE ?? "";