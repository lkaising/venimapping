# Building VeniMapping on macOS — Investigation, Architecture, and Plan

**Status:** analysis / proposal only — no implementation yet.
**Scope:** make the *build environment* reproducible on a macOS machine so that
`colcon build`, `clang-tidy`, and the IDE tooling behave identically to the
native Ubuntu 24.04 machine. Camera hardware access is explicitly out of scope.

---

## 1. TL;DR

What you remember from your previous workplace is, almost certainly, **VS Code
Remote Development** — specifically the **Dev Containers** flavor (and possibly
Remote-SSH layered on top of it). The "local server" you SSH'd into was most
likely the Linux VM that Docker Desktop transparently runs on every Mac; the
"VS Code window on a server" was the VS Code Server that the Dev Containers
extension injects into a running container. This is a mature, well-trodden,
first-class-supported workflow, and it maps onto this repository cleanly.

**Recommendation:** add a `.devcontainer/` directory to this repo containing a
`Dockerfile` (Ubuntu 24.04 + ROS 2 Jazzy + source-built `vimbax_ros2_driver` +
Vimba X SDK + LLVM 20 tooling, laid out exactly the way `scripts/env.sh`
expects) and a `devcontainer.json`. On the Mac, install a container runtime
(OrbStack or Docker Desktop) plus the VS Code Dev Containers extension. Open
the repo, click "Reopen in Container," and you get a terminal where
`source scripts/env.sh && colcon build` works verbatim — same paths, same
compiler, same clang-tidy 20, same everything. The same image doubles as a CI
image later, essentially for free.

The rest of this document is the audit of what the environment actually
requires, how the pieces of the remembered workflow fit together, the proposed
architecture in detail, macOS-specific caveats (Apple Silicon vs Intel), the
alternatives I considered and why I rejected them, and a phased implementation
plan.

---

## 2. Audit: what the environment contract actually is today

Everything below is derived from the current branch — `scripts/env.sh`,
`scripts/ide.sh`, `scripts/tidy.sh`, the two `package.xml` files, and the
`CMakeLists.txt` files. This is the exact contract any macOS solution has to
reproduce.

### 2.1 Operating system and toolchain

| Requirement | Where it comes from |
|---|---|
| Ubuntu 24.04 (Noble) | ROS 2 Jazzy's Tier-1 platform; everything below assumes it |
| C++23 compiler at `/usr/bin/c++` | `target_compile_features(... cxx_std_23)`; `ide.sh` pins `IDE_COMPILER_PATH=/usr/bin/c++` (GCC 13 on Noble) |
| CMake ≥ 3.20 | both `CMakeLists.txt` files |
| `colcon` + `ament_cmake` | build tool for the workspace |
| `clang-tidy-20` at `/usr/bin/clang-tidy-20` | `tidy.sh`, `ide.sh` (settings.json pins the path); `clang-apply-replacements-20` for fix mode |
| `run-clang-tidy` on `PATH` | `tidy.sh` |
| Python 3 at `/usr/bin/python3` | `ide.sh` JSON writers; ROS 2 launch |
| Bash (scripts refuse non-Bash shells) | `env.sh` guard |

### 2.2 The upstream layout (`~/workspace/upstream`)

`scripts/env.sh` validates and sources a very specific directory layout under
`${HOME}/workspace/upstream`, and refuses to proceed without all of it:

```
${HOME}/workspace/upstream/
├── ros2-jazzy/install/setup.bash          # ROS 2 Jazzy underlay (colcon-style install tree)
├── vimbax-ros2-driver/install/setup.bash  # source-built alliedvision/vimbax_ros2_driver overlay
└── vimbax-sdk/
    └── cti/*.cti                          # Vimba X GenTL producers
```

Additional environment expectations:

- `GENICAM_GENTL64_PATH` must already contain `~/workspace/upstream/vimbax-sdk/cti`
  (on the Ubuntu machine this presumably comes from the SDK's
  `/etc/profile.d/VimbaX_GenTL_Path_64bit.sh`, which `ide.sh` deliberately
  avoids when capturing the IDE env).
