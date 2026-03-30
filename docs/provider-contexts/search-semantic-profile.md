# Perfil Semántico De Búsqueda

El flujo de `ai-clientes` ya no trata la necesidad del cliente como texto plano.
Ahora la IA devuelve un perfil estructurado para mejorar la búsqueda semántica:

- `normalized_service`
- `domain`
- `category`

## Regla De Uso

- `normalized_service` es la señal principal de recuperación.
- `domain` y `category` se usan como contexto semántico enriquecido.
- El texto original del cliente se conserva como respaldo y trazabilidad.

## Cómo Se Usa

`ai-clientes` normaliza el perfil y lo envía a `ai-search` junto con:

- `problem_description`
- `service_candidate`
- `normalized_service`
- `domain_code`
- `category_name`
- sus variantes humanas (`domain`, `category`) cuando aplica

`ai-search` usa `normalized_service` + `domain_code` + `category_name` para
generar la query efectiva del embedding. `problem_description` queda como
contexto secundario para trazabilidad y reordenamiento, no para el embedding
principal.

## Capa De Precisión

Después del retrieval vectorial, `ai-search` reordena los candidatos con una
señal de alineación semántica universal que combina:

- similitud embebida
- coincidencia de dominio/categoría
- compatibilidad entre problema y servicio
- señales de confiabilidad del proveedor

Luego `ai-clientes` valida solo el subconjunto mejor priorizado para evitar
timeouts y reducir ruido de dominios claramente incompatibles.

## Intención Del Contrato

El objetivo no es clasificar por taxonomía solo por catálogo.
El objetivo es alinear el lenguaje del cliente con el lenguaje del proveedor
para que la búsqueda vectorial encuentre mejor coincidencias semánticas,
especialmente cuando el cliente describe el problema con otras palabras.

## Regla De Prueba

Cuando se valide el flujo de `ai-clientes`, cada intención debe probarse
aisladamente:

- limpiar el estado del teléfono antes de cada caso
- enviar una sola solicitud por flujo
- confirmar con `sí` solo cuando el caso lo requiera

Esto evita que una conversación anterior contamine la siguiente y hace que
la regresión del bot sea reproducible.
