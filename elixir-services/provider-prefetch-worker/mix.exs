defmodule ProviderPrefetchWorker.MixProject do
  use Mix.Project

  def project do
    [
      app: :provider_prefetch_worker,
      version: "0.1.0",
      elixir: "~> 1.17",
      start_permanent: Mix.env() == :prod,
      deps: deps()
    ]
  end

  def application do
    [
      extra_applications: [:logger, :crypto, :finch],
      mod: {ProviderPrefetchWorker.Application, []}
    ]
  end

  defp deps do
    [
      {:castore, "~> 1.0"},
      {:jason, "~> 1.4"},
      {:redix, "~> 1.5"},
      {:finch, "~> 0.19"},
      {:req, "~> 0.5"}
    ]
  end
end
