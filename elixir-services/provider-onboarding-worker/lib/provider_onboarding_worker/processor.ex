defmodule ProviderOnboardingWorker.Processor do
  alias ProviderOnboardingWorker.AIProveedoresClient
  alias ProviderOnboardingWorker.Event
  alias ProviderOnboardingWorker.OpenAIClient
  alias ProviderOnboardingWorker.ServiceClassifier
  alias ProviderOnboardingWorker.SupabaseClient
  require Logger

  @event_consent "provider.onboarding.consent.persist_requested"
  @event_real_phone "provider.onboarding.real_phone.persist_requested"
  @event_city "provider.onboarding.city.persist_requested"
  @event_dni_front "provider.onboarding.dni_front.persist_requested"
  @event_face "provider.onboarding.face.persist_requested"
  @event_experience "provider.onboarding.experience.persist_requested"
  @event_services "provider.onboarding.services.persist_requested"
  @event_social "provider.onboarding.social.persist_requested"
  @event_registration "provider.onboarding.registration.persist_requested"
  @event_review "provider.onboarding.review_requested"
  @nominatim_user_agent "tinkubot-provider-onboarding-worker/1.0 (support@tinkubot.com)"
  @nominatim_search_url "https://nominatim.openstreetmap.org/search"
  @nominatim_reverse_url "https://nominatim.openstreetmap.org/reverse"

  def process(%Event{event_type: @event_consent} = event), do: persist_consent(event)
  def process(%Event{event_type: @event_real_phone} = event), do: update_real_phone(event)
  def process(%Event{event_type: @event_city} = event), do: update_city(event)

  def process(%Event{event_type: @event_dni_front} = event),
    do: update_document(event, :dni_front)

  def process(%Event{event_type: @event_face} = event), do: update_document(event, :face)
  def process(%Event{event_type: @event_experience} = event), do: update_experience(event)
  def process(%Event{event_type: @event_services} = event), do: replace_services(event)
  def process(%Event{event_type: @event_social} = event), do: update_social(event)

  def process(%Event{event_type: @event_registration} = event),
    do: register_provider(event)

  def process(%Event{event_type: @event_review} = event),
    do: mark_review_pending(event)

  def process(%Event{event_type: "onboarding_transition"}), do: {:ok, :ignored}

  def process(%Event{event_type: "provider.onboarding.add_another_service.persist_requested"}), do: {:ok, :ignored}

  def process(%Event{event_type: event_type}), do: {:error, {:unsupported_event_type, event_type}}

  defp persist_consent(%Event{provider_id: provider_id, phone: phone, payload: payload}) do
    provider_payload =
      Map.merge(onboarding_meta(payload["checkpoint"]), %{
        "id" => provider_id,
        "phone" => phone,
        "full_name" => "",
        "city" => "",
        "status" => "pending",
        "has_consent" => true,
        "onboarding_complete" => false,
        "experience_range" => nil,
        "real_phone" => payload["real_phone"],
        "display_name" => payload["display_name"],
        "formatted_name" => payload["formatted_name"]
      })
      |> compact_map()

    identities =
      build_identity_entries(
        provider_id,
        payload["raw_phone"] || phone,
        payload["from_number"],
        payload["user_id"],
        payload["account_id"]
      )

    consent_payload = %{
      "user_id" => provider_id,
      "user_type" => "provider",
      "response" => "accepted",
      "consent_date" => payload["consent_timestamp"] || now_iso(),
      "message_log" =>
        Jason.encode!(%{
          consent_timestamp: payload["consent_timestamp"] || now_iso(),
          phone: phone,
          message_id: payload["message_id"],
          exact_response: payload["exact_response"],
          consent_type: "provider_registration",
          platform: payload["platform"] || "whatsapp"
        })
    }

    with {:ok, _} <- SupabaseClient.upsert_provider(provider_payload),
         {:ok, _} <- SupabaseClient.insert_consent(consent_payload),
         {:ok, _} <- maybe_upsert_identities(identities) do
      {:ok, :persisted}
    end
  end

  defp update_real_phone(%Event{provider_id: provider_id, payload: payload}) do
    update_provider_required(
      provider_id,
      Map.merge(onboarding_meta(payload["checkpoint"]), %{
        "real_phone" => payload["real_phone"]
      })
    )
  end

  defp update_city(%Event{provider_id: provider_id, payload: payload}) do
    update_provider_required(
      provider_id,
      Map.merge(onboarding_meta(payload["checkpoint"]), city_update_payload(payload))
    )
  end

  defp update_document(%Event{provider_id: provider_id, payload: payload}, document_type) do
    with true <- SupabaseClient.provider_exists?(provider_id),
         {:ok, path} <- resolve_photo_path(provider_id, document_type, payload),
         {:ok, _} <-
           SupabaseClient.update_provider(
             provider_id,
             document_update_payload(document_type, path, payload["checkpoint"])
           ) do
      {:ok, :persisted}
    else
      false -> {:retry, :provider_missing}
      error -> error
    end
  end

  defp resolve_photo_path(_provider_id, _document_type, %{"photo_url" => url})
       when is_binary(url) and url != "" do
    {:ok, url}
  end

  defp resolve_photo_path(provider_id, document_type, %{"image_base64" => b64})
       when is_binary(b64) and b64 != "" do
    with {:ok, bytes, content_type, extension} <- decode_image(b64),
         path <- build_storage_path(provider_id, document_type, extension),
         {:ok, _} <- SupabaseClient.upload_identity_media(path, bytes, content_type) do
      {:ok, path}
    end
  end

  defp resolve_photo_path(_provider_id, _document_type, _payload),
    do: {:error, :invalid_image}

  defp update_experience(%Event{provider_id: provider_id, payload: payload}) do
    update_provider_required(
      provider_id,
      Map.merge(onboarding_meta(payload["checkpoint"]), %{
        "experience_range" => payload["experience_range"]
      })
    )
  end

  defp replace_services(%Event{provider_id: provider_id, payload: payload}) do
    normalized_payload = normalize_service_payload(payload)

    with true <- SupabaseClient.provider_exists?(provider_id),
         {:ok, resolved} <- classify_service(normalized_payload["raw_service_text"]),
         {:ok, service_row} <- build_service_row(provider_id, normalized_payload, resolved),
         {:ok, _} <- SupabaseClient.replace_service_at_position(provider_id, service_row),
         {:ok, verified_payload} <-
           verified_payload(provider_id, normalized_payload["checkpoint"]),
         {:ok, _} <- SupabaseClient.update_provider(provider_id, verified_payload) do
      {:ok, :persisted}
    else
      false -> {:retry, :provider_missing}
      error -> error
    end
  end

  defp update_social(%Event{provider_id: provider_id, payload: payload}) do
    update_provider_required(
      provider_id,
      Map.merge(onboarding_meta(payload["checkpoint"]), %{
        "facebook_username" => payload["facebook_username"],
        "instagram_username" => payload["instagram_username"]
      })
    )
  end

  defp register_provider(%Event{} = event) do
    with {:ok, _} <- AIProveedoresClient.resolve_registration(event) do
      {:ok, :persisted}
    end
  end

  defp mark_review_pending(%Event{provider_id: provider_id, payload: payload}) do
    checkpoint = payload["checkpoint"] || "review_pending_verification"
    now = now_iso()

    updates = %{
      "onboarding_step" => checkpoint,
      "onboarding_step_updated_at" => now,
      "onboarding_complete" => true,
      "updated_at" => now
    }

    case SupabaseClient.update_provider(provider_id, updates) do
      {:ok, _} -> {:ok, :persisted}
      {:error, _} -> {:retry, :provider_missing}
    end
  end

  defp city_update_payload(payload) do
    case resolve_city(payload) do
      {:ok, city} ->
        %{
          "city" => city,
          "location_lat" => payload["location_lat"],
          "location_lng" => payload["location_lng"],
          "city_confirmed_at" => payload["city_confirmed_at"] || now_iso(),
          "location_updated_at" => payload["location_updated_at"] || now_iso()
        }

      {:error, _reason} ->
        %{
          "city" => blank_to_nil(payload["city"]),
          "location_lat" => payload["location_lat"],
          "location_lng" => payload["location_lng"],
          "city_confirmed_at" => payload["city_confirmed_at"] || now_iso(),
          "location_updated_at" => payload["location_updated_at"] || now_iso()
        }
    end
  end

  defp resolve_city(payload) do
    cond do
      not blank?(payload["city"]) ->
        {:ok, normalize_city(payload["city"])}

      not blank?(payload["raw_city_text"]) ->
        resolve_city_from_text(payload["raw_city_text"])

      not blank?(payload["location_name"]) ->
        resolve_city_from_text(payload["location_name"])

      not blank?(payload["location_address"]) ->
        resolve_city_from_text(payload["location_address"])

      is_number(payload["location_lat"]) and is_number(payload["location_lng"]) ->
        resolve_city_from_coordinates(payload["location_lat"], payload["location_lng"])

      true ->
        {:error, :city_not_available}
    end
  end

  defp resolve_city_from_text(text) do
    query = text |> to_string() |> String.trim()

    if query == "" do
      {:error, :city_not_available}
    else
      params = [
        format: "jsonv2",
        q: query,
        countrycodes: "ec",
        limit: 5,
        addressdetails: 1,
        "accept-language": "es"
      ]

      with {:ok, response} <- nominatim_get(@nominatim_search_url, params),
           {:ok, city} <- extract_city_from_search_response(response) do
        {:ok, city}
      else
        _ -> {:ok, normalize_city(query)}
      end
    end
  end

  defp resolve_city_from_coordinates(lat, lng) do
    params = [
      format: "jsonv2",
      lat: lat,
      lon: lng,
      zoom: 10,
      addressdetails: 1,
      "accept-language": "es"
    ]

    with {:ok, response} <- nominatim_get(@nominatim_reverse_url, params),
         {:ok, city} <- extract_city_from_reverse_response(response) do
      {:ok, city}
    else
      _ -> {:error, :city_not_available}
    end
  end

  defp nominatim_get(url, params) do
    req =
      Req.new(
        finch: ProviderOnboardingWorker.Finch,
        receive_timeout: 10_000,
        decode_body: true
      )

    case Req.get(req, url: url, params: params, headers: [{"User-Agent", @nominatim_user_agent}]) do
      {:ok, %{status: 200, body: body}} -> {:ok, body}
      {:ok, %{status: status, body: body}} -> {:error, {status, body}}
      {:error, reason} -> {:error, reason}
    end
  end

  defp extract_city_from_search_response(body) when is_list(body) do
    body
    |> Enum.find_value(fn item ->
      if is_map(item) do
        city = city_from_map(item["address"] || %{}) || normalize_city(item["display_name"])
        if blank?(city), do: nil, else: city
      end
    end)
    |> case do
      nil -> {:error, :city_not_found}
      city -> {:ok, city}
    end
  end

  defp extract_city_from_search_response(_), do: {:error, :city_not_found}

  defp extract_city_from_reverse_response(body) when is_map(body) do
    address = body["address"] || %{}
    city = city_from_map(address) || normalize_city(body["display_name"])

    if blank?(city), do: {:error, :city_not_found}, else: {:ok, city}
  end

  defp extract_city_from_reverse_response(_), do: {:error, :city_not_found}

  defp city_from_map(address) do
    Enum.find_value(["city", "town", "village", "municipality", "county"], fn key ->
      value = address[key]
      if blank?(value), do: nil, else: normalize_city(value)
    end)
  end

  defp normalize_city(value) do
    value
    |> to_string()
    |> String.trim()
    |> String.downcase()
  end

  defp update_provider_required(provider_id, updates) do
    case SupabaseClient.update_provider(provider_id, compact_map(updates)) do
      {:ok, _} -> {:ok, :persisted}
      {:error, _} -> {:retry, :provider_missing}
    end
  end

  defp build_identity_entries(provider_id, phone, from_number, user_id, account_id) do
    [phone, from_number, user_id]
    |> Enum.reject(&blank?/1)
    |> Enum.uniq()
    |> Enum.map(fn value ->
      %{
        "provider_id" => provider_id,
        "identity_type" => infer_identity_type(value, user_id),
        "identity_value" => value,
        "whatsapp_account_id" => account_id || "",
        "is_primary" => value == phone || value == from_number,
        "first_seen_at" => now_iso(),
        "last_seen_at" => now_iso(),
        "updated_at" => now_iso(),
        "metadata" => %{"source" => "provider-onboarding-worker", "observed_at" => now_iso()}
      }
    end)
  end

  defp maybe_upsert_identities([]), do: {:ok, :noop}
  defp maybe_upsert_identities(entries), do: SupabaseClient.upsert_identities(entries)

  defp infer_identity_type(value, user_id) when value == user_id, do: "user_id"

  defp infer_identity_type(value, _user_id) do
    if String.contains?(to_string(value), "@lid"), do: "lid", else: "phone"
  end

  def build_service_row(provider_id, payload, resolved) do
    service_detail = resolved["service_detail"] || %{}

    service_name =
      service_detail["service_name"] ||
        payload["raw_service_text"] ||
        "servicio pendiente de revisión"

    service_summary = service_detail["service_summary"] || service_name
    display_order = payload["service_position"] || 0
    service_name_normalized = normalize_for_search(service_name)
    domain_code = blank_to_nil(service_detail["domain_code"])
    category_name = blank_to_nil(service_detail["category_name"])
    embedding_text = canonical_embedding_text(service_summary, domain_code, category_name)

    with {:ok, embedding} <- generate_embedding(embedding_text) do
      {:ok,
       compact_map(%{
         "provider_id" => provider_id,
         "service_name" => service_name,
         "raw_service_text" =>
           service_detail["raw_service_text"] || payload["raw_service_text"] || service_name,
         "service_summary" => service_summary,
         "service_name_normalized" => service_name_normalized,
         "service_embedding" => embedding,
         "is_primary" => display_order == 0,
         "display_order" => display_order,
         "domain_code" => domain_code,
         "category_name" => category_name,
         "classification_confidence" => service_detail["classification_confidence"] || 0.0
       })}
    end
  end

  def canonical_embedding_text(service_summary, domain_code, category_name) do
    ProviderOnboardingWorker.EmbeddingGrammar.canonical_service_text(
      service_summary,
      domain_code,
      category_name
    )
  end

  defp generate_embedding(text) do
    case Application.get_env(:provider_onboarding_worker, :embedding_for_hook) do
      hook when is_function(hook, 1) -> hook.(text)
      _ -> OpenAIClient.embedding_for(text)
    end
  end

  defp normalize_service_payload(payload) do
    raw_service_text =
      first_present([
        payload["raw_service_text"],
        latest_service_entry(payload)["raw_service_text"],
        latest_service_entry(payload)["service_name"],
        latest_service(payload)
      ]) || ""

    service_position =
      payload["service_position"] ||
        Enum.max([length(service_entries(payload)) - 1, length(services_snapshot(payload)) - 1, 0])

    payload
    |> Map.put("raw_service_text", raw_service_text)
    |> Map.put("service_position", service_position)
  end

  defp verified_payload(provider_id, checkpoint) do
    with {:ok, %{body: [provider | _]}} <-
           SupabaseClient.fetch_provider(provider_id, "id,experience_range"),
         {:ok, count} <- SupabaseClient.count_services(provider_id) do
      {:ok,
       compact_map(
         Map.merge(onboarding_meta(checkpoint), %{
           "onboarding_complete" =>
             not blank?(provider["experience_range"]) and count > 0,
           "service_review_required" => false,
           "generic_services_removed" => []
         })
       )}
    end
  end

  defp decode_image("data:image/" <> _ = data_uri) do
    [meta, encoded] = String.split(data_uri, ",", parts: 2)
    content_type = meta |> String.trim_leading("data:") |> String.trim_trailing(";base64")
    extension = content_type_to_extension(content_type)
    Base.decode64(encoded) |> wrap_image_result(content_type, extension)
  end

  defp decode_image(encoded) when is_binary(encoded) do
    Base.decode64(encoded) |> wrap_image_result("image/jpeg", "jpg")
  end

  defp decode_image(_), do: {:error, :invalid_image}

  defp wrap_image_result({:ok, bytes}, content_type, extension),
    do: {:ok, bytes, content_type, extension}

  defp wrap_image_result(:error, _content_type, _extension),
    do: {:error, :invalid_image}

  defp content_type_to_extension("image/png"), do: "png"
  defp content_type_to_extension("image/webp"), do: "webp"
  defp content_type_to_extension("image/gif"), do: "gif"
  defp content_type_to_extension(_), do: "jpg"

  defp build_storage_path(provider_id, :dni_front, extension),
    do: "dni-fronts/#{provider_id}.#{extension}"

  defp build_storage_path(provider_id, :face, extension), do: "faces/#{provider_id}.#{extension}"

  defp document_update_payload(type, path, checkpoint) do
    field = if type == :dni_front, do: "dni_front_photo_url", else: "face_photo_url"

    onboarding_meta(checkpoint)
    |> Map.put(field, SupabaseClient.public_storage_url(path))
  end

  defp normalize_for_search(value) do
    value
    |> to_string()
    |> String.trim()
    |> String.replace(~r/\s+/u, " ")
    |> String.normalize(:nfd)
    |> String.replace(~r/\p{Mn}/u, "")
    |> String.downcase()
  end

  defp compact_map(map) do
    Enum.reduce(map, %{}, fn
      {_key, nil}, acc -> acc
      {key, value}, acc -> Map.put(acc, key, value)
    end)
  end

  defp first_present(values) do
    Enum.find(values, fn value -> not blank?(value) end)
  end

  defp latest_service_entry(payload) do
    payload
    |> service_entries()
    |> List.last()
    |> case do
      entry when is_map(entry) -> entry
      _ -> %{}
    end
  end

  defp service_entries(payload) do
    case payload["service_entries"] do
      entries when is_list(entries) -> entries
      _ -> []
    end
  end

  defp latest_service(payload) do
    payload
    |> services_snapshot()
    |> List.last()
  end

  defp services_snapshot(payload) do
    case payload["services"] do
      services when is_list(services) -> services
      _ -> []
    end
  end

  defp blank?(value), do: is_nil(value) or value == ""
  defp blank_to_nil(value) when value in [nil, "", "null"], do: nil
  defp blank_to_nil(value), do: value

  defp onboarding_meta(checkpoint) do
    now = now_iso()

    %{
      "updated_at" => now,
      "onboarding_step" => checkpoint,
      "onboarding_step_updated_at" => now
    }
  end

  defp now_iso, do: DateTime.utc_now() |> DateTime.truncate(:second) |> DateTime.to_iso8601()

  defp classify_service(raw_text) do
    case ServiceClassifier.classify(raw_text || "") do
      {:ok, result} ->
        # Wrap en la forma que espera build_service_row (igual que respondía Python)
        {:ok, %{"service_detail" => result}}

      {:error, reason} ->
        Logger.warning("ServiceClassifier failed: #{inspect(reason)}, usando texto crudo")
        {:ok, %{"service_detail" => %{"service_name" => raw_text, "service_summary" => raw_text, "raw_service_text" => raw_text}}}
    end
  end
end
