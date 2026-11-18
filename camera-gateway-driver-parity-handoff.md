# Handoff: camera gateway type reorganisation and full driver parity

You are picking up a piece of work in the `lkaising/venimapping` repository for Logan, the project owner. This brief was written at the end of a read-only analysis session. Nothing has been implemented yet. You have none of that conversation, so everything you need is here or in the code.

Read the code and the upstream driver yourself before you start. Then decide your own breakdown and ordering and carry the work out in whatever way you judge best. The design decisions below are settled; the approach is yours.

## 1. Goal and why

`src/venimapping_camera` contains a "camera gateway": a ROS-free C++ contract (`CameraGateway`) plus one implementation (`VimbaXCameraGateway`) that talks to Allied Vision's `vimbax_ros2_driver` over ROS 2 services. Higher layers of VeniMapping will use the contract and never see a ROS type.

Two things need to happen:

1. **Move the data types out of `camera_gateway.hpp`** into `include/venimapping_camera/types/`, one header per type, so the contract header holds only the abstract class.
2. **Bring the gateway to full coverage of the driver's 30 service endpoints.** Today it covers 10, hard-codes the feature module, and returns a partial camera status.

The reason for doing the types first is that Logan wants the type vocabulary settled and tidy before the remaining endpoints are filled in. The only consumer of the gateway today is a temporary probe executable, so renames and signature changes are cheap now and will not be later.

## 2. Repository state

- Repository: `lkaising/venimapping`. Work on branch **`feat/camera-gateway-driver-parity`**. At the time of writing it is at `d0a2626`, in sync with its remote, and 7 commits ahead of `main` with nothing to merge in.
- Do not open a pull request unless Logan asks. Do not push to any other branch.
- Commit style is Conventional Commits with a `camera` scope, for example `refactor(camera): move expected.hpp into types/`, `docs: add todo list for deferred camera gateway work`. History favours small, focused commits.

Files involved (all under `src/venimapping_camera/`):

| File | Role |
|---|---|
| `include/venimapping_camera/camera_gateway.hpp` | The contract. Currently also defines `FloatInfo`, `AccessMode`, `EnumInfo`, `CameraStatus`. |
| `include/venimapping_camera/types/error.hpp` | `Error` and `ErrorDomain`. |
| `include/venimapping_camera/types/expected.hpp` | `Expected<T>` alias. |
| `include/venimapping_camera/vimbax_camera_gateway.hpp` | Concrete gateway declaration; holds one `rclcpp::Client` per service. |
| `src/vimbax_camera_gateway.cpp` | Concrete gateway implementation. |
| `src/detail/gateway_util.{hpp,cpp}` | Private error builders and the `GatewayDiagnostic` enum. Not installed. |
| `src/camera_gateway_probe.cpp` | Temporary integration probe; the only consumer of the gateway. |
| `CMakeLists.txt`, `package.xml` | Build. A header-only `INTERFACE` target carries the ROS-free API; a library target carries the concrete gateway. |

Also relevant: `docs/todo.md` (parked ideas), `.clang-tidy`, `.clang-format`, `scripts/workspace.sh`, `scripts/tidy.sh`, `.devcontainer/Dockerfile`, `.github/workflows/container.yml`.

## 3. Conventions already in the code

Follow these; they are deliberate.

**Result and error vocabulary**
- C++23. Every gateway call returns `Expected<T>`, an alias for `std::expected<T, Error>`.
- `Error` carries a domain (`ErrorDomain::kDriver` or `kGateway`), an `int32` code and text. It is built only through `Error::from_driver` and `Error::from_gateway`.
- Inside the implementation, errors are built with `detail::driver_error(code, text)` and `detail::gateway_error(GatewayDiagnostic, text)` and wrapped in `std::unexpected(...)` at the call site.

**The `call` / `call_checked` pattern** (`src/vimbax_camera_gateway.cpp`)
- `call<Service>(client, request)` enforces the thread contract, starts one deadline shared by the service-availability wait and the response wait, and converts rclcpp exceptions into gateway errors.
- `call_checked<Service>` adds one step: if `response->error.code != 0`, it returns that driver error verbatim.
- Each public method builds a request, calls `call_checked`, and uses `.transform(...)` to turn the response into the return value.
- `connection_status_get()` is the only method that uses plain `call`, because `ConnectionStatus` is the only response with no `error` member. That stays true after this work: all 20 missing services have an `error` member.

