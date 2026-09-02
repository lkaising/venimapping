# Building VeniMapping on macOS: milestones

Each milestone adds one layer and ends with a pass test you can run alone.
Open one pull request per milestone. Do not start the next milestone until
the current one passes, because each layer depends on the one below it.

Hours are estimates for a first attempt. The driver and Mac milestones get
two weeks each.

| # | Milestone | Hours | Needs a Mac |
|---|---|---|---|
| 1 | Orientation | 4 | no |
| 2 | Base image and CI | 6 | no |
| 3 | SDK layer | 4 | no |
| 4 | Driver layer | 8 | no |
| 5 | VeniMapping builds | 4 | no |
| 6 | Dev container on the Mac | 8 | yes |
| 7 | Quickstart | 4 | yes |
| 8 | Stretch | open | no |

Milestones 2 to 5 run on any Docker host. Your Mac is fine, and so is a
Linux machine. CI is the judge for those four. Milestone 6 is the first one
that needs VS Code on the Mac.

## 1. Orientation

Goal. Understand the pieces before you build anything.

1. Install a container runtime on your Mac. OrbStack or Docker Desktop.
2. Run `docker run --rm -it ros:jazzy` and start `demo_nodes_cpp talker`
   in one shell and `listener` in another. Confirm they talk.
3. Read the three bootstrap READMEs and this repository's `scripts/env.sh`.
4. Read the design document.

Pass test. Bring written answers to the check-in.

- Which five files or directories does `scripts/env.sh` require before it
  sources anything? Give the exact paths.
- The image will not build ROS 2 from source. What single symlink makes
  `env.sh` accept the apt install at `/opt/ros/jazzy` instead?
- Why does the design run the bootstrap tools inside the image instead of
  copying their commands into the Dockerfile?

No pull request for this milestone.

## 2. Base image and CI

Goal. A Dockerfile that builds on both architectures, with a workflow that
proves it.

1. Create `.devcontainer/Dockerfile` from `ros:jazzy`.
2. Install `build-essential`, `ros-dev-tools`, `sudo`, `gdb`, `ccache`,
   `python3-venv`, and the `ros-jazzy-*` packages the design lists.
3. Add the `apt.llvm.org` repository for noble and install `clang-tidy-20`,
   `clang-apply-replacements-20`, and `clang-tools-20`.
4. Create a non-root user `dev` with passwordless sudo.
5. Create the underlay symlink the design shows.
6. Create a workflow under `.github/workflows/` that builds the image on
   `ubuntu-24.04` and `ubuntu-24.04-arm` and runs the pass test inside it.

Pass test. All of these succeed in CI on both runners, as user `dev`.

```
test -x /usr/bin/clang-tidy-20 && test -x /usr/bin/clang-apply-replacements-20
command -v run-clang-tidy
test -f ~/workspace/upstream/ros2-jazzy/install/setup.bash
bash -lc 'source /opt/ros/jazzy/setup.bash && ros2 pkg prefix cv_bridge'
```

Hints.

- Ubuntu 24.04 images ship a user named `ubuntu` at UID 1000. Check
  `getent passwd 1000` before you create `dev`, and decide what to do with
  the existing user. The dev container will later remap `dev` to your Mac
  UID, and that works best when `dev` starts at 1000.
- `ros:jazzy` already has `rosdep` initialized and colcon mixins installed.
  Do not repeat that work.
- Use `ARG TARGETARCH` for anything that differs between amd64 and arm64.
  You will need it in milestone 3.

## 3. SDK layer

Goal. The Vimba X SDK is unpacked at the path the scripts expect, and the
SDK bootstrap has registered it.

1. Fetch the archive for `TARGETARCH` from the URL in the brief. Verify the
   sha256 before you unpack. Fail the build if it does not match.
2. Unpack to `/home/dev/workspace/upstream/vimbax-sdk`. The archive has one
   top-level directory named `VimbaX_2026-2`, so strip it.
3. Clone `vimbax-sdk-bootstrap` and run its install command as `dev` with
   `--yes`.
4. Set `GENICAM_GENTL64_PATH` with a Dockerfile `ENV` line as well.

Pass test. In CI, as user `dev`, in a login shell:

```
bootstrap-vimbax-sdk verify
```

It must report at least one transport layer and one camera. The camera is
the simulator.

Hints.

- The SDK bootstrap writes `GENICAM_GENTL64_PATH` to `/etc/profile.d/`.
  Only login shells read that directory. `scripts/env.sh` fails hard when
  the variable is missing, and VS Code tasks do not run login shells. That
  is why step 4 exists.
- The bootstrap tries `udevadm control --reload-rules`. There is no udev in
  a container. The bootstrap treats the failure as a warning. Confirm that
  in its output rather than assume it.
- The bootstrap refuses to replace an existing registration without a
  terminal, and `--yes` does not override that. Docker builds have no
  terminal. Run it once, in a fresh layer.

## 4. Driver layer

Goal. The Vimba X ROS 2 driver is built in its own overlay by the driver
bootstrap, against the apt underlay, and its smoke test passes.

