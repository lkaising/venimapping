# Building VeniMapping on macOS: design

This is the reference design for the dev container. The
[brief](macos-project-brief.md) says what to deliver and the
[milestones](macos-project-milestones.md) say in what order. This document
says why the design looks the way it does and what each piece must do.

Every fact below was checked against the Ubuntu machine and the upstream
repositories on 2026-09-02.

## 1. Goal

Reproduce the Ubuntu 24.04 build environment inside a container so that
`source scripts/env.sh && colcon build`, `scripts/tidy.sh`, and
`scripts/ide.sh` behave the same on an Apple Silicon Mac as on the Ubuntu
machine. Camera hardware is out of scope. The SDK's camera simulator stands
in for it.

## 2. How the Ubuntu machine is built

Nobody configured the Ubuntu machine by hand. Three pinned, idempotent
bootstrap tools produce it, and this repository's scripts assume their
output. That is the best possible starting point, because the environment
is already code. The container work is plumbing.

### 2.1 ROS 2 Jazzy underlay

`ros2-jazzy-bootstrap` builds about 350 packages from source into
`~/workspace/upstream/ros2-jazzy`. It adds `ros-perception/vision_opencv`
at tag `4.1.0` on top of the official manifest, which is what provides
`cv_bridge`. The driver requires `cv_bridge`, and the core manifest does not
include it.

This bootstrap refuses any architecture but amd64, and a build takes 30
minutes to 2 hours. The mentor uses the source tree for reading ROS code,
not because the build needs it. The container replaces this layer with apt
packages. See section 4.1.

### 2.2 Vimba X SDK

`vimbax-sdk-bootstrap` does not download the SDK. It registers an SDK
already unpacked at `~/workspace/upstream/vimbax-sdk` by writing two
root-owned files.

- `/etc/profile.d/VimbaX_GenTL_Path_64bit.sh` exports `GENICAM_GENTL64_PATH`
  pointing at `<sdk>/cti`.
- `/etc/udev/rules.d/99-AVTUSBTL.rules` grants USB permissions for vendor
  `1ab2`.

Before it writes anything it checks that the ELF architecture of the SDK
binaries matches the host. Its `verify` command runs `ListCameras_VmbC` and
passes when it finds at least one transport layer and one camera. The
simulator transport layer `VimbaCameraSimulatorTL.cti` provides a camera
with no hardware, so `verify` passes in a container.

The Ubuntu machine runs Vimba X 2026-2. Allied Vision serves the archives
from public URLs, listed in the brief with their sha256 sums. Each archive
has one top-level directory, `VimbaX_2026-2`, with `bin/`, `cti/`, `doc/`,
and `api/` inside it.

### 2.3 Driver overlay

`vimbax-ros2-driver-bootstrap` clones `alliedvision/vimbax_ros2_driver` and
builds it with colcon into `~/workspace/upstream/vimbax-ros2-driver`, on top
of the Jazzy underlay. Facts that matter for the container:

- It supports x86_64 and aarch64.
- `--ros-underlay` accepts a workspace root, an install prefix, or a
  `setup.bash` path. `/opt/ros/jazzy` is a valid value.
- It requires the underlay to provide `rclcpp`, `rclcpp_components`,
  `image_transport`, `camera_info_manager`, `rosidl_default_generators`,
  and `cv_bridge`. It warns without `rmw_cyclonedds_cpp`.
- It clones with `git clone --branch <ref>`, so `--ref` must name a tag or
  branch. The default is the `dev` branch because every release through
  1.0.2 uses `_Float64` in a way GCC 13 rejects. The Ubuntu machine has
  `dev` at commit 296bdf68, and upstream tags that commit `v1.0.1-beta1`.
  The container pins the tag, so a rebuild next year gets the same code.
- It refuses to run as root, and refuses a shell where `ROS_DISTRO`,
  `ROS_VERSION`, `AMENT_PREFIX_PATH`, or `COLCON_PREFIX_PATH` is set.
- `--yes` skips only the install confirmation. Adopting an existing
  workspace directory needs a terminal, and `--yes` cannot grant that.
- With a usable SDK, its `verify` stage runs `vimbax_camera_node` for 8
  seconds against the simulator, on `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`
  and a random domain id.

### 2.4 This repository's scripts

`scripts/env.sh` validates five things, in order, before it sources
anything.

```
~/workspace/upstream/ros2-jazzy/install/setup.bash          must be a file
~/workspace/upstream/vimbax-ros2-driver/install/setup.bash  must be a file
~/workspace/upstream/vimbax-sdk                             must be a directory
~/workspace/upstream/vimbax-sdk/cti/*.cti                   at least one match
GENICAM_GENTL64_PATH                                        must contain that cti directory
```

