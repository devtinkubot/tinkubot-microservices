defmodule ProviderOnboardingWorker.ServiceClassifier do
  alias ProviderOnboardingWorker.OpenAIClient
  alias ProviderOnboardingWorker.SupabaseClient
  require Logger

  @system_prompt """
  Eres un clasificador de servicios para proveedores en Ecuador.
  Tu tarea es analizar el texto que describe un servicio y devolver SIEMPRE:
  - Un nombre normalizado y claro del servicio (normalized_service)
  - El dominio al que pertenece (domain_code), usando los códigos del catálogo
  - Una categoría específica dentro del dominio (category_name)
  - Un resumen breve operativo del servicio (service_summary)
  - Un nivel de confianza de 0.0 a 1.0 (confidence)

  Reglas obligatorias:
  - SIEMPRE asigna un domain_code y un category_name, incluso si el texto es vago.
    Usa el dominio y categoría más cercana según tu criterio.
  - normalized_service debe ser legible, en español neutro, máximo 80 caracteres.
    Nunca devuelvas un oficio puro (plomero, contador) — devuelve el servicio concreto.
  - service_summary es una frase operativa breve de lo que hace el proveedor.
  - confidence refleja qué tan claro es el servicio en el texto (0.9 = muy claro, 0.5 = interpretado).
  - La salida SIEMPRE es JSON estricto, sin texto adicional.
  - Nunca dejes domain_code ni category_name en null o vacío.
  """

  def classify(raw_text) when is_binary(raw_text) do
    text = String.trim(raw_text)

    cond do
      String.length(text) < 2 -> {:error, :text_too_short}
      String.length(text) > 300 -> {:error, :text_too_long}
      heuristic_reject?(text) -> {:error, :invalid_service_text}
      true -> do_classify(text)
    end
  end

  defp do_classify(text) do
    domains_prompt = fetch_domain_catalog() |> build_domains_prompt()

    user_prompt =
      "Clasifica este servicio:\n" <>
        "\"#{text}\"\n\n" <>
        "Catálogo de dominios disponibles (usa estos códigos exactos para domain_code):\n" <>
        domains_prompt <>
        "\n\nResponde SOLO con este JSON:\n" <>
        "{" <>
        "\"normalized_service\": \"nombre claro del servicio\"," <>
        "\"domain_code\": \"código del catálogo\"," <>
        "\"category_name\": \"categoría específica\"," <>
        "\"service_summary\": \"resumen operativo breve\"," <>
        "\"confidence\": 0.0" <>
        "}"

    case OpenAIClient.chat_completion(@system_prompt, user_prompt) do
      {:ok, json_text} ->
        case Jason.decode(json_text) do
          {:ok, result} ->
            {:ok, build_result(text, result)}

          _ ->
            Logger.warning("ServiceClassifier: no se pudo parsear JSON de OpenAI: #{inspect(json_text)}")
            {:ok, fallback_result(text)}
        end

      {:error, reason} ->
        Logger.warning("ServiceClassifier: error OpenAI: #{inspect(reason)}")
        {:error, reason}
    end
  end

  defp fetch_domain_catalog do
    case SupabaseClient.fetch_service_domains() do
      {:ok, %{body: domains}} when is_list(domains) and length(domains) > 0 -> domains
      _ -> []
    end
  end

  defp build_domains_prompt([]), do: "Sin catálogo — asigna el dominio y categoría según tu criterio."

  defp build_domains_prompt(domains) do
    domains
    |> Enum.take(40)
    |> Enum.map_join("\n", fn d ->
      desc = if d["description"] && d["description"] != "", do: " (#{d["description"]})", else: ""
      "- #{d["code"]}: #{d["display_name"]}#{desc}"
    end)
  end

  defp build_result(raw_text, result) do
    normalized = to_string_safe(result["normalized_service"]) |> default_if_blank(raw_text)
    summary = to_string_safe(result["service_summary"]) |> default_if_blank(normalized)
    domain = to_string_safe(result["domain_code"]) |> nil_if_blank()
    category = to_string_safe(result["category_name"]) |> nil_if_blank()
    confidence = to_float(result["confidence"])

    %{
      "service_name" => normalized,
      "service_summary" => summary,
      "domain_code" => domain,
      "category_name" => category,
      "classification_confidence" => confidence,
      "raw_service_text" => raw_text
    }
  end

  defp fallback_result(raw_text) do
    %{
      "service_name" => raw_text,
      "service_summary" => raw_text,
      "domain_code" => nil,
      "category_name" => nil,
      "classification_confidence" => 0.0,
      "raw_service_text" => raw_text
    }
  end

  defp heuristic_reject?(text) do
    normalized = text |> String.downcase() |> String.trim()
    normalized in ~w(hola buenas gracias ok okay info ayuda test prueba servicio servicios varios general)
  end

  defp to_string_safe(nil), do: ""
  defp to_string_safe(v), do: to_string(v) |> String.trim()

  defp default_if_blank("", default), do: default
  defp default_if_blank(v, _), do: v

  defp nil_if_blank(""), do: nil
  defp nil_if_blank(v), do: v

  defp to_float(nil), do: 0.0
  defp to_float(v) when is_float(v), do: v
  defp to_float(v) when is_integer(v), do: v * 1.0
  defp to_float(v) do
    case Float.parse(to_string(v)) do
      {f, _} -> f
      :error -> 0.0
    end
  end
end