- `RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` is auto-selected when the CycloneDDS
  RMW package is present, so the container should install it.
- An optional project virtualenv at `.venv/` and project overlay at
  `install/` are sourced when present.

### 2.3 Package dependencies

- `venimapping_camera`: `rclcpp`, `vimbax_camera_msgs` (from the driver
  overlay), `ament_cmake_gtest` for tests.
- `venimapping_bringup`: `launch`, `launch_ros`, `ros2launch`, and
  `vimbax_camera` (exec-only — the driver node the launch file starts).

**Key observation:** the project's *compile-time* dependency on Allied Vision
is only `vimbax_camera_msgs` (service/message types). The gateway talks to the
driver over ROS 2 services. The Vimba X SDK and its GenTL producers are
runtime concerns for the *driver node*, not for compiling this repo — but
`env.sh` refuses to run without them, and building the driver overlay itself
does need the SDK. So a faithful environment includes all of it.

### 2.4 One notable fork in the road: source-built vs apt-installed Jazzy

The underlay path `~/workspace/upstream/ros2-jazzy/install/setup.bash` implies
ROS 2 Jazzy is **built from source** on the Ubuntu machine (an apt install
would live at `/opt/ros/jazzy/setup.bash`). This matters for the container
design — see §4.3 for the options. It's also one of my open questions for you
(§8): if there's no hard reason for the source build, the container gets much
simpler and faster to build by using the official binary packages and
symlinking the expected path.

---

## 3. Decoding the remembered workflow

Your recollection — "SSH onto a server, launch a VS Code window on that
server, which has a Dockerized container with all dependencies, then run
`build.sh` inside it" — describes the standard **VS Code Remote Development**
architecture. Here's how the pieces actually fit, because it clarifies which
variant we want:

1. **VS Code's client/server split.** VS Code always runs your editor UI
   locally, but it can run its backend (the "VS Code Server": file watcher,
   language servers, terminals, debuggers) somewhere else — inside a
   container, on an SSH host, or in WSL. Extensions like C/C++ IntelliSense
   run *in the backend*, so they see the container's headers and compilers,
   not your Mac's.

2. **Dev Containers extension.** Reads `.devcontainer/devcontainer.json` in
   the repo, builds/starts the described Docker image, mounts your source
   tree into it, injects the VS Code Server, and reopens your window
   "inside" the container. Your terminal in VS Code is now a shell in
   Ubuntu 24.04 with everything installed. This is the "Dockerized container
   that has all the dependencies in the file system."

3. **Where Docker actually runs on a Mac.** Linux containers need a Linux
   kernel, so every macOS container runtime (Docker Desktop, OrbStack,
   Colima) runs a lightweight, invisible Linux VM and executes containers
   inside it. That VM is the "local server running on my macOS computer" you
   remember. Some setups do literally SSH into a local or remote VM/host and
   attach from there (VS Code Remote-SSH → then attach to a container), which
   would explain the SSH step; other workplaces put the containers on a
   beefy shared Linux build server and had developers Remote-SSH into it.
   Both variants use identical container definitions — which is one of the
   strengths of this approach: the same `.devcontainer/` works locally on
   the Mac, on a remote build server, and in CI.

So the feature you're asking for is: **commit a machine-readable definition of
the Ubuntu build environment into the repo, and let any machine — macOS
included — instantiate it in a container.** That's the whole idea.

---

## 4. Proposed architecture

### 4.1 Overview

