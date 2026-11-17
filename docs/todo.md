# TODO

Ideas parked for later. None of these are blocking.

## Camera gateway

- [ ] **Explore introducing an `Unexpected` type.**
  Add `using Unexpected = std::unexpected<Error>;` to `expected.hpp` and have
  `detail::gateway_error` return it, so call sites can write
  `return detail::gateway_error(...);` without wrapping it in `std::unexpected(...)`.
  - Mark `gateway_error` `[[nodiscard]]`. `std::unexpected<Error>` does not
    inherit `Error`'s `[[nodiscard]]`.
  - Delete the commented-out `make_driver_error` / `make_gateway_error` block in
    `expected.hpp` instead of moving it. It takes raw `int32_t` codes, which would
    lose the typed `GatewayDiagnostic`.
  - Watch out for lambda return types in `and_then` / `or_else` / `transform_error`.

- [ ] **Revisit renaming `check_driver_error` → `driver_error`.**
  A plain rename would be misleading, because the function can return success.
  Instead, move the `code != 0` check into `call_checked` and make `driver_error`
  a pure builder that mirrors `gateway_error`. This is best done after the
  `Unexpected` decision, since that decides the return type.

- [ ] **Include what you use in `camera_gateway.hpp`.**
  It uses `std::vector`, `std::string` and `std::uint32_t` without including
  `<vector>`, `<string>` or `<cstdint>`. It only compiles because other headers
  happen to pull them in.
