"""
自定义Teacher配置文件 - 用于dogV2.2.4机器人
原始文件: ../go2/parkour_teacher_cfg.py (保留作为参考)

主要修改：
1. 使用default_cfg_custom中的配置
2. 更新传感器prim_path为dogV2的base link名称
3. 使用CustomRobotCfg替换默认的UNITREE_GO2_CFG
"""

from isaaclab.sensors import ContactSensorCfg, RayCasterCfg, patterns
from isaaclab.utils import configclass

##
# Pre-defined configs
##
from parkour_isaaclab.terrains.extreme_parkour.config.parkour import (
    EXTREME_PARKOUR_TERRAINS_CFG,
)  # isort: skip
from parkour_isaaclab.envs import ParkourManagerBasedRLEnvCfg
from .parkour_mdp_cfg_custom import *
from parkour_tasks.default_cfg_custom import (
    ParkourDefaultSceneCfg,
    VIEWER,
    BASE_LINK_NAME,
)
from parkour_tasks.custom_robot_cfg import CustomRobotCfg  # 导入自定义机器人配置


@configclass
class ParkourTeacherSceneCfg(ParkourDefaultSceneCfg):
    robot = CustomRobotCfg(prim_path="{ENV_REGEX_NS}/Robot")

    height_scanner = RayCasterCfg(
        prim_path=f"{{ENV_REGEX_NS}}/Robot/{BASE_LINK_NAME}",
        offset=RayCasterCfg.OffsetCfg(pos=(0.375, 0.0, 20.0)),
        attach_yaw_only=True,
        pattern_cfg=patterns.GridPatternCfg(resolution=0.15, size=[1.65, 1.5]),
        debug_vis=False,
        mesh_prim_paths=["/World/ground"],
    )
    contact_forces = ContactSensorCfg(
        prim_path="{ENV_REGEX_NS}/Robot/.*",
        history_length=2,
        track_air_time=True,
        debug_vis=False,
        force_threshold=1.0,
    )

    def __post_init__(self):
        super().__post_init__()
        self.terrain.terrain_generator = EXTREME_PARKOUR_TERRAINS_CFG


@configclass
class DogV2TeacherParkourEnvCfg(ParkourManagerBasedRLEnvCfg):
    scene: ParkourTeacherSceneCfg = ParkourTeacherSceneCfg(
        num_envs=6144, env_spacing=1.0
    )
    # Basic settings
    observations: TeacherObservationsCfg = TeacherObservationsCfg()
    actions: ActionsCfg = ActionsCfg()
    commands: CommandsCfg = CommandsCfg()
    # MDP settings
    rewards: TeacherRewardsCfg = TeacherRewardsCfg()
    terminations: TerminationsCfg = TerminationsCfg()
    parkours: ParkourEventsCfg = ParkourEventsCfg()
    events: EventCfg = EventCfg()

    def __post_init__(self):
        """Post initialization."""
        # general settings
        self.decimation = 4
        self.episode_length_s = 20.0
        # simulation settings
        self.sim.dt = 0.005
        self.sim.render_interval = self.decimation
        self.sim.physics_material = self.scene.terrain.physics_material
        self.sim.physx.gpu_max_rigid_patch_count = 10 * 2**18
        # update sensor update periods
        self.scene.height_scanner.update_period = self.sim.dt * self.decimation
        self.scene.contact_forces.update_period = self.sim.dt * self.decimation
        self.scene.terrain.terrain_generator.curriculum = True
        self.actions.joint_pos.use_delay = False
        self.actions.joint_pos.history_length = 1
        self.events.random_camera_position = None


@configclass
class DogV2TeacherParkourEnvCfg_EVAL(DogV2TeacherParkourEnvCfg):
    viewer = VIEWER

    def __post_init__(self):
        # post init of parent
        super().__post_init__()
        self.scene.num_envs = 256
        self.episode_length_s = 20.0
        self.parkours.base_parkour.debug_vis = True
        self.commands.base_velocity.debug_vis = True
        self.scene.terrain.max_init_terrain_level = None
        if self.scene.terrain.terrain_generator is not None:
            self.scene.terrain.terrain_generator.num_rows = 5
            self.scene.terrain.terrain_generator.num_cols = 8
            self.scene.terrain.terrain_generator.random_difficulty = True
            self.scene.terrain.terrain_generator.difficulty_range = (0.0, 1.0)
        self.events.randomize_rigid_body_com = None
        self.events.randomize_rigid_body_mass = None
        self.events.push_by_setting_velocity.interval_range_s = (6.0, 6.0)
        self.commands.base_velocity.resampling_time_range = (60.0, 60.0)
        for (
            key,
            sub_terrain,
        ) in self.scene.terrain.terrain_generator.sub_terrains.items():
            if key == ["parkour", "parkour_hurdle", "parkour_step", "parkour_gap"]:
                sub_terrain.noise_range = (0.02, 0.02)
                sub_terrain.proportion = 0.25


@configclass
class DogV2TeacherParkourEnvCfg_PLAY(DogV2TeacherParkourEnvCfg_EVAL):
    viewer = VIEWER

    def __post_init__(self):
        # post init of parent
        super().__post_init__()
        self.episode_length_s = 60.0
        self.scene.num_envs = 16
        self.parkours.base_parkour.debug_vis = True
        self.commands.base_velocity.debug_vis = True
        # 修改速度命令（Play模式专用）
        # 线速度范围：默认 (0.3, 0.8)，可以修改为更慢或更快
        # self.commands.base_velocity.ranges.lin_vel_x = (2.0, 2.0)  # 更快：0.5-1.0 m/s
        # self.commands.base_velocity.ranges.lin_vel_x = (0.2, 0.5)  # 更慢：0.2-0.5 m/s
        # 朝向范围：默认 (-1.6, 1.6) 弧度，可以限制转向幅度
        # self.commands.base_velocity.ranges.heading = (-1.0, 1.0)  # 减少转向范围
        # 重新采样时间：默认 (6.0, 6.0)，可以改为固定值或范围
        # self.commands.base_velocity.resampling_time_range = (60.0, 60.0)  # 60秒不变换命令
        if self.scene.terrain.terrain_generator is not None:
            self.scene.terrain.terrain_generator.difficulty_range = (0.7, 1.0)
        self.events.push_by_setting_velocity = None
        for (
            key,
            sub_terrain,
        ) in self.scene.terrain.terrain_generator.sub_terrains.items():
            if key == "parkour_flat":
                sub_terrain.proportion = 0.0
            else:
                sub_terrain.proportion = 0.2
                sub_terrain.noise_range = (0.02, 0.02)
