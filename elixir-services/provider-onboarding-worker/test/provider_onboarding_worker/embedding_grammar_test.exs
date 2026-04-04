defmodule ProviderOnboardingWorker.EmbeddingGrammarTest do
  use ExUnit.Case, async: true

  alias ProviderOnboardingWorker.EmbeddingGrammar

  test "builds canonical service embedding text from the service summary" do
    assert EmbeddingGrammar.canonical_service_text(
             "Desarrollo de software a medida, con soporte y mantenimiento.",
             "Tecnología",
             "Servicios tecnológicos"
           ) == "desarrollo de software a medida con soporte y mantenimiento | tecnologia | servicios tecnologicos"
  end

  test "ignores blank components while keeping order stable" do
    assert EmbeddingGrammar.canonical_service_text("Plomería", nil, "") ==
             "plomeria"
  end
end
