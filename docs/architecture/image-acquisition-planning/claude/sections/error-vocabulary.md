## Error vocabulary

Acquisition adds one contractual error domain, `ErrorDomain::kAcquisition`, with eleven fixed codes (d6, ic5). Driver errors still pass unchanged, and gateway diagnostics stay private. A missing frame is a successful empty result, not an error.

Labels: `[F]` is a fact with a citation. `[A]` is a working assumption. `[Q]` is an open question.

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
| 1 | `kFeedClosed` | control plane | `feed_open`, `get_image` | The request came after `shutdown()` | Stop. The acquisition stack is closed. |
| 2 | `kDeadlinePassed` | control plane | `get_image` | No admitted frame before `GetImageOptions::deadline` (d26) | Retry later, or report. Read `status()` to see an outage. |
| 3 | `kStreamWedged` | control plane | `feed_open`, `get_image` | The controller is in `kWedged` (d19) | The operator restarts the driver process. The controller clears the state after it sees the restart. |
| 4 | `kFormatNotStreamable` | control plane | `feed_open`, `get_image`, `AcquisitionController::create` | `PixelFormat` is outside the allowed formats that are on the driver gate (d19 item 1) | Fix the settings file or the profile file. No retry. |
| 5 | `kProfileMismatch` | control plane | `feed_open`, `get_image` | A value still differs after the corrective writes (d18 item 6) | Compare the settings file with the profile file. No retry. |
| 6 | `kSubscriptionNotMatched` | control plane | `feed_open`, `get_image` | No matched publisher after 1000 ms (d17) | Check that the driver runs under the same namespace. Retry after that. |
| 7 | `kWrongThread` | data plane | `take`, `try_take` | A call from a thread other than the first consumer thread (ic2 rule 4) | Fix the caller. This is a program error. |
| 8 | `kTriggerNoFrame` | control plane | Nothing in phase 1 | Reserved for the phase 2 software trigger (d27) | None in phase 1. |
| 9 | `kRequestBusy` | control plane | `feed_open`, `get_image` | A feed is already open, or a get image is already outstanding (d13) | Wait for the other request, or close the other feed. |
| 10 | `kInvalidArgument` | data plane | `subscribe`, `ImageFrame::create` | Capacity outside 1 to 4, or a bad frame layout | Fix the argument. This is a program error. |
| 10 | `kInvalidArgument` | control plane | `AcquisitionController::create`, `feed_open` | A bad option in `ControllerOptions`, or a bad `FeedOptions::capacity` passed through from `subscribe` | Fix the option. |
| 11 | `kSourceCreateFailed` | data plane | `VimbaXFrameSource::create` | The ROS subscription could not be made | The composition root reports and exits. |

1. The data plane returns only codes 1, 7, 10, and 11. It never returns `kDriver` or `kGateway` errors (ic5 item 1).
2. The image callback never returns an error. It counts each discard in `FrameSourceStats` (ic5 item 4).
3. `kWrongThread` and `kInvalidArgument` are program errors. A test finds them. A running system does not retry them.

### Errors that pass through the controller

The controller returns gateway errors from its readback, its writes, and its stream calls unchanged (ic5 item 2). A caller sees these classes:

| Domain and code | Typical cause | Caller action |
|---|---|---|
| `kDriver`, -3 (`VmbErrorNotFound`) | The camera is not available. A disconnect is in progress (facts 1.9.5). | Retry after `status()` leaves `kOutage`, or after a fixed wait. |
| `kDriver`, another code | The driver refused one call. | Report the code and the text. The controller has already reconciled the stream state (d19). |
| `kGateway`, any code | The driver services do not answer, or a call timed out. | Check that the driver process runs. Retry after that. |

1. A caller must classify an error by `domain()` first and then by `code()`. A `kGateway` code number has no meaning to the caller (`src/venimapping_camera/src/gateway_support/gateway_errors.hpp:15`).
2. -15 (`VmbErrorInvalidCall`) never reaches a caller from a stream call. The controller turns it into `kWedged`, and the next request returns `kStreamWedged`.
3. -18 (`VmbErrorNotSupported`) from a format refusal at start cannot occur, because the format check comes first (c1 §3.1 item 2).

### Results that are not errors

| Result | Where | Meaning |
|---|---|---|
| Empty `std::optional` from `take` or `try_take` | data plane | No frame in the timeout. Also during an outage, a stall, a wedge, or a closed admission (ic5 item 3). |
| A queue eviction | data plane | The queue was at capacity. `queue_evictions` counts it (d10). |
| A discard in the callback | data plane | `discarded_layout`, `discarded_stamp_basis`, or `discarded_admission` counts it (d12). |
| `transport_lost` growth | data plane | DDS rejected samples at the reader (d12). |
| An outage, a stall, or a wedge with a feed open | control plane | `status().state` shows it. The feed stays open (d22, R14). |

`[A]` R14 keeps a feed open during an outage. If Logan answers L9 with "close the feed", phase 1 adds code 12, `kOutage`, which `take` returns. No other code changes.

### Caller pattern

A feed consumer reads the result in this order:

1. If the result has an error, check `is_acquisition(e, kFeedClosed)`. If true, stop the loop.
2. If the error is another code, it is a program error. Log it and stop the loop.
3. If the optional is empty, read `controller.status()` when the empty results last longer than the consumer accepts.
4. If the optional has a frame, use it. Check `stream_epoch` against the last frame to see a restart.

A get image caller reads the result in this order:

1. On success, use the frame.
2. On `kRequestBusy`, `kDeadlinePassed`, `kSubscriptionNotMatched`, a `kGateway` error, or driver -3, retry later.
3. On `kStreamWedged`, `kFormatNotStreamable`, or `kProfileMismatch`, report to the operator and do not retry.