It then sources the underlay and the overlay, selects
`RMW_IMPLEMENTATION=rmw_cyclonedds_cpp` when that package is present, and
prints a green summary line. `scripts/ide.sh` pins `/usr/bin/c++` and
`/usr/bin/python3`. `scripts/tidy.sh` pins `/usr/bin/clang-tidy-20`,
`/usr/bin/clang-apply-replacements-20`, and `run-clang-tidy` on `PATH`.

`env.sh` checks paths and files, not where they came from. Any tree that
provides those files satisfies it. The whole design hangs on that.

## 3. Dev containers in short

VS Code splits into a local window and a backend called VS Code Server. The
Dev Containers extension reads `.devcontainer/devcontainer.json`, builds or
pulls the image, mounts the repository into a container, injects the server,
and reopens the window inside. Every terminal and every extension that
reads code then sees the container's filesystem and toolchain.

Linux containers need a Linux kernel, so each macOS runtime runs a small
Linux virtual machine. Docker Desktop, OrbStack, and Colima all do this. On
Apple Silicon the virtual machine is arm64, so the image builds and runs
natively with no emulation.

## 4. Design

### 4.1 The bootstraps provision the container

A Dockerfile could copy apt lists, clone commands, and colcon flags out of
the bootstraps. It would drift from them at the first change. Instead the
image creates a non-root user `dev` with passwordless sudo, which is what
the bootstraps expect on a real machine, and runs them.

| Layer | On the Ubuntu machine | In the image |
|---|---|---|
| Jazzy underlay | source build by `ros2-jazzy-bootstrap` | apt packages at `/opt/ros/jazzy`, plus one symlink |
| Vimba X SDK | manual unpack, then `bootstrap-vimbax-sdk install` | fetch archive for `TARGETARCH`, verify sha256, unpack, then `bootstrap-vimbax-sdk install --yes` |
| Driver overlay | `bootstrap-vimbax-ros2-driver install` | `bootstrap-vimbax-ros2-driver install --yes --ros-underlay /opt/ros/jazzy --ref v1.0.1-beta1` |
| Lint and IDE toolchain | apt `clang-tidy-20` and friends | the same packages at the same paths |
| VeniMapping | this repository, built by hand | bind-mounted at container start, built by the same scripts |

The underlay is the one deliberate substitution. The apt distribution is
the same Jazzy release stream, it exists for amd64 and arm64, and every
package the driver bootstrap checks for is available. The base image
already has `ros-jazzy-ros-base`, which brings `rclcpp`, `launch_ros`, and
`rosidl_default_generators`. The image must add `ros-jazzy-cv-bridge`,
`ros-jazzy-image-transport`, `ros-jazzy-camera-info-manager`,
`ros-jazzy-rclcpp-components`, `ros-jazzy-rmw-cyclonedds-cpp`, and
`ros-jazzy-ament-cmake-gtest`.

### 4.2 Filesystem layout

`$HOME` is `/home/dev`. The SDK and the driver overlay land at the real
paths `env.sh` expects. One symlink bridges the underlay.

```
/home/dev/workspace/upstream/
├── ros2-jazzy/install  -> /opt/ros/jazzy      # setup.bash resolves through the link
├── vimbax-ros2-driver/install/...             # built in-image by the driver bootstrap
└── vimbax-sdk/{api,bin,cti,doc}               # unpacked in-image, registered by the SDK bootstrap
```

The SDK bootstrap registers `GENICAM_GENTL64_PATH` through `/etc/profile.d`,
which only login shells read. The Dockerfile must also set it with `ENV`,
so that VS Code tasks and plain `docker exec` shells see it. With that in
place, `env.sh`, `ide.sh`, and `tidy.sh` run unmodified.

### 4.3 Dockerfile shape

```dockerfile
FROM ros:jazzy                 # official, Ubuntu 24.04, amd64 and arm64
ARG TARGETARCH                 # amd64 | arm64, set by the builder
ARG VIMBAX_VERSION=2026-2
ARG DRIVER_REF=v1.0.1-beta1

# 1. apt: ros-jazzy-* set from 4.1, build-essential, ros-dev-tools, sudo,
#    gdb, ccache, python3-venv, and clang-tidy-20 + clang-apply-replacements-20
#    + clang-tools-20 from apt.llvm.org (noble)
# 2. user dev (UID 1000, passwordless sudo), underlay symlink from 4.2
# 3. SDK: fetch VimbaX_Setup-${VIMBAX_VERSION}-Linux{64,_ARM64}.tar.gz by
#    TARGETARCH, check sha256, unpack with the top directory stripped,
#    clone vimbax-sdk-bootstrap, install --yes, then ENV GENICAM_GENTL64_PATH
# 4. driver: clone vimbax-ros2-driver-bootstrap, then with ROS_DISTRO and
#    friends unset for this one command:
#    install --yes --ros-underlay /opt/ros/jazzy --ref ${DRIVER_REF}
```

