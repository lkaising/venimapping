// -----------------------------------------------------------------------------
//  Filename: vimbax_response_conversion.hpp
//
//  Purpose:  Declares conversions from Vimba X service responses to gateway types.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include <vector>

#include "venimapping_camera/types/camera_status.hpp"
#include "venimapping_camera/types/feature_info.hpp"
#include "vimbax_camera_msgs/srv/feature_info_query.hpp"
#include "vimbax_camera_msgs/srv/status.hpp"

namespace venimapping::camera::gateway_support {

[[nodiscard]] CameraStatus to_camera_status(vimbax_camera_msgs::srv::Status::Response& response);

[[nodiscard]] std::vector<FeatureInfo> to_feature_info_list(
    vimbax_camera_msgs::srv::FeatureInfoQuery::Response& response);

}  // namespace venimapping::camera::gateway_support