**Gateway philosophy** (stated in the header comments; keep it)
- The gateway exposes primitives. It does not clamp, validate against metadata, retry, read back after a set, or classify driver errors. Driver failures pass through unchanged.
- No ROS request, response or message type appears in the public contract or in anything under `types/`.
- Calls are synchronous and bound to one worker thread via `bind_to_current_thread()`. New calls must go through the same path so they inherit the thread check and the timeout behaviour.

**Style**
- Namespace `venimapping::camera`; private helpers in `venimapping::camera::detail`.
- Types `CamelCase`; functions, variables, parameters and members `lower_case`; private members end in `_`; enumerators are `kCamelCase` (`ErrorDomain::kDriver`, `GatewayDiagnostic::kResponseTimeout`).
- `[[nodiscard]]` on every function that returns a value. `#pragma once`. Each file starts with the banner comment (Filename, Purpose, Copyright); copy the form from an existing file.
- Includes are grouped as standard library, then ROS, then project, separated by blank lines.
- `.clang-format`: Google base, no column limit, function braces on their own line, includes sorted but blocks preserved. Run the formatter rather than formatting by hand.
- `.clang-tidy`: `bugprone-*`, `cppcoreguidelines-*`, `google-*`, `misc-*`, `modernize-*`, `performance-*`, `readability-*` with a short exclusion list. `./scripts/workspace.sh check` treats any finding in the camera package as a failure. Two checks that matter for this work:
  - `google-default-arguments` is active, so virtual methods cannot have default arguments.
  - `performance-enum-size` is active, so an enum with a wide underlying type needs either a narrow base or a justified `NOLINT` (see the existing one in `gateway_util.hpp`).
  - `misc-include-cleaner` is disabled, so nothing will catch a missing include for you.

## 4. Upstream reference

- Repository: `https://github.com/alliedvision/vimbax_ros2_driver`
- Commit: `296bdf68ca180c033e2a8d4a1f08d312cfdb2acd`. This is also tag `v1.0.1-beta1`. The project's dev container installs tag `v1.0.1-beta1-venimapping.1` from the fork `https://github.com/lkaising/vimbax_ros2_driver`. That tag adds two fixes on top of this commit and leaves the message and service definitions unchanged, so the interface below is the one the code builds against.
- Clone it somewhere outside the project and read it. The files that matter:
  - `vimbax_camera_msgs/msg/*.msg` and `vimbax_camera_msgs/srv/*.srv`: the wire definitions.
  - `vimbax_camera/src/vimbax_camera_node.cpp`: where each service is registered and how each response is filled.
  - `vimbax_camera/include/vimbax_camera/vimbax_camera.hpp` and `vimbax_camera_helper.hpp`: the driver's own C++ class and plain structs.

### The 30 endpoints

Endpoint names are relative to the camera namespace and must be used verbatim. Every response except `ConnectionStatus` also carries `Error error` (`int32 code`, `string text`). "Module" means the request has a `FeatureModule feature_module` field.

Status today: **done** means implemented end to end; **module** means done but the module is hard-coded to remote device; **partial** and **missing** as they read.