Everything is pinned. The base image, the SDK version and checksum, the
driver tag, and the LLVM major version. Rebuilding with the same arguments
gives the same image. That is the reproducibility claim.

The built image contains the SDK, and the SDK license does not allow
redistribution. Each machine builds locally, or the image goes to a private
registry. It never goes to a public one.

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

The named volumes exist because bind mounts on macOS cross the virtual
machine boundary on every file access. A colcon build writes many small
files, and those three directories are where they go. `.gitignore` already
excludes them, so nothing on the Mac side needs them. Milestone 6 measures
whether the volumes matter enough to keep.

`ide.sh` runs inside the container and writes `.vscode/` with container
paths. VS Code reads those files from inside the container, so the paths
match.

### 4.5 CI

The image is exactly what a GitHub Actions job needs. This repository and
the three bootstraps are public, so the `ubuntu-24.04` and `ubuntu-24.04-arm`
hosted runners are free. A workflow that builds the image on both and runs
the milestone pass tests inside it gives three things.

- The student gets a red or green signal that does not depend on their
  laptop.
- The mentor can review a milestone without a Docker host.
- The environment definition is checked on every push instead of trusted.

The SDK fetch in CI is the same public URL the Dockerfile uses. The built
image stays in the runner and is discarded. No registry is involved.

### 4.6 Runtime on the Mac

OrbStack and Docker Desktop both run dev containers on Apple Silicon.
Docker Desktop is what most guides assume. OrbStack is the smaller install.
The student chooses in milestone 6 and records why. Either way the Dev
Containers extension needs a `docker` command on `PATH`.

## 5. Known traps

These were verified by reading the base image and the bootstrap sources.
The milestones repeat them where they apply.

1. `ros:jazzy` sets `ENV ROS_DISTRO=jazzy`. The driver bootstrap refuses
   to run when it is set. Unset it for that one `RUN` step.
2. Ubuntu 24.04 images already have a user `ubuntu` at UID 1000. Creating
   `dev` at 1000 collides with it.
3. `--yes` on both bootstraps covers only the install confirmation. Any
   prompt that guards an existing directory or registration needs a
   terminal, which a Docker build does not have. Keep each bootstrap layer
   fresh.
4. `GENICAM_GENTL64_PATH` from `/etc/profile.d` reaches only login shells.
   `env.sh` hard-fails without it. Set it with `ENV` as well.
5. Git refuses to operate on a checkout owned by another UID. A bind mount
   from the Mac can trigger that. `updateRemoteUserUID` fixes the common
   case, and `safe.directory` covers the rest.

## 6. What the container can and cannot do

With no hardware attached it can build both packages, run `colcon test`,
run `scripts/tidy.sh check` and `fix`, run `scripts/ide.sh`, and run
`vimbax_camera_node` against the simulator. The driver bootstrap's own
smoke test does exactly that, so `ros2 launch venimapping_bringup
camera.launch.py` has a real target, and the gateway probe can run against
it.

It cannot reach a physical camera. USB3 Vision does not pass through the
runtime virtual machine, and GigE Vision across the virtual machine's NAT
is not worth the complexity here. It cannot show RViz or rqt without extra
display setup. It cannot discover DDS peers on the lab network without
deliberate network configuration. All three are out of scope.

## 7. Open decisions

The brief lists the decisions that belong to the student. Two more are
recorded here because they need input from the mentor when they come up.

- When to move the driver ref. The pin is a beta tag from November 2024.
  Allied Vision has not shipped a release that compiles under GCC 13 as of
  September 2026. Check the releases page at each stretch milestone.
- Whether a private registry is worth setting up. Not until a second
  machine or CI needs to skip the 10 to 20 minute local build.

## 8. References

- VS Code Dev Containers: <https://code.visualstudio.com/docs/devcontainers/containers>
- Dev Container specification: <https://containers.dev>
- Official `ros` images: <https://hub.docker.com/_/ros>
- ROS 2 Jazzy apt install: <https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html>
- Vimba X SDK downloads: <https://www.alliedvision.com/en/support/software-downloads/vimba-x-sdk/vimba-x>
- `alliedvision/vimbax_ros2_driver`: <https://github.com/alliedvision/vimbax_ros2_driver>
- LLVM apt packages: <https://apt.llvm.org>
- GitHub arm64 hosted runners for public repositories: <https://github.blog/changelog/2025-08-07-arm64-hosted-runners-for-public-repositories-are-now-generally-available/>
- The bootstraps:
  <https://github.com/lkaising/ros2-jazzy-bootstrap>,
  <https://github.com/lkaising/vimbax-sdk-bootstrap>,
  <https://github.com/lkaising/vimbax-ros2-driver-bootstrap>
