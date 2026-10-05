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
    ros-jazzy-image-transport \
    ros-jazzy-demo-nodes-cpp \
    ros-jazzy-demo-nodes-py \
    ros-jazzy-camera-info-manager \
    ros-jazzy-rosidl-default-generators \
    ros-jazzy-cv-bridge \
    ros-jazzy-rmw-cyclonedds-cpp \
    ros-jazzy-launch-pytest \
    clang-tidy-20 \
    clang-tools-20 \
    && rm -rf /var/lib/apt/lists/*

# Make LLVM 20's run-clang-tidy available under the command name expected by the project.
RUN ln -s /usr/bin/run-clang-tidy-20 /usr/local/bin/run-clang-tidy

# Create the development user
RUN usermod -l dev -d /home/dev -m ubuntu \
    && groupmod -n dev ubuntu \
    && echo "dev ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/dev

# Create the upstream workspace layout
RUN mkdir -p /home/dev/workspace/upstream/ros2-jazzy \
    && ln -s /opt/ros/jazzy /home/dev/workspace/upstream/ros2-jazzy/install \
    && mkdir -p /home/dev/workspace/upstream/vimbax-sdk \
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

RUN mkdir -p /etc/udev/rules.d \
    && git clone \
        https://github.com/lkaising/vimbax-sdk-bootstrap.git \
        /tmp/vimbax-sdk-bootstrap \
    && unset GENICAM_GENTL64_PATH \
    && /tmp/vimbax-sdk-bootstrap/bootstrap-vimbax-sdk install \
        --yes \
        --sdk-dir /home/dev/workspace/upstream/vimbax-sdk

ENV GENICAM_GENTL64_PATH=/home/dev/workspace/upstream/vimbax-sdk/cti
ENV COLCON_DEFAULTS_FILE=/home/dev/venimapping/.devcontainer/colcon-defaults.yaml

# Verify that the Vimba X SDK and camera simulator are available
RUN /tmp/vimbax-sdk-bootstrap/bootstrap-vimbax-sdk verify \
    --sdk-dir /home/dev/workspace/upstream/vimbax-sdk

USER dev

RUN git clone \
        https://github.com/lkaising/vimbax-ros2-driver-bootstrap.git \
        /tmp/vimbax-ros2-driver-bootstrap \
    && env -u ROS_DISTRO \
       -u ROS_VERSION \
       -u AMENT_PREFIX_PATH \
       -u COLCON_PREFIX_PATH \
       /tmp/vimbax-ros2-driver-bootstrap/bootstrap-vimbax-ros2-driver \
        install \
        --yes \
        --ros-underlay /opt/ros/jazzy \
        --ref v1.0.1-beta1

WORKDIR /home/dev