| # | Endpoint | Service type | Request fields | Response fields | Today |
|---|---|---|---|---|---|
| 1 | `connected` | `ConnectionStatus` | none | `bool connected` (no `error`) | done |
| 2 | `status` | `Status` | none | 16 fields, see below | partial (7 of 16) |
| 3 | `stream_start` | `StreamStartStop` | none | none | missing |
| 4 | `stream_stop` | `StreamStartStop` | none | none | missing |
| 5 | `settings/save` | `SettingsLoadSave` | `string filename` | none | missing |
| 6 | `settings/load` | `SettingsLoadSave` | `string filename` | none | missing |
| 7 | `features/list_get` | `FeaturesListGet` | module | `string[] feature_list` | module |
| 8 | `feature_info_query` | `FeatureInfoQuery` | `string[] feature_names`, module | `FeatureInfo[] feature_info` | missing |
| 9 | `features/access_mode_get` | `FeatureAccessModeGet` | `string feature_name`, module | `bool is_readable`, `bool is_writeable` | module |
| 10 | `features/int_get` | `FeatureIntGet` | name, module | `int64 value` | missing |
| 11 | `features/int_set` | `FeatureIntSet` | name, module, `int64 value` | none | missing |
| 12 | `features/int_info_get` | `FeatureIntInfoGet` | name, module | `int64 min`, `int64 max`, `int64 inc` | missing |
| 13 | `features/float_get` | `FeatureFloatGet` | name, module | `float64 value` | module |
| 14 | `features/float_set` | `FeatureFloatSet` | name, module, `float64 value` | none | module |
| 15 | `features/float_info_get` | `FeatureFloatInfoGet` | name, module | `float64 min`, `max`, `inc`, `bool inc_available` | module |
| 16 | `features/string_get` | `FeatureStringGet` | name, module | `string value` | missing |
| 17 | `features/string_set` | `FeatureStringSet` | name, module, `string value` | none | missing |
| 18 | `features/string_info_get` | `FeatureStringInfoGet` | name, module | `int64 max_length` | missing |
| 19 | `features/bool_get` | `FeatureBoolGet` | name, module | `bool value` | missing |
| 20 | `features/bool_set` | `FeatureBoolSet` | name, module, `bool value` | none | missing |
| 21 | `features/enum_get` | `FeatureEnumGet` | name, module | `string value` | module |
| 22 | `features/enum_set` | `FeatureEnumSet` | name, module, `string value` | none | module |
| 23 | `features/enum_info_get` | `FeatureEnumInfoGet` | name, module | `string[] possible_values`, `string[] available_values` | module |
| 24 | `features/enum_as_int_get` | `FeatureEnumAsIntGet` | name, module, `string option` | `int64 value` | missing |
| 25 | `features/enum_as_string_get` | `FeatureEnumAsStringGet` | name, module, `int64 value` | `string option` | missing |
| 26 | `features/command_run` | `FeatureCommandRun` | name, module | none | missing |
| 27 | `features/command_is_done` | `FeatureCommandIsDone` | name, module | `bool is_done` | missing |
| 28 | `features/raw_get` | `FeatureRawGet` | name, module | `byte[] buffer`, `uint32 buffer_size` | missing |
| 29 | `features/raw_set` | `FeatureRawSet` | name, module, `byte[] buffer` | none | missing |
| 30 | `features/raw_info_get` | `FeatureRawInfoGet` | name, module | `int64 max_length` | missing |

Note that `feature_info_query` is the one feature endpoint that is not under `features/`.

`Status` response fields, in upstream order: `error`, `display_name`, `model_name`, `device_firmware_version`, `device_id`, `device_user_id`, `device_serial_number`, `interface_id`, `transport_layer_id` (all strings), `bool streaming`, `uint32 width`, `uint32 height`, `float64 frame_rate`, `string pixel_format`, `TriggerInfo[] trigger_info`, `string ip_address`, `string mac_address`. The gateway currently copies `model_name`, `device_serial_number`, `pixel_format`, `frame_rate`, `width`, `height` and `streaming`.

Messages:

- `FeatureModule`: `uint8 id`, with constants `MODULE_REMOTE_DEVICE=0`, `MODULE_SYSTEM=1`, `MODULE_INTERFACE=2`, `MODULE_LOCAL_DEVICE=3`, `MODULE_STREAM=4`.
- `FeatureInfo`: `string name`, `category`, `display_name`, `sfnc_namespace`, `unit`, `uint32 data_type`, `FeatureFlags flags`, `uint32 polling_time`.
- `FeatureFlags`: `bool flag_none`, `flag_read`, `flag_write`, `flag_volatile`, `flag_modify_write`.
- `TriggerInfo`: `string selector`, `mode`, `source`.
- `Error`: `int32 code`, `string text`.

`data_type` carries the SDK's `VmbFeatureDataType`: 0 unknown, 1 int, 2 float, 3 enum, 4 string, 5 bool, 6 command, 7 raw, 8 none.

## 5. Decisions already made

Logan has made these. Please implement them as written and do not reopen them. If you find one is unworkable in practice, say so in your report rather than quietly doing something else.

### Type layout

- One header per type under `include/venimapping_camera/types/`, named after the type. A type that only ever appears as a member of another type lives in its owner's header (as `ErrorDomain` already lives in `error.hpp`).
  - *Why:* an earlier proposal grouped types into buckets such as "feature results", and the bucket boundaries were arbitrary. Naming each header after its type removes those decisions and matches the direction of the last few commits.
- New headers: `feature_module.hpp`, `feature_info.hpp`, `feature_access_mode.hpp`, `feature_int_info.hpp`, `feature_float_info.hpp`, `feature_enum_info.hpp`, and one for the camera status (its filename is open item C below).
- `camera_gateway.hpp` becomes contract only, with no struct definitions.
- Every public header includes what it uses and compiles on its own, with no ROS headers before it.

