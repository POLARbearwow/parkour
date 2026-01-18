# Copyright (c) 2025-2026, The Legged Lab Project Developers.
# All rights reserved.
# Modifications are licensed under BSD-3-Clause.

"""
自定义机器人配置文件
用于替换 Unitree Go2 为您的机器人模型 (dogV2.2.4)
按照URDF中的关节顺序加载
"""
from isaaclab.assets import ArticulationCfg, AssetBaseCfg
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.utils import configclass
import isaaclab.sim as sim_utils
import os
from parkour_isaaclab.actuators.parkour_actuator_cfg import ParkourDCMotorCfg


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# USD文件路径
USD_FILE_PATH = os.path.join(PROJECT_ROOT, "dogV2.2.4.sep.usd")


@configclass
class CustomRobotCfg(ArticulationCfg):
    """自定义机器人配置 - 使用您的USD文件

    按照URDF中的关节顺序加载，确保关节索引与URDF一致。

    URDF关节顺序（可驱动关节）:
    1. LF_HipA_joint, 2. LF_HipF_joint, 3. LF_Knee_joint,
    4. LR_HipA_joint, 5. LR_HipF_joint, 6. LR_Knee_joint,
    7. RF_HipA_joint, 8. RF_HipF_joint, 9. RF_Knee_joint,
    10. RR_HipA_joint, 11. RR_HipF_joint, 12. RR_Knee_joint

    注意：请根据您的实际USD文件调整以下参数：
    1. usd_path - USD文件路径
    2. init_state.pos - 初始位置（特别是Z轴高度）
    3. 关节和身体的命名约定
    """

    def __post_init__(self):
        super().__post_init__()
        if not os.path.exists(USD_FILE_PATH):
            raise FileNotFoundError(
                f"USD文件未找到: {USD_FILE_PATH}\n" f"请确保USD文件位于项目根目录下"
            )
        self.spawn = sim_utils.UsdFileCfg(
            usd_path=USD_FILE_PATH,
            activate_contact_sensors=True,
            rigid_props=sim_utils.RigidBodyPropertiesCfg(
                disable_gravity=False,
                retain_accelerations=False,
                linear_damping=0.0,
                angular_damping=0.0,
                max_linear_velocity=1000.0,
                max_angular_velocity=1000.0,
                max_depenetration_velocity=1.0,
            ),
            articulation_props=sim_utils.ArticulationRootPropertiesCfg(
                enabled_self_collisions=False,
                solver_position_iteration_count=4,
                solver_velocity_iteration_count=1,
            ),
        )

        self.init_state = ArticulationCfg.InitialStateCfg(
            pos=(0.0, 0.0, 0.42),  # 机器人初始高度
            rot=(1.0, 0.0, 0.0, 0.0),  # 四元数 (w, x, y, z)
            lin_vel=(0.0, 0.0, 0.0),  # 线速度
            ang_vel=(0.0, 0.0, 0.0),  # 角速度
        )

        # 设置软关节位置限制因子
        self.soft_joint_pos_limit_factor = 0.90

        self.actuators = {
            "hips": ParkourDCMotorCfg(
                joint_names_expr=[".*_HipA_joint", ".*_HipF_joint"],
                effort_limit=17.0,
                saturation_effort=17.0,
                velocity_limit=22.0,
                stiffness=25.0,
                damping=0.5,
                friction=0.0,
            ),
            "knees": ParkourDCMotorCfg(
                joint_names_expr=[".*_Knee_joint"],
                effort_limit=25.0,
                saturation_effort=25.0,
                velocity_limit=13.0,
                stiffness=25.0,
                damping=0.5,
                friction=0.0,
            ),
        }
