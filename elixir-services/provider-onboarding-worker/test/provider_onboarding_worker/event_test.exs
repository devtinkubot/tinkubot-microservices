defmodule ProviderOnboardingWorker.EventTest do
  use ExUnit.Case, async: true

  alias ProviderOnboardingWorker.Event

  test "parses tuple stream entries into events" do
    entry = {
      "1760000000-0",
      [
        "event_type",
        "provider.onboarding.services.persist_requested",
        "provider_id",
        "prov-1",
        "phone",
        "5491112345678@s.whatsapp.net",
        "checkpoint",
        "onboarding_specialty",
        "idempotency_key",
        "abc123",
        "payload",
        "{\"raw_service_text\":\"plomeria\",\"service_position\":0}"
      ]
    }

    assert {:ok, %Event{} = event} = Event.from_stream_entry(entry)
    assert event.id == "1760000000-0"
    assert event.event_type == "provider.onboarding.services.persist_requested"
    assert event.payload["raw_service_text"] == "plomeria"
    assert event.payload["service_position"] == 0
  end

  test "rejects malformed payloads" do
    entry = {
      "1760000000-1",
      [
        "event_type",
        "provider.onboarding.services.persist_requested",
        "provider_id",
        "prov-1",
        "phone",
        "5491112345678@s.whatsapp.net",
        "idempotency_key",
        "abc123",
        "payload",
        "{invalid-json}"
      ]
    }

    assert {:error, _reason} = Event.from_stream_entry(entry)
  end
end