### Naming philosophy

- **Not verbatim.** Keep upstream's structure and semantics, but use the project's own names and C++ types where they are clearer. Each type gets a comment naming its upstream source (the `.msg` or `.srv` it corresponds to).
- **Service endpoint names stay verbatim**, because they are wire addresses.

### Specific picks

- **`CameraStatus` keeps its name** and grows to all 16 upstream fields, with `TriggerInfo` defined alongside it. The seven existing field names stay as they are; the probe reads them.
- **`FeatureModule` is a required parameter, placed last:** `(feature_name, value, feature_module)`, and `(feature_name, feature_module)` for getters. It is a named enum in the project's enumerator style.
  - *Why required:* default arguments on virtual methods are flagged by `google-default-arguments`, and an explicit module fits a layer of primitives. Convenience belongs in a later layer.
  - *Why it exists at all:* stream, interface, system and local-device features are unreachable while the module is hard-coded.
- **Access mode fields are `readable` and `writable`** (upstream spells them `is_readable` and `is_writeable`).
- **Type names:** `FeatureAccessMode`, `FeatureIntInfo`, `FeatureFloatInfo`, `FeatureEnumInfo`. These replace today's `AccessMode`, `FloatInfo` and `EnumInfo`.
- **`FeatureFlags` is omitted from `FeatureInfo`,** because the upstream values are wrong (finding 1). Add a note to `docs/todo.md` recording the omission, the reason, and where the upstream bug is, so it can be revisited if upstream fixes it.
- **`FeatureInfo::data_type` is a named `FeatureDataType` enum** rather than a bare integer. It tells a caller which typed getter applies to a feature.
- **`ip_address` and `mac_address` are `std::optional<std::string>`.** An empty string on the wire becomes `std::nullopt` (finding 3).
- **Raw get returns `std::vector<std::uint8_t>`.** There is no struct for it (finding 2).
- **String info and raw info return the maximum length as an integer,** not a struct. The wire type is `int64`.
- **No `DriverError` struct.** `Error::from_driver(code, text)` already represents upstream's `Error` message.
- **No per-service request and response structs.** Request fields are parameters; a single-value response is returned as that value; an error-only response is `Expected<void>`.
  - *Why:* the driver's own C++ class (`VimbaXCamera`) has exactly this flattened shape, and only its node layer converts to `.srv` types. The gateway is effectively that class re-exposed across a service boundary. About two thirds of the 60 possible structs would be empty or hold one value, and every response's `error` duplicates what `Expected` already carries.
- **Out of scope:** events (`SubscribeEvent`, `UnsubscribeEvent`, `EventData`, the `events` and `feature_invalidation` topics) and image topics. They are topic-based and do not fit a blocking request/response gateway. The `Dummy` message and service are upstream placeholders; ignore them.

### What that means in total

The complete public type set is small: `FeatureModule`, `FeatureDataType`, `FeatureInfo`, `FeatureAccessMode`, `FeatureIntInfo`, `FeatureFloatInfo`, `FeatureEnumInfo`, `TriggerInfo`, `CameraStatus`, plus the existing `Error`, `ErrorDomain` and `Expected`. Of the 28 service types behind the 30 endpoints, 5 responses need a struct, 1 returns a list of `FeatureInfo`, 13 return a single value and 9 return only an error.

Details not listed here (field order, the names of the nine new `CameraStatus` fields, enumerator names, the exact integer types, how out-of-range wire values for the enums are handled, whether conversions live in the `.cpp` or in a private `src/detail/` file) are yours to decide within the naming philosophy.

## 6. Open items: recommendations Logan may overrule

These were never settled. Each has a recommendation. Unless the message that came with this brief says otherwise, proceed with the recommendation, and list all three in your report so Logan can change them. They are mechanical to change later.

**A. Gateway function names.**
Recommendation: do not rename the existing functions, and name the new ones by the same rule the existing feature functions already follow.
- Keep `camera_status_get`, `connection_status_get` and `features_list_get`.
- Feature functions use the snake_case of the upstream service type: `feature_int_get`, `feature_int_set`, `feature_int_info_get`, `feature_string_get`, `feature_string_set`, `feature_string_info_get`, `feature_bool_get`, `feature_bool_set`, `feature_enum_as_int_get`, `feature_enum_as_string_get`, `feature_command_run`, `feature_command_is_done`, `feature_raw_get`, `feature_raw_set`, `feature_raw_info_get`, `feature_info_query`.
- Where one service type serves two endpoints, use the endpoint: `settings_save`, `settings_load`, `stream_start`, `stream_stop`.

