# Building VeniMapping on macOS: project brief

| | |
|---|---|
| Mentor | Logan Kaising |
| Student | |
| Start | |
| Cadence | one check-in a week, one pull request per milestone |
| Budget | about 3 to 5 hours a week, about 10 weeks |

## What this project is

VeniMapping is a ROS 2 Jazzy workspace for an Allied Vision camera. Today it
builds on one Ubuntu 24.04 machine. Three tools provision that machine, and
this repository's `scripts/` folder assumes the layout they produce.

Your job is to make the same build work on an Apple Silicon Mac. You will do
that with a dev container. The repository will carry a machine-readable
definition of the Ubuntu environment. Any computer with a container runtime
will then build VeniMapping from that definition. VS Code will run its
terminals and C++ tooling inside the container while the window stays native.

The camera hardware stays out of scope. The Vimba X SDK ships a camera
simulator, and the driver runs against it with no camera attached. That is
the runtime you will test against.

## What you will deliver

1. `.devcontainer/Dockerfile`. Builds the environment on amd64 and arm64.
2. `.devcontainer/devcontainer.json`. Opens this repository inside that image
   from VS Code.
3. A GitHub Actions workflow. Builds the image on both architectures and
   runs the acceptance checks on every push.
4. `docs/macos-quickstart.md`. Takes a new user from an empty Mac to a
   working build with no other help.
5. One pull request per milestone. Each one records the decisions you made
   and the questions you parked.

The milestones, with a pass test for each, are in
[macos-project-milestones.md](macos-project-milestones.md). The design you
will implement is in
[macos-dev-environment-design.md](macos-dev-environment-design.md).

## Definition of done

The project is complete when all of the following are true.

- The CI workflow is green on `ubuntu-24.04` and `ubuntu-24.04-arm`.
- Inside the container, `source scripts/env.sh` prints
  `jazzy=active driver=active gentl=active rmw=rmw_cyclonedds_cpp`.
- Inside the container, `colcon build`, `./scripts/ide.sh`, and
  `./scripts/tidy.sh check` exit 0.
- The driver bootstrap's verify stage passes against the camera simulator.
- On your Mac, "Reopen in Container" gives a VS Code window where IntelliSense
  resolves `rclcpp` and `vimbax_camera_msgs` headers.
- A second person follows the quickstart on a clean Mac and reaches a green
  build.

## Fixed constraints

These are decisions the mentor made. Work inside them. If one blocks you,
say so at the check-in instead of working around it.

- **The bootstraps provision the container.** The image runs the three
  bootstrap tools. It does not copy their apt lists, clone commands, or
  colcon flags into Dockerfile lines. The bootstraps stay the only place that
  says how the environment is built, so the container cannot drift from the
  Ubuntu machine.
- **The three scripts do not change.** `scripts/env.sh`, `scripts/ide.sh`,
  and `scripts/tidy.sh` run unmodified. They check paths, not provenance, so
  the image must produce the paths they expect. The design document shows
  the layout.
- **Additive only.** You add files under `.devcontainer/`, `.github/`, and
  `docs/`. You do not edit files that the Ubuntu workflow uses.
- **The Jazzy underlay comes from apt.** The Ubuntu machine builds ROS 2 from
  source for code reading. That build runs only on amd64 and takes hours.
  The apt packages are the same release stream and exist for both
  architectures.
- **Every input is pinned.** Use the constants below. Do not pin to a moving
  branch.
- **The built image never goes to a public registry.** The Vimba X SDK is
  inside it, and the SDK license does not allow redistribution.

## Constants

| Item | Value |
|---|---|
| Base image | `ros:jazzy` (Ubuntu 24.04, amd64 and arm64) |
| Vimba X SDK | 2026-2 |
| SDK archive, amd64 | `https://www.alliedvision.com/downloads/software/Vimba_X/VimbaX_Setup-2026-2-Linux64.tar.gz` |
| SDK sha256, amd64 | `45eb34db03e7311ad3cf309c89fc13ddba8b3fd860082a4698198731963faa44` |
| SDK archive, arm64 | `https://www.alliedvision.com/downloads/software/Vimba_X/VimbaX_Setup-2026-2-Linux_ARM64.tar.gz` |
| SDK sha256, arm64 | `bc223962fc393878c71a6efce8215ce231cc3089bb1a85fffc6fb6eeee43c091` |
| Driver ref | `v1.0.1-beta1` (the commit the Ubuntu machine runs) |
| Lint toolchain | LLVM 20 from `apt.llvm.org`, packages `clang-tidy-20`, `clang-apply-replacements-20`, `clang-tools-20` |
| Compiler | GCC 13, the Ubuntu 24.04 default at `/usr/bin/c++` |

The SDK archives are served from public URLs, so the Dockerfile can fetch them
at build time and check the sha256. If the vendor moves the files, download
the same version by hand from the Allied Vision site. Then copy the archive
into the build context instead.

## Decisions that are yours

Record each one in the pull request that makes it, with the reason.

- Which container runtime to use on the Mac. OrbStack and Docker Desktop
  both work. Measure before you choose.
- Where `build/`, `install/`, and `log/` live. Named volumes are faster than
  the bind mount on macOS. Measure a full build both ways.
- How the acceptance checks are organized. One script, several workflow
  steps, or something else.
- Whether to pin the base image to a digest, and how to record the pins so a
  future update is one edit.
- Anything the design document marks as open.

## How we work

- Make a branch for each milestone. Name it as you like.
- Open a pull request when the milestone's pass test succeeds. The mentor
  reviews within the week and merges.
- Put two sections in every pull request description. "Decisions" lists each
  choice you made and why. "Parked" lists questions you could not answer.
- If you are stuck for more than two hours on one problem, write down what
  you tried and message the mentor. Do not wait for the check-in.
- At the check-in, show the pass test running. For the Mac milestone, share
  your screen.

## Read these first

- [macos-project-milestones.md](macos-project-milestones.md)
- [macos-dev-environment-design.md](macos-dev-environment-design.md)
- The three bootstrap READMEs:
  <https://github.com/lkaising/ros2-jazzy-bootstrap>,
  <https://github.com/lkaising/vimbax-sdk-bootstrap>,
  <https://github.com/lkaising/vimbax-ros2-driver-bootstrap>
- VS Code Dev Containers:
  <https://code.visualstudio.com/docs/devcontainers/containers>
- ROS 2 Jazzy installation on Ubuntu:
  <https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html>
