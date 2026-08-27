# Building VeniMapping on macOS

**Status:** design document. Nothing here is implemented; no existing file changes.
**Goal:** reproduce the Ubuntu 24.04 build environment on a macOS machine so that
`source scripts/env.sh && colcon build`, `scripts/tidy.sh`, and `scripts/ide.sh`
behave exactly as they do on the native machine. Camera hardware is out of scope.

Sources for this analysis: this repository's `scripts/` and package manifests,
plus the three provisioning tools that define the Ubuntu machine —
[`ros2-jazzy-bootstrap`](https://github.com/lkaising/ros2-jazzy-bootstrap),
[`vimbax-ros2-driver-bootstrap`](https://github.com/lkaising/vimbax-ros2-driver-bootstrap),
and [`vimbax-sdk-bootstrap`](https://github.com/lkaising/vimbax-sdk-bootstrap).

---

## 1. Summary

The workflow you remember from your previous workplace is VS Code Remote
Development, in its Dev Containers form: the repository carries a
`.devcontainer/` definition of the build environment, a container runtime on
the Mac instantiates it inside a hidden Linux VM, and VS Code runs its backend
(terminals, IntelliSense, clang-tidy) inside the container while the UI stays
native. Proposal:

- Add `.devcontainer/Dockerfile` + `devcontainer.json` to this repo.
- Inside the image, provision the driver overlay and SDK registration by
  **running your existing bootstrap tools**, not by duplicating their logic in
  Dockerfile commands. The bootstraps stay the single source of truth for how
  the environment is constructed.
- Replace only the Jazzy source build with the binary apt distribution
  (`/opt/ros/jazzy` + a symlink at the path `env.sh` expects). You confirmed
  the source build exists for code-reading, not as a build requirement, and it
  is the one bootstrap that cannot run on Apple Silicon (§2.1) or in
  reasonable image-build time.
- One Dockerfile serves both Mac architectures via `TARGETARCH`; Apple Silicon
  builds natively on arm64 (§5).

The container passes a stronger acceptance test than "it compiles": the Vimba X
SDK ships a camera simulator, and the driver bootstrap's smoke test runs
`vimbax_camera_node` against it. The full stack — build, tidy, IDE config,
driver node runtime — is verifiable on a Mac with no camera attached.

---

## 2. The environment, as actually defined

The Ubuntu machine is not hand-configured; it is the output of three pinned,
idempotent bootstrap tools plus this repo's own scripts. That is the best
possible starting position for containerization, because the environment is
already code. What each layer contributes:

### 2.1 ROS 2 Jazzy underlay — `ros2-jazzy-bootstrap`

- Source-builds ~350 packages into `~/workspace/upstream/ros2-jazzy`, from the
  `ros2.repos` manifest at tag `release-jazzy-20260618`, colcon `release`
  mixin, rosdep skip keys `fastcdr rti-connext-dds-6.0.1 urdfdom_headers`.
- Overlays `ros-perception/vision_opencv` at tag `4.1.0` onto the manifest —
  this is what provides **`cv_bridge`**, which the Vimba X driver requires and
  which is not part of the core `ros2.repos` set.
- Installs the official dev-tool apt set (`ros-dev-tools`, pytest/flake8/mypy
  packages).
- **Refuses any architecture but amd64**, refuses root, refuses shells with a
  ROS environment already sourced. Build takes 30 min–2 h and ~13–15 GB.

### 2.2 Vimba X SDK — `vimbax-sdk-bootstrap`

- Does **not** download or install the SDK. It registers an SDK already
  unpacked at `~/workspace/upstream/vimbax-sdk` by writing exactly two
  root-owned files:
  - `/etc/profile.d/VimbaX_GenTL_Path_64bit.sh` — exports
    `GENICAM_GENTL64_PATH` pointing at `<sdk>/cti`;
  - `/etc/udev/rules.d/99-AVTUSBTL.rules` — USB permissions (vendor `1ab2`).
- Validates that the SDK binaries' ELF architecture matches the host.
- `verify` runs `ListCameras_VmbC` and passes when at least one transport
  layer and one camera are found — the SDK's **camera simulator** provides a
  camera with no hardware attached.

Consequence for the container: something else must acquire the SDK tarball
(Allied Vision publishes `VimbaX_Setup-<ver>-Linux64.tar.gz` and
`-Linux_ARM64.tar.gz`), and the bootstrap then registers it exactly as on
metal.

### 2.3 Driver overlay — `vimbax-ros2-driver-bootstrap`

- Clones and colcon-builds `alliedvision/vimbax_ros2_driver` into
  `~/workspace/upstream/vimbax-ros2-driver`, `--symlink-install`, on top of
  the Jazzy underlay.
- **Ref `dev`, deliberately**: driver releases through 1.0.1 use `_Float64`
  in a way GCC 13 on Ubuntu 24.04 rejects.
- Supports **x86_64 and aarch64** (unlike the Jazzy bootstrap).
- Underlay resolution accepts a workspace root, an **install prefix**, or a
  `setup.bash` path — so `/opt/ros/jazzy` is a valid `--ros-underlay` as-is.
- Validates that the underlay provides `rclcpp`, `rclcpp_components`,
  `image_transport`, `camera_info_manager`, `rosidl_default_generators`, and
  `cv_bridge` (hard error), and warns without `rmw_cyclonedds_cpp`.
- SDK is optional at build time (`vmbc_interface` vendors the VmbC headers);
  required at runtime. With a usable SDK, `verify` runs the node for 8 s
  against the simulator, on `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` and a
  randomized domain ID.
- Refuses root; uses sudo only for rosdep-installed system packages.
  `install --yes` is non-interactive on a fresh machine.

### 2.4 This repository's contract (`scripts/`)

`env.sh` validates and sources, in order: the underlay setup at
`~/workspace/upstream/ros2-jazzy/install/setup.bash`, the driver overlay
setup, `GENICAM_GENTL64_PATH` containing `~/workspace/upstream/vimbax-sdk/cti`
with at least one `.cti` present, then optionally the project overlay and
`.venv`. It selects `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` when available.
`ide.sh` pins `/usr/bin/c++` (GCC 13 on Noble) and `/usr/bin/python3`;
`tidy.sh` and the generated VS Code settings pin `/usr/bin/clang-tidy-20`,
`clang-apply-replacements-20`, and `run-clang-tidy`. The packages need
CMake ≥ 3.20, C++23, colcon, and `ament_cmake_gtest`.

Note that `env.sh` checks paths and files, not provenance: any directory tree
that provides those `setup.bash` files and `.cti` producers satisfies it.
That is the hook the container design hangs on.

---

## 3. The remembered workflow, decoded

VS Code splits into a local UI and a backend ("VS Code Server") that can run
elsewhere — over SSH, in WSL, or in a container. The Dev Containers extension
reads `.devcontainer/devcontainer.json` from the repo, builds or pulls the
image, mounts the source tree, injects the server, and reopens the window
inside the container; every terminal and every extension that inspects code
(cpptools, clangd, Python) now sees the container's filesystem and toolchain.

The pieces of your recollection map as follows. Linux containers need a Linux
kernel, so every macOS runtime (Docker Desktop, OrbStack, Colima) runs a
lightweight VM — that is the "local server running on my Mac." The "VS Code
window on a server" is the injected VS Code Server. The SSH step was either
Remote-SSH into that VM or into a shared Linux build host; both attach to
containers the same way, from the same container definition. The `build.sh`
inside the container corresponds to `source scripts/env.sh && colcon build`
here.

The feature, stated precisely: commit a machine-readable definition of the
Ubuntu environment into this repo, so any machine with a container runtime can
instantiate it. The definition already half-exists — it is the three
bootstraps. The container work is mostly plumbing them into an image.

---

## 4. Design

### 4.1 Principle: the bootstraps provision the container

A naive Dockerfile would re-encode apt lists, clone commands, and colcon
invocations, and would drift from the bootstraps the moment either changed.
Instead the image build creates a non-root `dev` user with passwordless sudo
(the bootstraps refuse root and expect sudo, exactly as on metal) and runs:

| Layer | On the Ubuntu machine | In the image |
|---|---|---|
| Jazzy underlay | `ros2-jazzy-bootstrap` source build | **apt binary Jazzy** at `/opt/ros/jazzy` + symlink (see 4.2) |
| Vimba X SDK | manual unpack + `bootstrap-vimbax-sdk install` | fetch tarball for `TARGETARCH`, unpack to `~/workspace/upstream/vimbax-sdk`, run `bootstrap-vimbax-sdk install --yes` |
| Driver overlay | `bootstrap-vimbax-ros2-driver install` | `bootstrap-vimbax-ros2-driver install --yes --ros-underlay /opt/ros/jazzy` (prefix form is supported) |
| Lint/IDE toolchain | apt: `clang-tidy-20` etc. | same apt packages, same paths |
| VeniMapping | this repo, built by hand | bind-mounted at container start; built by the same `scripts/` |

The bootstraps' host checks cooperate with this: a fresh image layer has no
sourced ROS environment, a non-root user, Ubuntu 24.04, and (for the driver
bootstrap) a supported architecture on both amd64 and arm64. Their
idempotence also gives Docker layer caching clean stage boundaries. The udev
rule the SDK bootstrap writes is inert in a container; harmless.

Two deviations from metal, both deliberate:

1. **Underlay from apt, not source.** You confirmed the source build is for
   code-diving, not a build requirement. The apt distribution is the same
   Jazzy release stream the source tag pins, is multi-arch (the Jazzy
   bootstrap is amd64-only and would take hours per image build), and
   `cv_bridge` plus everything the driver bootstrap checks for is available
   as `ros-jazzy-*` packages: `ros-jazzy-ros-base`, `ros-jazzy-cv-bridge`,
   `ros-jazzy-image-transport`, `ros-jazzy-camera-info-manager`,
   `ros-jazzy-rmw-cyclonedds-cpp`, `ros-jazzy-ament-cmake-gtest`,
   `ros-jazzy-launch*`. When you want to dig through ROS sources, the
   source checkout on the Ubuntu machine remains the place to do it — the
   container is a build environment, not a replacement for that habit.
2. **Driver ref pinned, not `dev`.** `dev` is a moving branch; an image
   rebuilt next month would silently pick up different driver code. The image
   should pass `--ref <commit or tag>` — today that means pinning the `dev`
   commit the Ubuntu machine currently has (`git -C
   ~/workspace/upstream/vimbax-ros2-driver/src/vimbax_ros2_driver rev-parse
   HEAD`), revisited when Allied Vision ships a release that compiles under
   GCC 13.

### 4.2 Satisfying `env.sh` without modifying it

`env.sh` hardcodes `~/workspace/upstream/{ros2-jazzy/install, 
vimbax-ros2-driver/install, vimbax-sdk}`. In the image, `$HOME` is
`/home/dev`, the driver overlay and SDK land at the real expected paths, and
the underlay is bridged with one symlink:

```
/home/dev/workspace/upstream/
├── ros2-jazzy/install  -> /opt/ros/jazzy        # setup.bash resolves; env.sh only checks -f
├── vimbax-ros2-driver/install/…                  # built in-image by the driver bootstrap
└── vimbax-sdk/cti/*.cti                          # unpacked in-image, registered by the SDK bootstrap
```

One subtlety: the SDK bootstrap registers `GENICAM_GENTL64_PATH` via
`/etc/profile.d`, which only login shells read, and `env.sh` hard-fails when
the variable is missing. The Dockerfile should additionally set it with `ENV`
so every process — login shell or not, VS Code task or terminal — sees it.
`scripts/env.sh`, `ide.sh`, and `tidy.sh` then run byte-for-byte unmodified,
and `ide.sh`'s pinned paths (`/usr/bin/c++`, `/usr/bin/clang-tidy-20`)
become guarantees the image enforces rather than assumptions about a host.

### 4.3 Dockerfile shape

```dockerfile
FROM ros:jazzy                        # official, Ubuntu 24.04, multi-arch
ARG TARGETARCH                        # amd64 | arm64
ARG VIMBAX_VERSION=2026-2             # pin to whatever the Ubuntu machine runs
ARG DRIVER_REF=<pinned commit>

# 1. apt layer: ros-jazzy-* set from §4.1, build-essential, ros-dev-tools,
#    clang-tidy-20 + clang-apply-replacements-20 + clang-tools (run-clang-tidy)
#    from apt.llvm.org for noble, gdb, ccache, python3-venv, sudo
# 2. non-root user `dev`, passwordless sudo, underlay symlink from §4.2
# 3. SDK: fetch/COPY VimbaX_Setup-${VIMBAX_VERSION}-Linux{64,_ARM64}.tar.gz
#    per TARGETARCH → ~/workspace/upstream/vimbax-sdk;
#    clone vimbax-sdk-bootstrap → install --yes;  ENV GENICAM_GENTL64_PATH
# 4. driver: clone vimbax-ros2-driver-bootstrap →
#    install --yes --ros-underlay /opt/ros/jazzy --ref ${DRIVER_REF}
#    (its verify stage exercises the node against the SDK simulator)
```

Everything is pinned: base image, SDK version, driver commit, LLVM major.
Rebuilding the image with the same arguments is the reproducibility story.

Distribution: the SDK sits behind Allied Vision's EULA, so the built image
must not be pushed to a public registry. Either each machine builds locally
(fine — one-time cost, roughly 10–20 minutes, dominated by the driver build)
or the image goes to a private registry (GHCR private on this account) and
"Reopen in Container" becomes a pull.

### 4.4 `devcontainer.json` shape

```jsonc
{
  "name": "venimapping",
  "build": { "dockerfile": "Dockerfile" },
  "remoteUser": "dev",
  "updateRemoteUserUID": true,
  "workspaceFolder": "/home/dev/venimapping",
  "workspaceMount": "source=${localWorkspaceFolder},target=/home/dev/venimapping,type=bind",
  "mounts": [
    "source=venimapping-build,target=/home/dev/venimapping/build,type=volume",
    "source=venimapping-install,target=/home/dev/venimapping/install,type=volume",
    "source=venimapping-log,target=/home/dev/venimapping/log,type=volume"
  ],
  "customizations": { "vscode": { "extensions": [
    "ms-vscode.cpptools", "ms-python.python"
  ]}},
  "postCreateCommand": "bash -lc 'source scripts/env.sh && colcon build --symlink-install && ./scripts/ide.sh'"
}
```

The named volumes are the one macOS-specific decision that matters. Bind
mounts cross the macOS↔VM boundary (VirtioFS) and are markedly slower than
the VM's native filesystem; source files are read once per compile and are
fine, but `build/` churn is not. Keeping `build/`, `install/`, and `log/` on
volumes keeps compile and link speed native while the sources stay
live-editable from the Mac side. They are Linux artifacts with no value on
the host anyway. This mirrors what `.gitignore` already says about them.

`ide.sh` runs in `postCreateCommand`, so `.vscode/` (untracked, as now) is
regenerated inside the container where its pinned paths are correct, and
cpptools — running in the container — resolves headers against the real
underlay and overlay trees.

### 4.5 Container runtime on the Mac

The Dev Containers extension needs a Docker-compatible CLI; the repo should
not care which provides it.

| Runtime | Notes |
|---|---|
| OrbStack | Fastest VM and file sharing on macOS; drop-in `docker` CLI. Commercial use is paid. |
| Docker Desktop | The default choice; enable VirtioFS. Free for personal use and small orgs. |
| Colima | Free/OSS, Lima-based; works with Dev Containers with minor setup. |

Any of the three works for this design. For a single personal machine, pick
whichever you prefer; the quickstart doc can name one to reduce decisions.

---

## 5. Intel vs Apple Silicon

Your instinct — that the Mac's architecture shouldn't matter — is achievable,
with one asterisk.

The same Dockerfile builds for both: `TARGETARCH` selects the SDK tarball
(Allied Vision ships Linux64 and Linux_ARM64), apt Jazzy and the LLVM 20
packages are multi-arch, and the driver bootstrap explicitly supports
aarch64. An Apple Silicon Mac builds and runs the arm64 image natively at
full speed; an Intel Mac does the same with the amd64 image. Nothing in the
developer experience differs.

The asterisk: the produced binaries differ by architecture. For everything
this environment is for — compiling, unit tests, clang-tidy, the simulator
smoke test — that is irrelevant. The place where amd64 parity with the
Ubuntu machine is actually enforced should be CI (§7), which runs the same
image on amd64 runners. Running the amd64 image on Apple Silicon via
Rosetta emulation works but is several times slower; treat it as an escape
hatch for reproducing an amd64-only bug locally, not as a mode anyone
develops in.

The only component that is genuinely amd64-only is the Jazzy *source-build*
bootstrap, and it is out of the container path by design. If you ever want
it inside a container too (e.g. to reproduce the metal machine exactly for
an amd64 CI job), its host check is the only obstacle on amd64 — it already
runs fine under Docker's non-root + sudo pattern.

---

## 6. What the container can and cannot do

Can, with no hardware attached:

- Build both packages, run `colcon test`, `scripts/tidy.sh check|fix`,
  `scripts/ide.sh` — the full development loop.
- Run `vimbax_camera_node` against the SDK's camera simulator, which is how
  the driver bootstrap's own smoke test passes. `ros2 launch
  venimapping_bringup camera.launch.py` has a real, testable target.
- Run the gateway probe against that simulated driver node.

Cannot, and out of scope by your framing:

- Reach a physical camera. USB3 Vision passthrough into the runtime VM is
  effectively unavailable; GigE Vision across the VM NAT boundary is
  theoretically bridgeable but not worth the complexity here.
- GUI tools (RViz, rqt) without extra display plumbing.
- Cross-host DDS discovery to machines on the LAN, without deliberate
  network configuration.

---

## 7. CI for free

The image is exactly what a GitHub Actions job needs: build it (or pull from
a private registry) on an amd64 runner, then run `colcon build`, `colcon
test`, and `scripts/tidy.sh check` on every push. This closes the
architecture-parity gap from §5 without any Mac emulating anything, and it
turns the environment definition into something continuously verified rather
than trusted. The SDK licensing constraint from §4.3 applies to where the
image is stored, not to whether CI can use it.

---

## 8. Implementation plan

Additive only — no existing file changes, no risk to the Ubuntu workflow.

**Phase 1 — image.**
`.devcontainer/Dockerfile` per §4.3. Acceptance: inside the built container,
`scripts/env.sh` prints its green summary (`jazzy=active driver=active
gentl=active rmw=rmw_cyclonedds_cpp`), `colcon build` and `colcon test`
succeed, `scripts/tidy.sh check` runs clang-tidy 20, and the driver
bootstrap's verify stage has passed against the simulator. This phase is
testable on any Docker host, no Mac required.

**Phase 2 — dev container UX.**
`devcontainer.json` per §4.4, then validation on the Silicon Mac: runtime
installed, "Reopen in Container", build, IntelliSense resolving `rclcpp` and
`vimbax_camera_msgs` headers, format-on-save and clang-tidy behaving per the
generated settings. Measure a full build with and without the named volumes
to confirm the mount strategy. Write `docs/macos-quickstart.md` (install
runtime → install extension → reopen in container → build).

**Phase 3 — optional hardening.**
CI workflow (§7); private-registry prebuilt image so container startup is a
pull; a decision on the driver ref pin cadence.

Open items to settle at implementation time, none blocking the design:

1. The exact SDK version and driver `dev` commit currently on the Ubuntu
   machine, so the image pins match reality (`ls ~/workspace/upstream/
   vimbax-sdk`, `git rev-parse HEAD` in the driver checkout).
2. Whether `--ref` accepts a bare commit SHA or needs a tag/branch —
   trivially verifiable against the bootstrap; worst case the Dockerfile
   checks out the SHA before invoking it.
3. Runtime choice for the quickstart (OrbStack vs Docker Desktop — §4.5).
4. Whether to bother with a private registry now or leave local builds as
   the only path until a second machine or CI needs the image.

---

## 9. References

- VS Code Dev Containers: <https://code.visualstudio.com/docs/devcontainers/containers>
- Dev Container spec (editor-agnostic; same files drive Codespaces/CI): <https://containers.dev>
- Official `ros:jazzy` images (multi-arch): <https://hub.docker.com/_/ros>
- ROS 2 Jazzy platforms (Ubuntu 24.04 amd64/arm64, Tier 1): <https://docs.ros.org/en/jazzy/Installation.html>
- Vimba X SDK downloads (Linux64 / Linux_ARM64): <https://www.alliedvision.com/en/support/software-downloads/vimba-x-sdk/vimba-x>
- `alliedvision/vimbax_ros2_driver`: <https://github.com/alliedvision/vimbax_ros2_driver>
- LLVM apt packages for Noble (clang-tidy-20): <https://apt.llvm.org>
- Provisioning tools this design builds on:
  <https://github.com/lkaising/ros2-jazzy-bootstrap>,
  <https://github.com/lkaising/vimbax-ros2-driver-bootstrap>,
  <https://github.com/lkaising/vimbax-sdk-bootstrap>
