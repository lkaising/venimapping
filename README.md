# VeniMapping

A ROS 2 project using the Allied Vision Vimba X SDK and ROS 2 camera driver.

<!-- TODO: Add project overview and usage documentation. -->

## Development setup

1. **Native Ubuntu 24.04** — the main development environment. Set it up with
   [ros2-jazzy-bootstrap](https://github.com/lkaising/ros2-jazzy-bootstrap),
   [vimbax-sdk-bootstrap](https://github.com/lkaising/vimbax-sdk-bootstrap), and
   [vimbax-ros2-driver-bootstrap](https://github.com/lkaising/vimbax-ros2-driver-bootstrap).
2. **VS Code dev container (Apple Silicon Macs)** — follow the
   [macOS quickstart](docs/macos-quickstart.md).

## Useful commands

Run from the repository root in your development environment:

```bash
source scripts/env.sh         # Load the environment
colcon build --symlink-install # Build the workspace
./scripts/ide.sh              # Generate VS Code configuration
./scripts/tidy.sh check       # Run clang-tidy
./scripts/workspace.sh check  # Run the full build, tests and clang-tidy checks
```

Connect to the running dev container from an outside terminal. Run from the
checkout root on your host; the environment loads automatically:

```bash
docker exec -it -u dev \
  -w /home/dev/workspace/project/venimapping \
  "$(docker ps -q --filter "label=devcontainer.local_folder=$(pwd)")" \
  bash
```
