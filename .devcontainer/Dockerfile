FROM ros:jazzy

ARG TARGETARCH


# System and ROS 2 dependencies
RUN apt-get update && apt-get install -y \
    wget \
    git \
    cmake \
    g++ \
    sudo \
    build-essential \
    ros-dev-tools \
    gdb \
    ccache \
    python3-venv \
    ros-jazzy-rclcpp \
    ros-jazzy-rclcpp-components \
    ros-jazzy-image-transport \
    ros-jazzy-demo-nodes-cpp \
    ros-jazzy-demo-nodes-py \
    ros-jazzy-camera-info-manager \
    ros-jazzy-rosidl-default-generators \
    ros-jazzy-cv-bridge \
    ros-jazzy-rmw-cyclonedds-cpp \
    ros-jazzy-launch-pytest \
    ros-jazzy-ament-cmake-gtest \
    clang-tidy-20 \
    clang-tools-20 \
    && rm -rf /var/lib/apt/lists/*

# Make LLVM 20's run-clang-tidy available under the command name expected by the project.
RUN ln -s /usr/bin/run-clang-tidy-20 /usr/local/bin/run-clang-tidy

# Create the development user
RUN usermod -l dev -d /home/dev -m ubuntu \
    && groupmod -n dev ubuntu \
    && echo "dev ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/dev

# Create the workspace layout: upstream dependencies and the project mount point's parent
RUN mkdir -p /home/dev/workspace/upstream/ros2-jazzy \
    && ln -s /opt/ros/jazzy /home/dev/workspace/upstream/ros2-jazzy/install \
    && mkdir -p /home/dev/workspace/upstream/vimbax-sdk \
    && mkdir -p /home/dev/workspace/project \
    && chown -R dev:dev /home/dev/workspace

# Download the architecture-specific Vimba X SDK
RUN set -eux; \
    if [ "$TARGETARCH" = "amd64" ]; then \
        SDK_URL="https://www.alliedvision.com/downloads/software/Vimba_X/VimbaX_Setup-2026-2-Linux64.tar.gz"; \
        SDK_SHA256="45eb34db03e7311ad3cf309c89fc13ddba8b3fd860082a4698198731963faa44"; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        SDK_URL="https://www.alliedvision.com/downloads/software/Vimba_X/VimbaX_Setup-2026-2-Linux_ARM64.tar.gz"; \
        SDK_SHA256="bc223962fc393878c71a6efce8215ce231cc3089bb1a85fffc6fb6eeee43c091"; \
    else \
        echo "Unsupported TARGETARCH: $TARGETARCH"; \
        exit 1; \
    fi; \
    wget -O /tmp/vimbax.tar.gz "$SDK_URL"; \
    echo "$SDK_SHA256  /tmp/vimbax.tar.gz" | sha256sum -c -; \
    tar -xzf /tmp/vimbax.tar.gz \
        --strip-components=1 \
        -C /home/dev/workspace/upstream/vimbax-sdk; \
    rm /tmp/vimbax.tar.gz


# Register the Vimba X SDK
USER root

ARG SDK_BOOTSTRAP_COMMIT=70ce1fe0c77bd66a49ffcc53aad0c8948ea48102

RUN mkdir -p /etc/udev/rules.d \
    && git clone \
        https://github.com/lkaising/vimbax-sdk-bootstrap.git \
        /tmp/vimbax-sdk-bootstrap \
    && git -C /tmp/vimbax-sdk-bootstrap checkout --detach \
        "$SDK_BOOTSTRAP_COMMIT" \
    && test "$(git -C /tmp/vimbax-sdk-bootstrap rev-parse HEAD)" \
        = "$SDK_BOOTSTRAP_COMMIT" \
    && unset GENICAM_GENTL64_PATH \
    && /tmp/vimbax-sdk-bootstrap/bootstrap-vimbax-sdk install \
        --yes \
        --sdk-dir /home/dev/workspace/upstream/vimbax-sdk

ENV GENICAM_GENTL64_PATH=/home/dev/workspace/upstream/vimbax-sdk/cti

# Project mount point. Keep in sync with workspaceFolder and workspaceMount in
# devcontainer.json and the workspace paths in .github/workflows/container.yml.
ENV VENIMAPPING_ROOT=/home/dev/workspace/project/venimapping
ENV COLCON_DEFAULTS_FILE=${VENIMAPPING_ROOT}/.devcontainer/colcon-defaults.yaml

# Verify that the Vimba X SDK and camera simulator are available
RUN /tmp/vimbax-sdk-bootstrap/bootstrap-vimbax-sdk verify \
    --sdk-dir /home/dev/workspace/upstream/vimbax-sdk

USER dev

ARG DRIVER_BOOTSTRAP_COMMIT=c1c1ab2e90681cbe1da1bae221a2140aec41a9e5

RUN git clone \
        https://github.com/lkaising/vimbax-ros2-driver-bootstrap.git \
        /tmp/vimbax-ros2-driver-bootstrap \
    && git -C /tmp/vimbax-ros2-driver-bootstrap checkout --detach \
        "$DRIVER_BOOTSTRAP_COMMIT" \
    && test "$(git -C /tmp/vimbax-ros2-driver-bootstrap rev-parse HEAD)" \
        = "$DRIVER_BOOTSTRAP_COMMIT" \
    && env -u ROS_DISTRO \
       -u ROS_VERSION \
       -u AMENT_PREFIX_PATH \
       -u COLCON_PREFIX_PATH \
       /tmp/vimbax-ros2-driver-bootstrap/bootstrap-vimbax-ros2-driver \
        install \
        --yes \
        --ros-underlay /opt/ros/jazzy \
        --ref v1.0.1-beta1

# Load ROS 2, the Vimba X driver and the project overlay (scripts/env.sh) in
# every interactive Bash shell of the dev user. /etc/bash.bashrc returns early
# in non-interactive shells. The Dev Containers CLI probes the environment with
# an interactive login shell, so devcontainer exec and lifecycle commands
# inherit it.
USER root

RUN printf '%s\n' \
    '' \
    '# venimapping: load the project environment for the dev user' \
    'if [ "$(id -un)" = dev ] && [ -n "${VENIMAPPING_ROOT:-}" ] && [ -f "${VENIMAPPING_ROOT}/scripts/env.sh" ]; then' \
    '    source "${VENIMAPPING_ROOT}/scripts/env.sh"' \
    'fi' \
    >> /etc/bash.bashrc

USER dev

WORKDIR /home/dev
