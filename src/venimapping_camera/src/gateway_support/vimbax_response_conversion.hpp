// -----------------------------------------------------------------------------
//  Filename: vimbax_response_conversion.hpp
//
//  Purpose:  Declares conversions from Vimba X service responses to gateway types.
//
//  Copyright (C) 2026 Logan Kaising.  All rights reserved.
// -----------------------------------------------------------------------------

#pragma once

#include "venimapping_camera/types/camera_status.hpp"
#include "venimapping_camera/types/feature_access_mode.hpp"
#include "venimapping_camera/types/feature_enum_info.hpp"
#include "venimapping_camera/types/feature_float_info.hpp"
#include "venimapping_camera/types/feature_info_list.hpp"
#include "venimapping_camera/types/feature_int_info.hpp"
#include "venimapping_camera/types/feature_list.hpp"
#include "venimapping_camera/types/feature_raw_value.hpp"
#include "vimbax_camera_msgs/srv/feature_access_mode_get.hpp"
#include "vimbax_camera_msgs/srv/feature_enum_info_get.hpp"
#include "vimbax_camera_msgs/srv/feature_float_info_get.hpp"
#include "vimbax_camera_msgs/srv/feature_info_query.hpp"
#include "vimbax_camera_msgs/srv/feature_int_info_get.hpp"
#include "vimbax_camera_msgs/srv/feature_raw_get.hpp"
#include "vimbax_camera_msgs/srv/features_list_get.hpp"
#include "vimbax_camera_msgs/srv/status.hpp"

namespace venimapping::camera::gateway_support {

namespace vimbax_srv = vimbax_camera_msgs::srv;

[[nodiscard]] CameraStatus to_camera_status(
    vimbax_srv::Status::Response& response);

[[nodiscard]] FeatureList to_feature_list(
    vimbax_srv::FeaturesListGet::Response& response);

[[nodiscard]] FeatureInfoList to_feature_info_list(
    vimbax_srv::FeatureInfoQuery::Response& response);

[[nodiscard]] FeatureAccessMode to_feature_access_mode(
    const vimbax_srv::FeatureAccessModeGet::Response& response);

[[nodiscard]] FeatureIntInfo to_feature_int_info(
    const vimbax_srv::FeatureIntInfoGet::Response& response);

[[nodiscard]] FeatureFloatInfo to_feature_float_info(
    const vimbax_srv::FeatureFloatInfoGet::Response& response);

[[nodiscard]] FeatureEnumInfo to_feature_enum_info(
    vimbax_srv::FeatureEnumInfoGet::Response& response);

[[nodiscard]] FeatureRawValue to_feature_raw_value(
    vimbax_srv::FeatureRawGet::Response& response);

}  // namespace venimapping::camera::gateway_support