Reasoning: this keeps the `_get` and `_set` suffix convention already in the code, matches the decision to keep `CameraStatus`, and still lets a reader map each function to its wire address by name. The alternative is upstream-style names throughout (`status`, `connection_status`). One sub-question to surface: `feature_string_info_get` and `feature_raw_info_get` return a bare maximum length, so a name such as `feature_string_max_length_get` would describe the return value better at the cost of the name-to-endpoint mapping. The recommendation is to keep the upstream-derived name and document the return value.

**B. Parameter name: `name` or `feature_name`.**
Recommendation: `feature_name`. Once `feature_module` sits beside it, and other calls take `filename`, `option` and `feature_names`, the longer name is unambiguous and matches the upstream field. It is a parameter name, so no call site changes.

**C. Filename of the camera status header.**
Logan's list of new headers says `status.hpp`, but that list predates the decision to keep the name `CameraStatus`, and the layout rule says a header is named after its type. Recommendation: `types/camera_status.hpp`, following the rule. If Logan prefers the literal `status.hpp`, it is a one-line rename.

## 7. Upstream findings

Each of these was confirmed by reading the upstream source at `296bdf6`. Verify any you rely on.

1. **`FeatureFlags` is computed from the wrong field.** In `vimbax_camera/src/vimbax_camera.cpp` (around lines 1241 to 1249), each flag is derived from `vmb_info.featureDataType` instead of the feature's flags field. The resulting booleans reflect the data type's bit pattern, not the feature's access flags. This is why the flags are omitted. Current access state comes from `features/access_mode_get`.
2. **`FeatureRawGet.buffer_size` is redundant.** The node sets it to `buffer.size()`. ROS `byte[]` arrives in C++ as a vector of `unsigned char`.
3. **The IP and MAC addresses are optional inside the driver.** They are `std::optional<std::string>` in the driver's `Info` struct, and the node only sets the response field when a value is present. A camera without them (for example a non-GigE camera) produces empty strings on the wire.
4. **`FeatureIntInfoGet` has no `inc_available`.** Float info has it; int info does not. The asymmetry is upstream's, so `FeatureIntInfo` has three fields.
5. **`ConnectionStatus` has no `error` field,** and `connected` means only that the driver currently holds a camera object. It is the one call that cannot go through `call_checked`.
6. **`feature_info_query` with an empty `feature_names` list returns info for every feature in the module.** Worth documenting on the contract.
7. **Driver-side error codes you will see passed through:** an unknown module id yields `-7` (`VmbErrorBadParameter`); a call made while the camera is unavailable yields `-3` (`VmbErrorNotFound`).
8. **`features/command_run` blocks on the driver side.** The driver runs the command and then polls for completion every 100 ms for up to 1 second, returning `-12` (`VmbErrorTimeout`) if the command has not finished. A gateway timeout shorter than about a second can therefore expire first. Do not add policy for this; note it where a caller will see it.
9. **`settings/save` and `settings/load` take a path on the machine running the driver,** not the machine running the gateway.
10. **`features/list_get` is served from a cache built when the driver opens the camera.** The existing header comment already says so; keep it accurate now that the call takes a module.
11. **The driver's internal `Module` enum is in a different order from the wire constants.** The wire constants in `FeatureModule.msg` are what the gateway must send.
12. **String and raw maximum lengths are `uint32` inside the driver and `int64` on the wire.**

## 8. Loose ends to fix along the way

