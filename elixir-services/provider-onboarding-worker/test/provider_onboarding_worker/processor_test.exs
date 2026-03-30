defmodule ProviderOnboardingWorker.ProcessorTest do
  use ExUnit.Case, async: true

  alias ProviderOnboardingWorker.Processor

  test "build_service_row uses canonical embedding text and preserves summary" do
    on_exit(fn ->
      Application.delete_env(:provider_onboarding_worker, :embedding_for_hook)
    end)

    Application.put_env(:provider_onboarding_worker, :embedding_for_hook, fn text ->
      send(self(), {:embedding_text, text})
      {:ok, [0.1, 0.2]}
    end)

    resolved = %{
      "service_detail" => %{
        "service_name" => "Desarrollo Web",
        "service_summary" => "Resumen para UI",
        "domain_code" => "tecnologia",
        "category_name" => "Servicios tecnologicos",
        "classification_confidence" => 0.92
      }
    }

    payload = %{
      "raw_service_text" => "Desarrollo Web",
      "service_position" => 0
    }

    assert {:ok, row} = Processor.build_service_row("prov-1", payload, resolved)

    assert_received {:embedding_text, "desarrollo web | tecnologia | servicios tecnologicos"}

    assert row["service_summary"] == "Resumen para UI"
    assert row["service_name"] == "Desarrollo Web"
    assert row["service_name_normalized"] == "desarrollo web"
    assert row["service_embedding"] == [0.1, 0.2]
    assert row["is_primary"] == true
    assert row["display_order"] == 0
  end

  test "canonical embedding text drops empty components" do
    assert Processor.canonical_embedding_text("diseno grafico", nil, "") ==
             "diseno grafico"
  end
end