1. Clone `vimbax-ros2-driver-bootstrap`.
2. Run its install command as `dev` with `--yes`, `--ros-underlay
   /opt/ros/jazzy`, and `--ref v1.0.1-beta1`.

Pass test. In CI, on both runners, as user `dev`:

```
bootstrap-vimbax-ros2-driver verify
```

Its smoke test must run `vimbax_camera_node` against the simulator. The
output says the node stayed alive for 8 seconds. A skipped smoke test is a
failure. It means milestone 3 is not complete.

Hints.

- `ros:jazzy` sets `ROS_DISTRO=jazzy` in the image environment. The driver
  bootstrap refuses to run when `ROS_DISTRO`, `ROS_VERSION`,
  `AMENT_PREFIX_PATH`, or `COLCON_PREFIX_PATH` is set. Unset them for that
  one command. Do not remove them from the image.
- The bootstrap clones with `git clone --branch`, so `--ref` takes a tag or
  branch and never a commit hash. `v1.0.1-beta1` is the upstream tag for the
  commit the Ubuntu machine runs.
- Do not create `/home/dev/workspace/upstream/vimbax-ros2-driver` yourself.
  If the directory exists, the bootstrap asks for interactive confirmation
  to adopt it, and the build hangs or fails.
- The bootstrap runs `rosdep update` for `dev` and calls `sudo` for
  `rosdep install`. Both need network and the sudo setup from milestone 2.
- This layer is the slow one. Expect 5 to 15 minutes per build. Order the
  Dockerfile so this layer sits below anything you still edit often.

## 5. VeniMapping builds

Goal. This repository builds inside the container with its own scripts,
unchanged.

1. In the workflow, check out the repository and bind-mount it into the
   container at `/home/dev/venimapping`.
2. Run the pass test inside the container as `dev`.

Pass test.

```
source scripts/env.sh
colcon build --symlink-install
./scripts/ide.sh
./scripts/tidy.sh check
```

The first line must print
`[venimapping] jazzy=active driver=active gentl=active rmw=rmw_cyclonedds_cpp`
followed by the venv and overlay fields. The other three must exit 0.
`colcon test` must also exit 0, but the packages define no tests today, so
do not read much into that.

Hints.

- `env.sh` chooses CycloneDDS when `rmw_cyclonedds_cpp` is installed. If the
  summary says `rmw=default`, the apt list from milestone 2 is missing a
  package.
- `tidy.sh fix` refuses a dirty git tree, and git refuses a checkout owned
  by a different UID. Both matter when the repository is a bind mount. Look
  at `git config --global --add safe.directory` and at the UID of `dev`.
- `ide.sh` needs `build/` and `install/` to exist. Run it after the build.

## 6. Dev container on the Mac

Goal. "Reopen in Container" works in VS Code on your Mac, and the editor
tooling behaves as it does on the Ubuntu machine.

1. Write `.devcontainer/devcontainer.json` from the design document.
2. Install the Dev Containers extension and reopen this repository in the
   container.
3. Build, run `./scripts/ide.sh`, and reload the window.
4. Open `src/venimapping_camera/src/vimbax_camera_gateway.cpp`. Hover a
   `rclcpp` symbol and a `vimbax_camera_msgs` symbol.
5. Save a C++ file with a formatting error and confirm format-on-save fixes
   it. Confirm clang-tidy diagnostics appear.
6. Time a full clean build with `build/`, `install/`, and `log/` on the bind
   mount, then with named volumes. Record both.

Pass test. Show all of these at the check-in over screen share.

- `source scripts/env.sh` in a VS Code terminal prints the green summary.
- IntelliSense resolves both header families with no red squiggles.
- Format-on-save and clang-tidy run with the settings `ide.sh` generated.
- The pull request contains a table with both build times and the runtime
  you chose, with reasons.

Hints.

- `updateRemoteUserUID` remaps `dev` to your Mac UID at container start.
  Files you create in the bind mount then belong to you on the Mac side.
- `postCreateCommand` runs once after the container is created. A build
  there means the first open takes minutes. Decide whether you want that or
  a manual first build, and say why.
- Named volumes hide `build/`, `install/`, and `log/` from the Mac
  filesystem. That is fine because `.gitignore` excludes them anyway.

## 7. Quickstart

Goal. A document that takes a new user from a clean Mac to a green build.

1. Write `docs/macos-quickstart.md`. Cover runtime install, extension
   install, reopen in container, first build, and how to run the pass tests.
2. Delete the image, the named volumes, and the VS Code server cache on
   your Mac.
3. Follow your own document, and nothing else, to a green build.
4. Fix everything you had to look up elsewhere.

Pass test. The mentor follows the document on a different Mac and reaches
the green summary without asking you a question. Every question they ask is
a defect in the document.

## 8. Stretch

Pick any of these if time remains. Each one is a separate pull request.

- Pin `ros:jazzy` to a digest and put every pin in one place, so that a
  future update is one edit.
- Cache the driver layer in CI so a Dockerfile change above it does not
  rebuild the driver.
- Write a short note on when to move the driver ref. Allied Vision has not
  shipped a release that compiles under GCC 13 as of September 2026.
- Evaluate a private registry so a new machine pulls the image instead of
  building it. The SDK license rules out a public one.
