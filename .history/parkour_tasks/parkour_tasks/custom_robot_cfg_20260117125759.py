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

# 获取项目根目录
# 假设此文件位于: parkour_tasks/parkour_tasks/custom_robot_cfg.py
# 项目根目录应该是: /Users/niuniu/Desktop/pakour
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

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
        # 检查USD文件是否存在
        if not os.path.exists(USD_FILE_PATH):
            raise FileNotFoundError(
                f"USD文件未找到: {USD_FILE_PATH}\n"
                f"请确保USD文件位于项目根目录下"
            )
        
        # 设置USD文件配置，包含物理属性
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
                enabled_self_collisions=False,  # 四足机器人初期建议 False，避免腿部碰撞导致摔倒
                solver_position_iteration_count=4,
                solver_velocity_iteration_count=1,
            ),
        )
        
        # 设置初始状态
        # 根据您的机器人调整初始高度（Z轴）
        # 根据URDF和您的配置，设置为0.42
        self.init_state = AssetBaseCfg.InitialStateCfg(
            pos=(0.0, 0.0, 0.42),  # 根据机器人尺寸调整起始高度
            rot=(1.0, 0.0, 0.0, 0.0),  # 单位四元数 (w, x, y, z)
            joint_pos={
                # 初始站立姿态配置 - 按照URDF顺序
                ".*_HipA_joint": 0.0,
                ".*_HipF_joint": 0.0,
                ".*_Knee_joint": 0.0,
            },
            joint_vel={".*": 0.0},
        )
        
        # 设置软关节位置限制因子
        self.soft_joint_pos_limit_factor = 0.90
        
        # 配置执行器 - 按照URDF顺序
        # 使用ImplicitActuatorCfg，按照URDF中的关节顺序配置
        # 注意：joint_names_expr的顺序会影响执行器的索引顺序
        self.actuators = {
            "legs": ImplicitActuatorCfg(
                # 按照URDF顺序列出关节匹配模式
                # 这样可以确保执行器索引与URDF中的关节顺序一致
                joint_names_expr=[
                    ".*_HipA_joint",  # 匹配所有HipA关节（LF, LR, RF, RR）
                    ".*_HipF_joint",  # 匹配所有HipF关节
                    ".*_Knee_joint",  # 匹配所有Knee关节
                ],
                stiffness={
                    ".*_HipA_joint": 25.0,
                    ".*_HipF_joint": 25.0,
                    ".*_Knee_joint": 25.0,
                },
                damping={
                    ".*_HipA_joint": 0.5,
                    ".*_HipF_joint": 0.5,
                    ".*_Knee_joint": 0.5,
                },
                armature={
                    ".*_HipA_joint": 0.01,
                    ".*_HipF_joint": 0.01,
                    ".*_Knee_joint": 0.01,
                },
            ),
        }
