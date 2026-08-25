# Vimba X camera gateway improvements

## Goal

Make the gateway's thread contract and timeout behavior predictable without changing its current threading model.

## Tasks

- [x] Return thread-contract violations through `Expected`.
  - Remove the assertions from `bind_to_current_thread()` and `check_callable_from_this_thread()`.
  - Keep the existing `kThreadContractViolation` errors for calls before binding, repeated binding, and calls from the wrong thread.
  - Update the header comments to describe one consistent error path.

- [x] Use one deadline for each gateway operation.
  - Start one deadline when `call()` begins.
  - Share the remaining time between the service-availability wait and the response wait.
  - Update the timeout documentation to cover the total operation time.

- [x] Explicitly initialize the unbound thread ID.
  - Initialize `bound_thread_` with `std::thread::id{}` at its declaration.
  - Keep the default thread ID as the unbound sentinel.

## Completion checks

- Thread-contract mistakes return errors instead of terminating the process.
- The configured timeout bounds the complete gateway operation.
- The unbound thread state is visible where `bound_thread_` is declared.
- The package builds, tidy reports no new findings, and the manual deadline check passes.
