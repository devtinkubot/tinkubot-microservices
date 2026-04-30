defmodule ProviderOnboardingWorker.ReviewChecklistTest do
  use ExUnit.Case, async: true

  alias ProviderOnboardingWorker.Processor

  describe "check_minimum_fields/2" do
    setup do
      complete_provider = %{
        "has_consent" => true,
        "real_phone" => "593991234567",
        "city" => "guayaquil",
        "location_lat" => -2.203,
        "location_lng" => -79.897,
        "dni_front_photo_url" => "https://storage/dni-front.jpg",
        "face_photo_url" => "https://storage/face.jpg",
        "experience_range" => "3 a 5 años"
      }

      %{provider: complete_provider}
    end

    test "returns empty list when all minimum fields are present", %{provider: provider} do
      assert Processor.check_minimum_fields(provider, 3) == []
    end

    test "returns has_consent when consent is missing", %{provider: provider} do
      provider = Map.put(provider, "has_consent", false)
      assert "has_consent" in Processor.check_minimum_fields(provider, 3)
    end

    test "returns real_phone when phone is missing", %{provider: provider} do
      provider = Map.put(provider, "real_phone", nil)
      assert "real_phone" in Processor.check_minimum_fields(provider, 3)
    end

    test "returns real_phone when phone is empty string", %{provider: provider} do
      provider = Map.put(provider, "real_phone", "")
      assert "real_phone" in Processor.check_minimum_fields(provider, 3)
    end

    test "returns city_or_location when both city and location are missing", %{provider: provider} do
      provider = Map.put(provider, "city", nil)
      provider = Map.put(provider, "location_lat", nil)
      provider = Map.put(provider, "location_lng", nil)
      assert "city_or_location" in Processor.check_minimum_fields(provider, 3)
    end

    test "passes when location exists even without city", %{provider: provider} do
      provider = Map.put(provider, "city", nil)
      assert Processor.check_minimum_fields(provider, 3) == []
    end

    test "returns dni_front_photo_url when missing", %{provider: provider} do
      provider = Map.put(provider, "dni_front_photo_url", nil)
      assert "dni_front_photo_url" in Processor.check_minimum_fields(provider, 3)
    end

    test "returns face_photo_url when missing", %{provider: provider} do
      provider = Map.put(provider, "face_photo_url", nil)
      assert "face_photo_url" in Processor.check_minimum_fields(provider, 3)
    end

    test "returns experience_range when missing", %{provider: provider} do
      provider = Map.put(provider, "experience_range", nil)
      assert "experience_range" in Processor.check_minimum_fields(provider, 3)
    end

    test "returns provider_services when count is 0", %{provider: provider} do
      assert "provider_services" in Processor.check_minimum_fields(provider, 0)
    end

    test "returns provider_services when count is nil", %{provider: provider} do
      assert "provider_services" in Processor.check_minimum_fields(provider, nil)
    end

    test "social media fields are not required", %{provider: provider} do
      result = Processor.check_minimum_fields(provider, 3)
      refute "facebook_username" in result
      refute "instagram_username" in result
    end

    test "returns all missing fields at once" do
      empty = %{
        "has_consent" => false,
        "real_phone" => nil,
        "city" => nil,
        "location_lat" => nil,
        "location_lng" => nil,
        "dni_front_photo_url" => nil,
        "face_photo_url" => nil,
        "experience_range" => nil
      }

      missing = Processor.check_minimum_fields(empty, 0)

      assert "has_consent" in missing
      assert "real_phone" in missing
      assert "city_or_location" in missing
      assert "dni_front_photo_url" in missing
      assert "face_photo_url" in missing
      assert "experience_range" in missing
      assert "provider_services" in missing
    end
  end
end
