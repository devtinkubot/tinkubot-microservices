defmodule ProviderOnboardingWorker.SupabaseClient do
  @moduledoc false
  use Agent
  require Logger

  def start_link(_opts) do
    Agent.start_link(
      fn ->
        supabase_url = Application.fetch_env!(:provider_onboarding_worker, :supabase_url)
        key = Application.fetch_env!(:provider_onboarding_worker, :supabase_service_key)
        bucket = Application.fetch_env!(:provider_onboarding_worker, :providers_bucket)

        req =
          Req.new(
            base_url: supabase_url,
            headers: [
              {"apikey", key},
              {"Authorization", "Bearer #{key}"},
              {"Content-Type", "application/json"},
              {"Prefer", "return=representation"}
            ],
            finch: ProviderOnboardingWorker.Finch,
            decode_body: true,
            receive_timeout: 15_000
          )

        {req, bucket}
      end,
      name: __MODULE__
    )
  end

  defp req, do: Agent.get(__MODULE__, fn {r, _} -> r end)
  defp bucket, do: Agent.get(__MODULE__, fn {_, b} -> b end)

  defp request(method, path, opts \\ []) do
    merged = Keyword.merge([method: method, url: path], opts)

    case Req.request(req(), merged) do
      {:ok, %{status: status} = resp} when status >= 200 and status < 300 ->
        {:ok, resp}

      {:ok, %{status: status, body: body}} ->
        Logger.warning("Supabase HTTP #{status} #{method} #{path}: #{inspect(body)}")
        {:error, {:http_error, status, body}}

      {:error, _} = error ->
        error
    end
  end

  def provider_exists?(provider_id) do
    case request(
           :get,
           "/rest/v1/providers?id=eq.#{URI.encode_www_form(provider_id)}&select=id&limit=1"
         ) do
      {:ok, %{body: [%{"id" => _}]}} -> true
      _ -> false
    end
  end

  def upsert_provider(payload, on_conflict \\ "phone") do
    request(
      :post,
      "/rest/v1/providers?on_conflict=#{URI.encode_www_form(on_conflict)}",
      json: [payload],
      headers: [{"prefer", "resolution=merge-duplicates,return=representation"}]
    )
  end

  def update_provider(provider_id, payload) do
    request(
      :patch,
      "/rest/v1/providers?id=eq.#{URI.encode_www_form(provider_id)}",
      json: payload,
      headers: [{"prefer", "return=representation"}]
    )
  end

  def fetch_provider(provider_id, fields \\ "id,phone,experience_range") do
    request(
      :get,
      "/rest/v1/providers?id=eq.#{URI.encode_www_form(provider_id)}&select=#{URI.encode_www_form(fields)}&limit=1"
    )
  end

  def insert_consent(payload) do
    request(
      :post,
      "/rest/v1/consents",
      json: [payload],
      headers: [{"prefer", "return=representation"}]
    )
  end

  def upsert_identities(entries) do
    request(
      :post,
      "/rest/v1/provider_whatsapp_identities?on_conflict=whatsapp_account_id,identity_type,identity_value",
      json: entries,
      headers: [{"prefer", "resolution=merge-duplicates,return=representation"}]
    )
  end

  def replace_services(provider_id, entries) do
    with {:ok, _} <-
           request(
             :delete,
             "/rest/v1/provider_services?provider_id=eq.#{URI.encode_www_form(provider_id)}"
           ),
         {:ok, _} <-
           maybe_insert_services(entries) do
      {:ok, :replaced}
    end
  end

  def replace_service_at_position(provider_id, entry) do
    display_order = entry["display_order"] || 0

    with {:ok, _} <-
           request(
             :delete,
             "/rest/v1/provider_services?provider_id=eq.#{URI.encode_www_form(provider_id)}&display_order=eq.#{display_order}"
           ),
         {:ok, _} <-
           request(
             :post,
             "/rest/v1/provider_services",
             json: [entry],
             headers: [{"prefer", "return=representation"}]
           ) do
      {:ok, :replaced}
    end
  end

  def count_services(provider_id) do
    case request(:head, "/rest/v1/provider_services?provider_id=eq.#{provider_id}",
           headers: [{"Prefer", "count=exact"}, {"Range", "0-0"}]
         ) do
      {:ok, %{headers: resp_headers}} ->
        count =
          Enum.find_value(resp_headers, fn
            {"content-range", v} -> content_range_count(v)
            {"Content-Range", v} -> content_range_count(v)
            _ -> nil
          end) || 0

        {:ok, count}

      {:error, reason} ->
        {:error, reason}
    end
  end

  def upload_identity_media(path, body, content_type) do
    request(
      :post,
      "/storage/v1/object/#{bucket()}/#{path}",
      body: body,
      headers: [
        {"content-type", content_type},
        {"x-upsert", "true"}
      ]
    )
  end

  def fetch_service_domains do
    req = Agent.get(__MODULE__, &elem(&1, 0))

    case Req.get(req,
           url: "/rest/v1/service_domains",
           params: [select: "code,display_name,description,status", order: "code.asc"]
         ) do
      {:ok, %{status: 200, body: body}} -> {:ok, %{body: body}}
      {:ok, %{status: status, body: body}} -> {:error, {status, body}}
      {:error, reason} -> {:error, reason}
    end
  end

  defp maybe_insert_services([]), do: {:ok, :noop}

  defp maybe_insert_services(entries) do
    request(
      :post,
      "/rest/v1/provider_services",
      json: entries,
      headers: [{"prefer", "return=representation"}]
    )
  end

  def content_range_count(value) do
    value
    |> normalize_header_value()
    |> case do
      nil ->
        nil

      range ->
        range
        |> String.split("/", parts: 2)
        |> List.last()
        |> String.to_integer()
    end
  rescue
    ArgumentError -> nil
  end

  defp normalize_header_value(value) when is_binary(value), do: String.trim(value)

  defp normalize_header_value(value) when is_list(value),
    do: value |> List.first() |> normalize_header_value()

  defp normalize_header_value(_value), do: nil
end
