// Copyright (c) 2026 Almoon-D. All rights reserved.
// The Spanish catalogue: every string the page shows. `{name}` is replaced by `t`.
export const es = {
  "app.title": "Subphora",
  "app.tagline": "Parcela catastral sobre la ortofoto PNOA",
  "app.loading": "Cargando el mapa…",
  "app.mapUnavailable": "No se ha podido cargar la configuración del mapa. Comprueba que el servidor de Subphora está en marcha.",

  "search.label": "Referencia catastral",
  "search.placeholder": "p. ej. 7279701NH3477G",
  "search.hint": "14 o 20 caracteres, rústica o urbana.",
  "search.submit": "Buscar",
  "search.searching": "Buscando…",
  "search.empty": "Escribe una referencia catastral.",

  "error.malformed_reference": "La referencia catastral no es válida: revisa que tenga 14 o 20 caracteres y, si tiene 20, que las dos letras finales sean las correctas.",
  "error.territory_not_supported": "Esta parcela está en Navarra o en el País Vasco, que tienen catastro propio (foral). Su consulta aún no está disponible.",
  "error.parcel_not_found": "Catastro no tiene ninguna parcela con esa referencia.",
  "error.upstream_timeout": "Catastro no ha respondido a tiempo. Vuelve a intentarlo en unos minutos.",
  "error.upstream_error": "Catastro ha respondido con un error. Vuelve a intentarlo más tarde.",
  "error.network": "No se puede conectar con el servidor de Subphora.",
  "error.unexpected": "El servidor ha dado una respuesta inesperada.",

  "parcel.heading": "Parcela {reference}",
  "parcel.place": "{municipality} ({province})",
  "parcel.area": "Superficie catastral: {area}",
  "parcel.point": "Punto de referencia ({crs}): X {x}, Y {y}",
  "parcel.precision": "El contorno es el del plano catastral, con la precisión de su escala de captura; no es un levantamiento topográfico.",
  "parcel.sources": "Fuente: {sources}, consultado el {date}.",

  "map.cadastreHidden": "Acerca el mapa para ver las parcelas catastrales.",
} as const;

export type MessageKey = keyof typeof es;
