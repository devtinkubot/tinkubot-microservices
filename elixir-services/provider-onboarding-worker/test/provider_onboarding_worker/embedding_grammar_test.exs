defmodule ProviderOnboardingWorker.EmbeddingGrammarTest do
  use ExUnit.Case, async: true

  alias ProviderOnboardingWorker.EmbeddingGrammar

  test "builds canonical service embedding text from the base fields only" do
    assert EmbeddingGrammar.canonical_service_text(
             "Desarrollo de Software",
             "Tecnología",
             "Servicios tecnológicos"
           ) == "desarrollo de software | tecnologia | servicios tecnologicos"
  end

  test "ignores blank components while keeping order stable" do
    assert EmbeddingGrammar.canonical_service_text("Plomería", nil, "") ==
             "plomeria"
  end
end
