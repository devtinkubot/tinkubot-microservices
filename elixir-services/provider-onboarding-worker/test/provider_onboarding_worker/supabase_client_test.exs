defmodule ProviderOnboardingWorker.SupabaseClientTest do
  use ExUnit.Case, async: true

  alias ProviderOnboardingWorker.SupabaseClient

  describe "content_range_count/1" do
    test "acepta un header string" do
      assert SupabaseClient.content_range_count("0-0/1") == 1
    end

    test "acepta un header como lista" do
      assert SupabaseClient.content_range_count(["0-0/1"]) == 1
    end

    test "retorna nil ante valores inválidos" do
      assert SupabaseClient.content_range_count(nil) == nil
      assert SupabaseClient.content_range_count([]) == nil
      assert SupabaseClient.content_range_count(["invalido"]) == nil
    end
  end
end
