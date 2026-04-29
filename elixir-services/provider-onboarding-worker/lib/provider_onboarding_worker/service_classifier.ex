defmodule ProviderOnboardingWorker.ServiceClassifier do
  @moduledoc """
  Clasifica servicios de onboarding usando OpenAI y el catálogo de dominios
  de Supabase. Reemplaza la dependencia en ai-proveedores Python.
  """

  alias ProviderOnboardingWorker.OpenAIClient
  alias ProviderOnboardingWorker.SupabaseClient
  require Logger

  @system_prompt """
  Eres un clasificador obligatorio de servicios para proveedores en Ecuador.
  Tu trabajo es cerrar un servicio operativo, su dominio y su categoría
  sin dejar campos vacíos cuando el texto sí permite resolverlos.
  El usuario envía un servicio por WhatsApp y el texto ya pasó por
  filtros básicos, así que no respondas con basura ni con oficios puros.
  Piensa en la jerarquía conceptual de UNSPSC solo como guía, sin usar
  códigos numéricos.
  Devuelve `normalized_service`, `domain_code`, `category_name` y
  `service_summary` en español neutro, claros y operativos.
  Nunca devuelvas una profesión pura como normalized_service.
  Si el texto es ambiguo, usa `clarification_required` en vez de inventar.
  No uses `catalog_review_required` ni sugerencias de revisión.
  La salida debe ser JSON estricto.
  """

  @doc """
  Clasifica un texto de servicio crudo.

  Devuelve {:ok, map} con:
    - service_name: string normalizado y visible
    - service_summary: descripción breve operativa
    - domain_code: código del catálogo de dominios (puede ser nil)
    - category_name: categoría (puede ser nil)
    - classification_confidence: float 0.0..1.0
    - raw_service_text: texto original

  o {:error, reason}
  """
  def classify(raw_text) when is_binary(raw_text) do
    text = String.trim(raw_text)

    cond do
      String.length(text) < 2 ->
        {:error, :text_too_short}

      String.length(text) > 300 ->
        {:error, :text_too_long}

      heuristic_reject?(text) ->
        {:error, :invalid_service_text}

      true ->
        do_classify(text)
    end
  end

  defp do_classify(text) do
    domains = fetch_domain_catalog()
    domains_prompt = build_domains_prompt(domains)

    with {:ok, result} <- call_openai(text, domains_prompt, strict: false) do
      if classification_complete?(result, domains) do
        {:ok, build_result(text, result)}
      else
        # Segunda llamada en modo estricto si la primera no cerró dominio/categoría
        case call_openai(text, domains_prompt, strict: true) do
          {:ok, result2} when result2 != nil ->
            final = if classification_complete?(result2, domains), do: result2, else: result
            {:ok, build_result(text, final)}

          _ ->
            {:ok, build_result(text, result)}
        end
      end
    end
  end

  defp call_openai(text, domains_prompt, strict: strict) do
    strict_note =
      if strict do
        "\nModo estricto: si el texto es un servicio real, debes cerrar " <>
          "domain_code y category_name; no dejes ambos vacíos. " <>
          "Si no puedes resolverlos, devuelve clarification_required."
      else
        ""
      end

    user_prompt =
      "Clasifica este servicio:\n" <>
        "\"#{text}\"\n\n" <>
        "Dominios disponibles:\n" <>
        domains_prompt <>
        "\n\nResponde SOLO con JSON con la forma " <>
        "{\"normalized_service\":\"...\"," <>
        "\"domain_code\":\"...\"," <>
        "\"category_name\":\"...\"," <>
        "\"service_summary\":\"...\"," <>
        "\"confidence\":0.0," <>
        "\"reason\":\"...\"," <>
        "\"clarification_question\":\"... o null\"," <>
        "\"status\":\"accepted|clarification_required|rejected\"}" <>
        strict_note

    case OpenAIClient.chat_completion(@system_prompt, user_prompt) do
      {:ok, json_text} ->
        case Jason.decode(json_text) do
          {:ok, parsed} -> {:ok, parsed}
          _ -> {:ok, %{}}
        end

      {:error, reason} ->
        Logger.warning("ServiceClassifier OpenAI error: #{inspect(reason)}")
        {:error, reason}
    end
  end

  defp fetch_domain_catalog do
    case SupabaseClient.fetch_service_domains() do
      {:ok, %{body: domains}} when is_list(domains) -> domains
      _ -> []
    end
  end

  defp build_domains_prompt([]), do: "- sin_catalogo: usar null si no hay dominio claro"

  defp build_domains_prompt(domains) do
    domains
    |> Enum.take(40)
    |> Enum.map_join("\n", fn d ->
      desc = if d["description"] && d["description"] != "", do: " (#{d["description"]})", else: ""
      "- #{d["code"]}: #{d["display_name"]}#{desc}"
    end)
  end

  defp classification_complete?(result, domains) do
    category = result["category_name"]
    status = result["status"]
    domain_code = result["domain_code"]
    valid_codes = Enum.map(domains, & &1["code"])

    not blank?(result["normalized_service"]) and
      not blank?(category) and
      status in ["accepted", nil, ""] and
      (blank?(domain_code) or Enum.member?(valid_codes, domain_code))
  end

  defp build_result(raw_text, result) do
    normalized = blank_to_default(result["normalized_service"], raw_text)
    summary = blank_to_default(result["service_summary"], normalized)

    %{
      "service_name" => normalized,
      "service_summary" => summary,
      "domain_code" => blank_to_nil(result["domain_code"]),
      "category_name" => blank_to_nil(result["category_name"]),
      "classification_confidence" => to_float(result["confidence"]),
      "raw_service_text" => raw_text
    }
  end

  defp heuristic_reject?(text) do
    normalized = text |> String.downcase() |> String.trim()
    normalized in ~w(hola buenas gracias ok okay info ayuda test prueba servicio servicios varios general)
  end

  defp blank?(value), do: is_nil(value) or value == ""
  defp blank_to_nil(value) when value in [nil, "", "null"], do: nil
  defp blank_to_nil(value), do: value
  defp blank_to_default(value, default) when value in [nil, ""], do: default
  defp blank_to_default(value, _default), do: value
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
