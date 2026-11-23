## Error vocabulary

Acquisition adds one contractual error domain, `ErrorDomain::kAcquisition`, with eleven fixed codes (d6, ic5). Driver errors still pass unchanged, and gateway diagnostics stay private. A missing frame from `take` is a successful empty result, not an error.

Labels: `[F]` is a fact with a citation. `[A]` is a working assumption. `[Q]` is an open question. `ros:path:line` is from the ROS source root.

### What exists today

1. `[F]` `ErrorDomain` has two values, `kDriver = 0` and `kGateway = 1`. `Error` has the factories `from_driver` and `from_gateway`, each with a nonzero code (`src/venimapping_camera/include/venimapping_camera/types/error.hpp:17-34`).
2. `[F]` `Expected<T>` is `std::expected<T, Error>` (`src/venimapping_camera/include/venimapping_camera/types/expected.hpp:17-18`).
3. `[F]` A nonzero driver `error.code` becomes a `kDriver` error with the code and text unchanged (`src/venimapping_camera/src/vimbax_camera_gateway.cpp:213-229`).
4. `[F]` Gateway diagnostics 1 to 5 are for logs and tests only. Callers classify errors by domain (`src/venimapping_camera/src/gateway_support/gateway_errors.hpp:15-22`).

v1 proposed new non-contractual gateway diagnostics for the data plane (v1 §9). v2 replaces that with a contractual domain. A wedge, a format refusal, a passed deadline, and a closed feed need different caller actions (facts 1.4.3, 1.4.4, c1 §3.1). A caller cannot act on a code that is not part of the contract.

### Header changes

`types/error.hpp` gets one enum value and one factory. The factory follows the existing form.

```cpp
enum class ErrorDomain : std::uint8_t {
  kDriver = 0,
  kGateway = 1,
  kAcquisition = 2,
};

// In class Error:
[[nodiscard]] static constexpr Error from_acquisition(std::int32_t code, std::string text) noexcept
{
  assert(code != 0 && "an acquisition error code must be nonzero");
  return Error{ErrorDomain::kAcquisition, code, std::move(text)};
}
```

New installed header `types/acquisition_error.hpp`:

```cpp
namespace venimapping::camera {

enum class AcquisitionCode : std::int32_t {
  kFeedClosed = 1,
  kDeadlinePassed = 2,
  kStreamWedged = 3,
  kFormatNotStreamable = 4,
  kProfileMismatch = 5,
  kSubscriptionNotMatched = 6,
  kWrongThread = 7,
  kTriggerNoFrame = 8,          // reserved for phase 2
  kRequestBusy = 9,
  kInvalidArgument = 10,
  kSourceCreateFailed = 11,
};

[[nodiscard]] inline Error acquisition_error(AcquisitionCode code, std::string text)
{
  return Error::from_acquisition(static_cast<std::int32_t>(code), std::move(text));
}

[[nodiscard]] constexpr bool is_acquisition(const Error& error, AcquisitionCode code) noexcept
{
  return error.domain() == ErrorDomain::kAcquisition &&
         error.code() == static_cast<std::int32_t>(code);
}

[[nodiscard]] constexpr std::string_view to_string(AcquisitionCode code) noexcept;

}  // namespace venimapping::camera
```

1. The numbers are fixed. A code is never reused or renumbered. A new code takes the next free number.
2. Both headers stay ROS-free. They belong to the existing INTERFACE target `venimapping_camera_gateway_api`, so `acquisition_error` and `to_string` are `inline` (ic8).
3. The `int32_t` base matches `Error::code()`, as `GatewayDiagnostic` does (`src/venimapping_camera/src/gateway_support/gateway_errors.hpp:16`).
4. The text names the cause and the value. For example: "PixelFormat Mono10 is not in the allowed formats [Mono8]".

### Error values

