interface OpcionesSolicitud extends RequestInit {
  parsearJson?: boolean;
}

export async function realizarSolicitudHttp<T = unknown>(
  recurso: RequestInfo | URL,
  opciones: OpcionesSolicitud = {}
): Promise<T> {
  const { parsearJson = true, headers, ...resto } = opciones;

  const respuesta = await fetch(recurso, {
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      ...(headers ?? {})
    },
    ...resto
  });

  const cuerpo = parsearJson ? await respuesta.json().catch(() => null) : null;

  if (!respuesta.ok) {
    const mensaje =
      (cuerpo &&
        typeof cuerpo === 'object' &&
        'error' in cuerpo &&
        typeof (cuerpo as { error?: unknown }).error === 'string'
        ? (cuerpo as { error: string }).error
        : undefined) ||
      (cuerpo &&
        typeof cuerpo === 'object' &&
        'message' in cuerpo &&
        typeof (cuerpo as { message?: unknown }).message === 'string'
        ? (cuerpo as { message: string }).message
        : undefined) ||
      respuesta.statusText ||
      'Solicitud fallida';

    throw new Error(mensaje);
  }

  return (cuerpo as T) ?? (null as T);
}