- **`camera_gateway.hpp` does not compile on its own.** It uses `std::vector` without including `<vector>`. Confirmed with `g++ -std=c++23 -fsyntax-only` against a file containing only that include. It builds today only because ROS headers happen to come first.
- **Other missing standard includes.** `vimbax_camera_gateway.hpp` uses `std::atomic`, `std::thread`, `std::chrono`, `std::unique_ptr`, `std::string` and `std::vector` without including their headers. `vimbax_camera_gateway.cpp` uses `std::format`, `std::max`, `std::future_status`, `std::string_view` and `std::make_shared` the same way. `types/error.hpp` uses `std::move` without `<utility>`. Check the rest as you go.
- **The probe needs updating.** `src/camera_gateway_probe.cpp` uses `FloatInfo`, the current function names and the current signatures, so it must change for the renames and the new module parameter. It is temporary by design, but it is the only way Logan can verify against real hardware, so consider having its read-only sequence exercise the new read-only calls. Anything that changes camera state must stay behind its existing `enable_writes` switch, and it should never load settings, stop the stream or run a command by default.
- **Request helpers hard-code the module.** `make_remote_device_request` and `make_remote_feature_request` in the `.cpp` set `MODULE_REMOTE_DEVICE`.
- **Comments that will go stale.** The Purpose line of `camera_gateway.hpp` mentions "the result types it returns"; the comment above the API target in `CMakeLists.txt` lists the headers it covers.
- **Leave alone:** the commented-out `Unexpected` helpers in `types/expected.hpp` and the asserts in `types/error.hpp`. Both are tracked in `docs/todo.md` as separate, deferred work.
- **For awareness:** `package.xml` declares `ament_cmake_gtest`, but the package has no tests.

## 9. Constraints and verification

**No camera.** Neither a cloud session nor the dev container has a camera attached, so the probe cannot be run there and no call can be verified against real hardware. Logan will do that on the Linux machine. Do not claim hardware behaviour you have not observed.

**Find out what your environment can build before you rely on it.** There are two likely cases:

- *Dev container or native Ubuntu 24.04.* ROS 2 Jazzy, the driver's message package, colcon and clang-tidy 20 are present. `./scripts/workspace.sh check` runs the colcon build, `colcon test` and clang-tidy, and is what CI runs. This is the full verification available without hardware.
- *A cloud session.* The one that wrote this brief had no ROS installation and no colcon; it had g++ 13.3 and clang-tidy and clang-format 18 only. In that state the ROS-free headers (`camera_gateway.hpp` and everything under `types/`) can be compiled standalone, but the concrete gateway and the probe cannot be built at all. Installing ROS Jazzy and building `vimbax_camera_msgs` from the upstream clone may or may not be possible there; that was not tried.

**CI will not run for you.** The `Container CI` workflow runs on pull requests and on pushes to `main`. Pushing this branch triggers nothing, and you are not to open a pull request unless asked.

**Runtime evidence.** A test that stands up a fake server for the `vimbax_camera_msgs` services would be the only way to exercise the request and response paths without a camera. It is not required. If you judge a small amount of it worthwhile, keep it camera-free; if not, say that runtime behaviour is unverified. One unexplored lead: the dev container's Dockerfile verifies that the Vimba X SDK ships a camera simulator, and CI runs a driver smoke test. Whether the driver can serve these endpoints from that simulator was not investigated, so do not count on it.

**Other constraints**
- Keep the public contract and everything under `types/` free of ROS types and ROS includes.
- Do not add clamping, retries, readback or validation to the gateway.
- Do not skip or weaken checks to get a clean result, and do not silence clang-tidy without a stated reason.

## 10. What done looks like

- `camera_gateway.hpp` contains the abstract class and no struct definitions.
- The types live in one-type-per-header files under `types/`, each with a comment naming its upstream source, and each public header compiles on its own without ROS headers.
- `CameraGateway` declares, and `VimbaXCameraGateway` implements, all 30 endpoints, using the verbatim endpoint names, with the feature module plumbed through every feature call.
- `CameraStatus` carries all 16 upstream fields, with `TriggerInfo` and the optional addresses.
- The probe is updated for the new API.
- `docs/todo.md` has the `FeatureFlags` note.
- The loose ends in section 8 are dealt with.
- The work is committed on `feat/camera-gateway-driver-parity` and pushed. No pull request.
- Whatever your environment allows has been run: at minimum the standalone header checks, and the full build and clang-tidy if ROS is available.

## 11. Report back

When you finish, or if you have to stop, report to Logan with:

- **What was implemented:** the headers created, the types and their fields, and the final list of gateway functions with signatures.
- **What was verified and how:** the commands you ran and their results. Separate clearly what was compiled, what passed clang-tidy, what was exercised at run time, and what was not verified at all. Nothing has been verified against a real camera unless you say how.
- **The three open items in section 6:** what you went with for each.
- **Anything left open:** judgement calls you made on details this brief left to you, anything in this brief that turned out to be wrong or unworkable, and anything you found upstream that contradicts it.
- **What Logan should run on the Linux machine** to verify against the camera.