| Code | Name | Layer | Returned by | Cause | Caller action |
|---|---|---|---|---|---|
| 1 | `kFeedClosed` | data plane | `take`, `try_take` | `close()` ran, the `FrameSource` is gone, or the controller shut down | Stop reading. Open a new feed if needed. |
| 1 | `kFeedClosed` | control plane | `feed_open`, `get_image`, `Feed::take` on an empty `Feed` | The request came after `shutdown()` started, or it was queued or running when shutdown ran, also before `start`. Or `WorkerInit` failed | Stop. The acquisition stack is closed. |
| 1 | `kFeedClosed` | control plane | `start` | `shutdown()` started before or during `start` | Stop. Make a new controller if needed. |
| 2 | `kDeadlinePassed` | control plane | `feed_open`, `get_image` | The request deadline passed before the call had its result. See "Deadline stages" | Retry later, or report. Read `status()` to see an outage. |
| 3 | `kStreamWedged` | control plane | `feed_open`, `get_image` | The controller is in `kWedged`, or the request caused it (d19) | The operator restarts the driver process. The controller clears the state after a confirmation stop succeeds. |
| 4 | `kFormatNotStreamable` | control plane | `feed_open`, `get_image`, `AcquisitionController::create` | The final `PixelFormat` is outside the allowed formats that are on the driver gate (d19 item 1) | Fix the settings file or the profile file. No retry. |
| 5 | `kProfileMismatch` | control plane | `feed_open`, `get_image` | A value in the final readback still differs after the corrective writes (d18 item 6) | Compare the settings file with the profile file. No retry. |
| 6 | `kSubscriptionNotMatched` | control plane | `feed_open`, `get_image` | No matched publisher after 1000 ms (d17) | Check that the driver runs under the same namespace. Retry after that. |
| 7 | `kWrongThread` | data plane | `take`, `try_take` | A call from a thread other than the first consumer thread (ic2 rule 4) | Fix the caller. This is a program error. |
| 8 | `kTriggerNoFrame` | control plane | Nothing in phase 1 | Reserved for the phase 2 software trigger (d27) | None in phase 1. |
| 9 | `kRequestBusy` | control plane | `feed_open`, `get_image` | A feed is already open, or a get image is already outstanding (d13) | Wait for the other request, or close the other feed. |
| 10 | `kInvalidArgument` | data plane | `subscribe`, `ImageFrame::create` | Capacity outside 1 to 4, or a bad frame layout | Fix the argument. This is a program error. |
| 10 | `kInvalidArgument` | control plane | `AcquisitionController::create`, `start`, `feed_open` | A bad option in `ControllerOptions`, a second `start` call while the worker starts or runs, or a bad `FeedOptions::capacity` passed through from `subscribe` | Fix the caller. |
| 11 | `kSourceCreateFailed` | data plane | `VimbaXFrameSource::create` | The ROS subscription could not be made, or the namespace is empty | The composition root reports and exits. |

1. The data plane returns only codes 1, 7, 10, and 11. It never returns `kDriver` or `kGateway` errors (ic5 item 1).
2. The image callback never returns an error. It counts each discard in `FrameSourceStats` (ic5 item 4).
3. `kWrongThread` and `kInvalidArgument` are program errors. A test finds them. A running system does not retry them.
4. A `shutdown()` before `start` completes each queued request with `kFeedClosed` on the calling thread, with no gateway call.

### Deadline stages

`kDeadlinePassed` has one cause: the absolute request deadline passed before the call had its result. `FeedOptions::deadline` is 5000 ms by default, and `GetImageOptions::deadline` is 2000 ms (d26). The worker checks the outcome and the deadline before each gateway call that the request causes. The same code covers each stage:

| Stage | Who sees the deadline | What the worker does after it |
|---|---|---|
| Waiting in the worker queue, also before `start` | The caller | Takes the expired request, makes no `subscribe` and no gateway call |
| Readback, corrective writes, second readback | The caller. The worker sees it before its next gateway call | Finishes the pending gateway call. Makes no further call in the list |
| Match wait | The caller. The worker sees it at the next 10 ms poll | Makes no `open_admission` and no `stream_start` |
| After `open_admission`, before `stream_start` | The caller. The worker sees it before `stream_start` | Calls `close_admission()`, makes no `stream_start`, and runs the lease release rules |
| `stream_start` | The caller | Finishes the call. Then the lease release stops the stream, or the failure recovery runs |
| Delivery | The worker, in the same locked section as the `kDelivered` transition | Abandons the request instead of a delivery, and destroys the `Feed` |
| `get_image` only: wait for a frame with `receive_seq > R` | The caller, before each `take` and after each frame that `take` returns | The caller drops a frame that it took after the deadline and destroys its `Feed`, which releases the lease |

1. A `get_image` that returns a frame accepted it at or before its deadline. A frame that `take` returns after the deadline gives `kDeadlinePassed`, also if it is fresh. The caller cannot see when a frame entered its queue, so the acceptance time is the only exact check.
2. The `stream_stop` after a get image delivery is outside the deadline (d26 item 3).
3. A gateway call keeps its own timeout. The request deadline does not shorten it (d26 item 5). A check before each call frees the worker within one gateway timeout after the deadline.

### Errors that pass through the controller

The controller returns gateway errors from its reads and its stream calls unchanged (ic5 item 2). A caller sees these classes:

