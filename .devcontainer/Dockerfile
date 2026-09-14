# starts the VeniMapping image from the official ROS 2 Jazzy image
FROM ros:jazzy

# these commands are executed while the image is built
RUN apt-get update && apt-get install -y \
    #adds packages to retrieve source code, configure C++ builds, and compiler C++ code
    git \
    cmake \
    g++ \
    #adds ROS specific packages
    ros-jazzy-rclcpp \
    ros-jazzy-image-transport \
    ros-jazzy-demo-nodes-cpp \
    ros-jazzy-demo-nodes-py \
    ros-jazzy-camera-info-manager \
    ros-jazzy-rosidl-default-generators \
    ros-jazzy-cv-bridge \
    ros-jazzy-rmw-cyclonedds-cpp \
    # identifies and modifies potential bugs and issues
    clang-tidy-20 \
    clang-tools-20 \
    && rm -rf /var/lib/apt/lists/*

# creates a symlink between /usr/local/bin/run-clang-tidy and /usr/bin/run-clang-tidy-20
RUN ln -s /usr/bin/run-clang-tidy-20 /usr/local/bin/run-clang-tidy

# changes the default user to dev and moves it to the /home/dev home directory and gives it access to sudo
RUN usermod -l dev -d /home/dev -m ubuntu \
    && groupmod -n dev ubuntu \
    && echo "dev ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/dev

# creates a symlink btw /home/dev/workspace/upstream/ros2-jazzy/install and /opt/ros/jazzy in the dev workspace
RUN mkdir -p /home/dev/workspace/upstream/ros2-jazzy \
    && ln -s /opt/ros/jazzy /home/dev/workspace/upstream/ros2-jazzy/install \
    && chown -R dev:dev /home/dev/workspace

# switches the docker to the dev user
USER dev
WORKDIR /home/dev