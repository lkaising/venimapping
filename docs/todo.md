# TODO

Ideas parked for later. None of these are blocking.

## Camera gateway

- [ ] **Explore introducing an `Unexpected` type.**
  Add `using Unexpected = std::unexpected<Error>;` to `expected.hpp` and have
  `detail::gateway_error` and `detail::driver_error` return it, so call sites can
  write `return detail::gateway_error(...);` without wrapping it in `std::unexpected(...)`.
  - Mark both helpers `[[nodiscard]]`. `std::unexpected<Error>` does not
    inherit `Error`'s `[[nodiscard]]`.
  - Delete the commented-out `make_driver_error` / `make_gateway_error` block in
    `expected.hpp` instead of moving it. It takes raw `int32_t` codes, which would
    lose the typed `GatewayDiagnostic`.
  - Watch out for lambda return types in `and_then` / `or_else` / `transform_error`.

- [ ] **Consider removing the asserts in `types/error.hpp`.**
  `Error::from_driver` and `Error::from_gateway` assert that `code != 0`. The
  internal callers already guarantee this, but the factories are public, so test
  fakes and future layers could still pass 0. If they are removed, also drop
  `#include <cassert>`.