| Domain and code | Typical cause | Caller action |
|---|---|---|
| `kDriver`, -3 (`VmbErrorNotFound`) | The camera is not available. A disconnect is in progress (facts 1.9.5). | Retry after `status()` leaves `kOutage`, or after a fixed wait. |
| `kDriver`, -15 (`VmbErrorInvalidCall`) | A stream call met a transitional driver state, and the reconciliation stop then succeeded | Retry. The reconciliation stop confirmed the stopped state. |
| `kDriver`, another code | The driver refused one call. | Report the code and the text. The controller has already reconciled the stream state (d19). |
| `kGateway`, any code | The driver services do not answer, or a call timed out. | Check that the driver process runs. Retry after that. |

1. A caller must classify an error by `domain()` first and then by `code()`. A `kGateway` code number has no meaning to the caller (`src/venimapping_camera/src/gateway_support/gateway_errors.hpp:15`).
2. For a failed stream call, the controller keeps two results apart. The caller gets the first error. `status().last_error` holds the same error. `status().last_reconciliation` holds the error of the reconciliation stop, or is empty if it succeeded.
3. -15 reaches a caller only with a successful reconciliation stop. If the reconciliation stop fails, the caller gets `kStreamWedged`, and its text names both errors.
4. -18 (`VmbErrorNotSupported`) from a format refusal at start cannot occur, because the format check comes first (c1 §3.1 item 2).
5. The confirmation stop in `kWedged` runs with no request. Its error never reaches a caller. It goes to `status().last_reconciliation`, and the state stays `kWedged`.

Corrective writes do not pass through:

1. The second readback decides the result of the corrective writes, because a setter that times out can still apply (`src/venimapping_camera/include/venimapping_camera/camera_gateway.hpp:24-26`).
2. If the second readback matches, the request continues, and the write error goes only to `status().last_error`.
3. If a value still differs, the caller gets `kFormatNotStreamable` or `kProfileMismatch`. The text names the value and the write error.
4. If a read in the second readback fails, that read error passes through unchanged.

### Results that are not errors

| Result | Where | Meaning |
|---|---|---|
| Empty `std::optional` from `take` or `try_take` | data plane | No frame in the timeout. Also during an outage, a stall, a fault, a wedge, or a closed admission (ic5 item 3). |
| A queue eviction | data plane | The queue was at capacity. `queue_evictions` counts it (d10). |
| A discard in the callback | data plane | `discarded_layout`, `discarded_stamp_basis`, or `discarded_admission` counts it (d12). |
| `transport_lost` growth | data plane | The total count of the RMW `message_lost` event, which Cyclone DDS takes from the DDS sample lost status (d12). |
| An outage, a stall, a fault, or a wedge with a feed open | control plane | `status().state` shows it. The feed stays open (d22, R14). |
| A frame of an epoch whose start failed later | control plane | A valid image at the verified profile. Later frames carry a higher epoch. `status().last_error` holds the start error. |

`[F]` `transport_lost` does not count every lost sample. Cyclone DDS fills the RMW event from `dds_get_sample_lost_status` (`ros:ros2/rmw_cyclonedds/rmw_cyclonedds_cpp/src/rmw_node.cpp:3943-3955`). When the reader history is full, Cyclone DDS replaces the oldest unread sample and raises no sample lost status (`ros:eclipse-cyclonedds/cyclonedds/src/core/ddsc/src/dds_rhc_default.c:854-875`). So a slow executor with the KEEP_LAST 2 reader loses samples that `transport_lost` does not show. A gap in `receive_seq` cannot show them either, because the sequence starts in the callback.

`[A]` R14 keeps a feed open during an outage. If Logan answers L9 with "close the feed", phase 1 adds code 12, `kOutage`, which `take` returns. No other code changes.

### Caller pattern

A feed consumer reads the result in this order:

1. If the result has an error, check `is_acquisition(e, kFeedClosed)`. If true, stop the loop.
2. If the error is another code, it is a program error. Log it and stop the loop.
3. If the optional is empty, read `controller.status()` when the empty results last longer than the consumer accepts.
4. If the optional has a frame, use it. Check `stream_epoch` against the last frame to see a restart.

A `feed_open` or `get_image` caller reads the result in this order:

1. On success, use the feed or the frame.
2. On `kFeedClosed`, stop. The controller has shut down.
3. On `kRequestBusy`, `kDeadlinePassed`, `kSubscriptionNotMatched`, a `kGateway` error, driver -3, or driver -15, retry later.
4. On `kStreamWedged`, `kFormatNotStreamable`, or `kProfileMismatch`, report to the operator and do not retry.
5. On another driver code, report it. A retry is allowed after `status()` shows `kIdle` or `kFaulted`.