```
┌─────────────────────────── macOS host ───────────────────────────┐
│  VS Code (UI)          Container runtime (OrbStack / Docker      │
│      │                 Desktop) → lightweight Linux VM           │
│      │ Dev Containers ext.        │                              │
│      ▼                            ▼                              │
│  ┌──────────────── Ubuntu 24.04 dev container ────────────────┐  │
│  │  VS Code Server, terminals, cpptools, clangd/clang-tidy-20 │  │
│  │                                                            │  │
│  │  /home/dev/workspace/upstream/                             │  │
│  │    ├── ros2-jazzy/install/      (underlay, baked in image) │  │
│  │    ├── vimbax-ros2-driver/install/  (built in image)       │  │
│  │    └── vimbax-sdk/cti/*.cti     (SDK, baked in image)      │  │
│  │                                                            │  │
│  │  /home/dev/venimapping   ← bind mount of the repo on macOS │  │
│  │    ├── build/, install/, log/  ← named volume (Linux-only  │  │
│  │    │                             artifacts, fast I/O)      │  │
│  │    └── source scripts/env.sh && colcon build   ← unchanged │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

Design principle: **the container replicates the Ubuntu machine's layout
exactly**, so `env.sh`, `ide.sh`, and `tidy.sh` run unmodified. The repo's
scripts stay the single source of truth for how to build; the container is
just a portable place to run them.

### 4.2 The Dockerfile (sketch, not implementation)

Multi-stage, roughly:

```dockerfile
# Stage 0: base — Ubuntu 24.04 with ROS 2 Jazzy
FROM ros:jazzy AS base            # official OSRF image, ubuntu:24.04, multi-arch (amd64+arm64)
# + apt: build-essential, cmake, colcon, rmw-cyclonedds-cpp, ament-cmake-gtest, ...
# + LLVM apt repo: clang-tidy-20, clang-apply-replacements-20, clang-tools (run-clang-tidy)

# Stage 1: vimba-sdk — fetch & unpack the Vimba X SDK for TARGETARCH
#   VimbaX_Setup-<ver>-Linux64.tar.gz or -Linux_ARM64.tar.gz
#   → /opt/vimbax  (cti/ inside)

# Stage 2: driver — colcon build alliedvision/vimbax_ros2_driver (pinned tag)
#   against the Jazzy underlay + SDK

