defmodule ProviderOnboardingWorker.OpenAIClient do
  use Agent

  def start_link(_opts) do
    Agent.start_link(
      fn ->
        api_key = Application.fetch_env!(:provider_onboarding_worker, :openai_api_key)
        model = Application.fetch_env!(:provider_onboarding_worker, :openai_embedding_model)

        req =
          Req.new(
            base_url: "https://api.openai.com",
            headers: [
              {"Authorization", "Bearer #{api_key}"},
              {"Content-Type", "application/json"}
            ],
            finch: ProviderOnboardingWorker.Finch,
            receive_timeout: 30_000,
            decode_body: true
          )

        {req, model}
      end,
      name: __MODULE__
    )
  end

  def embedding_for(text) when not is_binary(text) or text == "" do
    {:ok, nil}
  end

  def embedding_for(text) do
    case Application.get_env(:provider_onboarding_worker, :embedding_for_hook) do
      hook when is_function(hook, 1) -> hook.(text)
      _ -> embedding_for_openai(text)
    end
  end

  defp embedding_for_openai(text) do
    {req, model} = Agent.get(__MODULE__, & &1)

    case Req.post(req, url: "/v1/embeddings", json: %{input: text, model: model}) do
      {:ok, %{status: 200, body: %{"data" => [%{"embedding" => embedding}]}}} ->
        {:ok, embedding}

      {:ok, %{status: status, body: body}} ->
        {:error, "OpenAI API error #{status}: #{inspect(body)}"}

      {:error, reason} ->
        {:error, reason}
    end
  end

  def chat_completion(system_prompt, user_prompt) do
    req = Agent.get(__MODULE__, &elem(&1, 0))
    model = Application.get_env(:provider_onboarding_worker, :chat_model, "gpt-4o-mini")

    body = %{
      model: model,
      messages: [
        %{role: "system", content: system_prompt},
        %{role: "user", content: user_prompt}
      ],
      temperature: 0.1
    }

    case Req.post(req, url: "/chat/completions", json: body) do
      {:ok, %{status: 200, body: %{"choices" => [%{"message" => %{"content" => content}} | _]}}} ->
        {:ok, content}

      {:ok, %{status: status, body: body}} ->
        {:error, {:openai_error, status, body}}

      {:error, reason} ->
        {:error, reason}
    end
  end
end
