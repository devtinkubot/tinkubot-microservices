defmodule ProviderOnboardingWorker.WorkerSupportTest do
  use ExUnit.Case, async: true

  alias ProviderOnboardingWorker.WorkerSupport

  test "extracts stream entry ids from tuple and list replies" do
    assert WorkerSupport.stream_entry_id({"1760000000-0", []}) == "1760000000-0"
    assert WorkerSupport.stream_entry_id(["1760000000-1", []]) == "1760000000-1"
    assert WorkerSupport.stream_entry_id(:invalid) == nil
  end

  test "uses a safe retry delay for poll errors" do
    assert WorkerSupport.poll_retry_delay_ms(5_000) == 2_500
    assert WorkerSupport.poll_retry_delay_ms(500) == 1_000
    assert WorkerSupport.poll_retry_delay_ms(nil) == 1_000
  end
end