# Stage 3: dev — assemble the developer image
#   - non-root user `dev` (UID remapped by the dev container tooling)
#   - /home/dev/workspace/upstream/{ros2-jazzy,vimbax-ros2-driver,vimbax-sdk}
#     laid out exactly as env.sh expects (symlinks to /opt/... are fine:
#     env.sh checks for files/dirs, not for physical directories)
#   - GENICAM_GENTL64_PATH baked via /etc/profile.d, matching the Ubuntu box
#   - ccache, gdb, valgrind, python venv tooling, etc.
```

Key choices inside this sketch:

- **Pin everything.** Base image by digest or at least distro tag, the driver
  by git tag/commit, the SDK by version, LLVM by major version. The whole
  point is that "works on my machine" becomes "works in image `sha256:…`".
- **`.cti` and `GENICAM_GENTL64_PATH` are installed even though no camera
  will ever be reachable** — because `env.sh` validates them, and because the
  driver node can at least start and enumerate zero cameras, which keeps the
  runtime story honest.
- **The SDK cannot be redistributed casually.** Allied Vision's download is
  behind their site/EULA. The Dockerfile should download it at build time
  (URL or a `--build-arg`/local tarball), and the resulting image should live
  in a *private* registry if pushed at all. Building locally on each Mac is
  perfectly fine and avoids the question entirely.

### 4.3 The underlay decision: apt Jazzy vs source-built Jazzy

Two ways to satisfy `~/workspace/upstream/ros2-jazzy/install/setup.bash`:

| Option | How | Pros | Cons |
|---|---|---|---|
| **A. Binary (recommended)** | `ros:jazzy` apt packages at `/opt/ros/jazzy`; symlink `~/workspace/upstream/ros2-jazzy/install → /opt/ros/jazzy` | Image builds in minutes; official multi-arch images; trivially updatable | Not bit-identical to your source-built underlay; if your source build carries patches or non-default flags, behavior could differ |
| **B. Source build in image** | Replicate your `ros2-jazzy` colcon build inside the Dockerfile | Maximum fidelity to the current machine | 1–2 h image build, large image, you must encode the exact checkout/flags of your current underlay, arm64 build is on you |

`env.sh` only requires that `setup.bash` exists and sources cleanly, so
Option A satisfies the contract as written. I recommend **A**, unless the
source build exists for a specific reason (patched packages, a subset build,
non-default CMake flags) — flagged as open question Q1 in §8. Even then, a
middle path exists: keep A for daily macOS development and accept the small
fidelity gap, since the Ubuntu machine remains the integration truth.

The same logic applies to the driver overlay, except there Option B (source
build, pinned tag) is the *only* option and is cheap — it's one small
workspace.

### 4.4 The `devcontainer.json` (sketch)

```jsonc
{
  "name": "venimapping",
  "build": { "dockerfile": "Dockerfile", "context": ".." },
  "remoteUser": "dev",
  "updateRemoteUserUID": true,               // files you create belong to you
  "workspaceFolder": "/home/dev/venimapping",
  "workspaceMount": "source=${localWorkspaceFolder},target=/home/dev/venimapping,type=bind",
  "mounts": [
    // build artifacts stay inside the Linux VM's filesystem: much faster than
    // writing them back through the macOS bind mount, and they're Linux
    // binaries a macOS host has no use for anyway
    "source=venimapping-build,target=/home/dev/venimapping/build,type=volume",
    "source=venimapping-install,target=/home/dev/venimapping/install,type=volume",
    "source=venimapping-log,target=/home/dev/venimapping/log,type=volume"
  ],
  "customizations": {
    "vscode": {
      "extensions": ["ms-vscode.cpptools", "ms-python.python"]
      // settings.json / c_cpp_properties.json still come from scripts/ide.sh
    }
  },
  "postCreateCommand": "bash -lc 'source scripts/env.sh && colcon build ... && ./scripts/ide.sh'"
}
```

Notes:

- **Bind-mount I/O is the one real performance trap on macOS.** File I/O
  across the macOS↔VM boundary (gRPC-FUSE/VirtioFS) is markedly slower than
  native. Source trees are fine; `build/` churn is not. Putting `build/`,
  `install/`, `log/` on named volumes keeps compiles at near-native speed
  while the sources stay live-editable from the Mac side. (OrbStack's
  VirtioFS is fast enough that this matters less, but the volumes cost
  nothing and make Docker Desktop tolerable too.)
- **`ide.sh` works unmodified** and its output gains a nice property: paths
  like `/usr/bin/c++`, `/usr/bin/clang-tidy-20`, and
  `${HOME}/workspace/upstream/...` are now *guaranteed* correct because the
  image defines them. The generated `.vscode/` stays untracked (already in
  `.gitignore`), and since cpptools runs inside the container, IntelliSense
  resolves against the container's headers — the whole reason this
  architecture works.
- One wrinkle to verify at implementation time: `ide.sh` hardcodes
  `${HOME}/workspace/upstream/...` in `VENIMAPPING_UPSTREAM_PREFIXES`, and
  `env.sh` hardcodes the same root. As long as the container user's `$HOME`
  is `/home/dev` and the layout lives there, nothing needs changing. If you
  ever want host-side flexibility, a tiny follow-up would be to let an env
  var (e.g. `VENIMAPPING_UPSTREAM`) override the root — optional, not
  required for this design.

### 4.5 Container runtime on the Mac

Any OCI runtime works; the Dev Containers extension just needs a `docker`
(or compatible) CLI:

| Runtime | Notes |
|---|---|
| **OrbStack** (recommended) | Fastest VM + file sharing on macOS today, tiny resource footprint, drop-in `docker` CLI. Free for personal use; paid for commercial. |
| **Docker Desktop** | The default everyone knows; fine. License required for larger companies; free for small orgs/personal. Enable VirtioFS + Rosetta options. |
| **Colima** | Free/OSS (Lima-based). Works well with Dev Containers; a bit more hands-on. |
| **Rancher Desktop / Podman Desktop** | Workable; Dev Containers support is more finicky (Podman needs extra settings). |

The repo shouldn't care which one a developer picks — that's the point of
standardizing on the devcontainer spec.

### 4.6 Apple Silicon vs Intel, and the architecture question

- **Apple Silicon (M-series)** runs `linux/arm64` containers *natively* (no
  emulation). ROS 2 Jazzy is Tier-1 on Ubuntu 24.04 arm64, the official
  `ros:jazzy` image is multi-arch, LLVM 20 ships arm64 debs, and Allied
  Vision ships `VimbaX_Setup-…-Linux_ARM64.tar.gz`. So the entire stack
  builds natively on arm64. The Dockerfile should select the SDK tarball via
  `TARGETARCH`.
- **Intel Macs** run `linux/amd64` natively; same Dockerfile, other branch of
  `TARGETARCH`.
- **Fidelity caveat:** an arm64 build is not the same binary artifact as the
  amd64 build on your Ubuntu box. For day-to-day development (does it
  compile, do tests pass, does clang-tidy agree) this is irrelevant and the
  native speed is worth it. If you ever want bit-for-bit platform parity
  from a Mac, Docker Desktop/OrbStack can run `--platform linux/amd64`
  images under Rosetta 2 — it works but is several times slower, and I would
  *not* make it the default. The better answer for parity is CI (§6).

### 4.7 What deliberately does not work on the Mac

Named explicitly so nobody is surprised:

- **Camera hardware.** USB3 Vision passthrough into the container VM is
  somewhere between painful and impossible; GigE Vision could theoretically
  reach a camera on the LAN via bridged networking, but per your framing this
  is a non-goal. The environment still contains the SDK/driver, so the
  driver node starts and the full stack *builds*; it just enumerates zero
  cameras.
- **GUI tools** (RViz, rqt) need extra plumbing (X11/VNC/`xvfb`). Out of
  scope; can be added later if wanted.
- **Multi-host DDS discovery** from inside the VM to robots on the LAN is
  its own adventure. Out of scope for a build environment.

---

## 5. Alternatives considered (and why not)

1. **RoboStack (conda-forge ROS 2 native on macOS).** Real project, genuinely
   runs ROS 2 on macOS without VMs. Rejected: different compiler (Apple
   Clang), different sysroot, no Ubuntu fidelity, and the Vimba X ROS driver
   + GenTL stack is Linux-targeted here. You'd be debugging a *third*
   platform, not reproducing your first one.
2. **Full Linux VM (UTM/Parallels/Multipass) with Ubuntu 24.04.** Faithful
   but heavy: manual provisioning drift, no repo-committed definition, worse
   editor integration than dev containers, and every developer's VM rots
   differently. The devcontainer *is* a VM under the hood, minus all of
   those downsides.
3. **Remote-SSH to a shared Linux build server.** Great complement (it's
   likely what your old workplace layered on top), and the same
   `.devcontainer/` works there too. But as the *primary* answer it requires
   maintaining a server and being online; the local container needs neither.
4. **Nix / nix-ros-overlay.** Reproducibility gold standard, but a steep
   adoption cost and an awkward fit with a proprietary SDK and a
   colcon-centric workflow. Overkill for a two-package workspace.
5. **Cross-compiling from macOS with an Ubuntu sysroot.** Fragile bespoke
   toolchain work with none of the "identical environment" guarantees.
   Nobody should do this in 2026.

---

## 6. Bonus: the same image is your CI

Once the Dockerfile exists, a GitHub Actions workflow can build the image (or
pull it from a private registry / GHCR with the SDK caveat from §4.2) and run
`colcon build && colcon test && scripts/tidy.sh check` on every PR — on
`linux/amd64`, which also closes the Apple-Silicon parity gap from §4.6
without any Mac ever emulating x86. This falls out of the design for free and
is, frankly, half the reason to do it even if the Mac feature didn't exist.

---

## 7. Implementation plan (when you green-light it)

**Phase 1 — Containerize the environment (the core, ~a day of iteration):**
1. `.devcontainer/Dockerfile` — base `ros:jazzy`, apt deps, LLVM 20 repo,
   Vimba X SDK per `TARGETARCH`, source-build `vimbax_ros2_driver` at a
   pinned tag, assemble `/home/dev/workspace/upstream/…` layout, profile.d
   for `GENICAM_GENTL64_PATH`, non-root `dev` user, ccache.
2. Validate *on Linux first* (this container is Ubuntu-agnostic): clean
   `source scripts/env.sh` → green summary line, `colcon build`, `colcon
   test`, `scripts/tidy.sh check`, `scripts/ide.sh` — all unmodified.

**Phase 2 — Dev container UX:**
3. `.devcontainer/devcontainer.json` per §4.4 (mounts, remoteUser, UID
   remap, extensions, postCreate).
4. Test on an actual Mac: OrbStack or Docker Desktop + Dev Containers
   extension → "Reopen in Container" → build + IntelliSense + clang-tidy all
   green. Measure build times with and without the named build volumes to
   confirm the mount strategy.
5. A short `docs/macos-quickstart.md`: install runtime, install extension,
   reopen in container, `source scripts/env.sh`, build. Five steps, no
   Ubuntu machine required.

**Phase 3 — Optional hardening:**
6. CI workflow reusing the image (§6).
7. Pre-built image in a private registry so "Reopen in Container" pulls
   instead of building (minutes → seconds for new machines); needs the SDK
   licensing decision.
8. Optional `VENIMAPPING_UPSTREAM` override in `env.sh`/`ide.sh` if you ever
   want the same scripts to serve differently-laid-out hosts.

Nothing in Phases 1–2 modifies any existing file: the entire feature is
additive (`.devcontainer/`, docs). That also means zero risk to the current
Ubuntu workflow — the native machine keeps working exactly as it does today,
and the container is an alternative front door to the same scripts.

---

## 8. Open questions for you

1. **Why is the Jazzy underlay source-built** (`~/workspace/upstream/
   ros2-jazzy/install`) rather than apt's `/opt/ros/jazzy`? Patches? Habit?
   A subset build? This decides §4.3 Option A vs B. If it's "no strong
   reason," Option A makes the image dramatically cheaper.
2. **Which Vimba X SDK version and `vimbax_ros2_driver` ref** are on the
   Ubuntu machine right now? The image should pin the same ones
   (`vimbaxviewer --version` / SDK dir name, and the driver checkout's
   `git describe`).
3. **Your Mac's chip** — Apple Silicon or Intel? Both are covered, but it
   decides which image arch gets tested first and whether the Rosetta
   discussion in §4.6 is ever relevant to you.
4. **Docker runtime preference/licensing** — is Docker Desktop acceptable
   for your situation, or should the quickstart standardize on OrbStack or
   Colima?
5. **Private registry availability** (GHCR on this repo would do) — only
   matters for Phase 3 pre-built images, and interacts with the SDK
   redistribution question.

---

## 9. References

- VS Code Dev Containers: <https://code.visualstudio.com/docs/devcontainers/containers>
- Dev Container spec (editor-agnostic, also used by CI/Codespaces): <https://containers.dev>
- Official ROS docker images (`ros:jazzy`, multi-arch): <https://hub.docker.com/_/ros>
- ROS 2 Jazzy platforms (Ubuntu 24.04 amd64/arm64 Tier 1): <https://docs.ros.org/en/jazzy/Installation.html>
- Allied Vision Vimba X SDK downloads (Linux64 and Linux ARM64 tarballs): <https://www.alliedvision.com/en/support/software-downloads/vimba-x-sdk/vimba-x>
- `alliedvision/vimbax_ros2_driver` (colcon-buildable source): <https://github.com/alliedvision/vimbax_ros2_driver>
- LLVM apt packages for Ubuntu Noble (clang-tidy-20): <https://apt.llvm.org>
