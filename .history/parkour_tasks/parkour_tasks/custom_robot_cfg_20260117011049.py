"""
自定义机器人配置文件
用于替换 Unitree Go2 为您的机器人模型
"""
from isaaclab.assets import ArticulationCfg
from isaaclab.utils import configclass
import isaaclab.sim as sim_utils
import os

# 获取项目根目录
# 假设此文件位于: parkour_tasks/parkour_tasks/custom_robot_cfg.py
# 项目根目录应该是: /Users/niuniu/Desktop/pakour
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

@configclass
class CustomRobotCfg(ArticulationCfg):
    """自定义机器人配置 - 使用您的USD文件
    
    注意：请根据您的实际USD文件调整以下参数：
    1. usd_path - USD文件路径
    2. init_state.pos - 初始位置（特别是Z轴高度）
    3. 关节和身体的命名约定
    """
    
    def __post_init__(self):
        super().__post_init__()
        # 设置USD文件路径
        # 请确保USD文件路径正确
        usd_file_path = os.path.join(PROJECT_ROOT, "dogV2.2.4.sep.usd")
        
        # 检查文件是否存在
        if not os.path.exists(usd_file_path):
            raise FileNotFoundError(
                f"USD文件未找到: {usd_file_path}\n"
                f"请确保USD文件位于项目根目录下"
            )
        
        # 设置USD文件配置
        self.spawn = sim_utils.UsdFileCfg(
            usd_path=usd_file_path
        )
        
        # 设置初始状态
        # 根据您的机器人调整初始高度（Z轴）
        # 建议先设置为0.5，然后根据实际情况调整
        self.init_state.pos = (0.0, 0.0, 0.5)
        self.init_state.rot = (1.0, 0.0, 0.0, 0.0)  # 单位四元数 (w, x, y, z)
        
        # 启用自碰撞（如果需要）
        self.spawn.articulation_props.enabled_self_collisions = True
