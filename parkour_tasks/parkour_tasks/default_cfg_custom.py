from isaaclab.scene import InteractiveSceneCfg
from isaaclab.assets import ArticulationCfg, AssetBaseCfg
import isaaclab.sim as sim_utils
from isaaclab.utils.assets import ISAAC_NUCLEUS_DIR, ISAACLAB_NUCLEUS_DIR
from isaaclab.terrains import TerrainImporterCfg
from isaaclab.utils import configclass
from parkour_isaaclab.terrains.parkour_terrain_importer import ParkourTerrainImporter
from parkour_tasks.extreme_parkour_task.config.dogv2 import agents  # DogV2 agents
from isaaclab.sensors import RayCasterCameraCfg
from isaaclab.sensors.ray_caster.patterns import PinholeCameraPatternCfg
from isaaclab.envs import ViewerCfg
import os, torch
from parkour_isaaclab.actuators.parkour_actuator_cfg import ParkourDCMotorCfg
from parkour_tasks.custom_robot_cfg import CustomRobotCfg  # 导入自定义机器人配置


BASE_LINK_NAME = "base_link"


def quat_from_euler_xyz_tuple(
    roll: torch.Tensor, pitch: torch.Tensor, yaw: torch.Tensor
) -> tuple:
    cy = torch.cos(yaw * 0.5)
    sy = torch.sin(yaw * 0.5)
    cr = torch.cos(roll * 0.5)
    sr = torch.sin(roll * 0.5)
    cp = torch.cos(pitch * 0.5)
    sp = torch.sin(pitch * 0.5)
    # compute quaternion
    qw = cy * cr * cp + sy * sr * sp
    qx = cy * sr * cp - sy * cr * sp
    qy = cy * cr * sp + sy * sr * cp
    qz = sy * cr * cp - cy * sr * sp
    convert = torch.stack([qw, qx, qy, qz], dim=-1) * torch.tensor([1.0, 1.0, 1.0, -1])
    return tuple(convert.numpy().tolist())


@configclass
class ParkourDefaultSceneCfg(InteractiveSceneCfg):
    """DogV2 机器人的默认场景配置

    注意：这个配置类是为 DogV2 自定义机器人设计的。
    默认使用 CustomRobotCfg，但子类可以覆盖 robot 配置。
    """

    # 使用 DogV2 自定义机器人配置
    robot: ArticulationCfg = CustomRobotCfg(prim_path="{ENV_REGEX_NS}/Robot")

    sky_light = AssetBaseCfg(
        prim_path="/World/skyLight",
        spawn=sim_utils.DomeLightCfg(
            intensity=750.0,
            texture_file=f"{ISAAC_NUCLEUS_DIR}/Materials/Textures/Skies/PolyHaven/kloofendal_43d_clear_puresky_4k.hdr",
        ),
    )

    terrain = TerrainImporterCfg(
        class_type=ParkourTerrainImporter,
        prim_path="/World/ground",
        terrain_type="generator",
        terrain_generator=None,
        max_init_terrain_level=2,
        collision_group=-1,
        physics_material=sim_utils.RigidBodyMaterialCfg(
            friction_combine_mode="average",
            restitution_combine_mode="average",
            static_friction=1.0,
            dynamic_friction=1.0,
        ),
        visual_material=sim_utils.MdlFileCfg(
            mdl_path=f"{ISAACLAB_NUCLEUS_DIR}/Materials/TilesMarbleSpiderWhiteBrickBondHoned/TilesMarbleSpiderWhiteBrickBondHoned.mdl",
            project_uvw=True,
            texture_scale=(0.25, 0.25),
        ),
        debug_vis=False,
    )

    def __post_init__(self):
        """后初始化配置

        注意：CustomRobotCfg 已经配置了执行器，所以这里不需要额外配置。
        如果子类需要覆盖 robot 配置为其他类型，请在子类的 __post_init__ 中处理。
        """
        pass


## DogV2 深度相机配置
## 使用 raycaster 相机，而不是 pinhole 相机
## 参考: https://github.com/isaac-sim/IsaacLab/issues/719
CAMERA_CFG = RayCasterCameraCfg(
    prim_path="{ENV_REGEX_NS}/Robot/base_link",  # 挂载到 DogV2 的 base_link
    data_types=["distance_to_camera"],
    offset=RayCasterCameraCfg.OffsetCfg(
        pos=(0.31505, 0.00, 0.023),
        rot=quat_from_euler_xyz_tuple(*tuple(torch.tensor([0, 1.57, -1.57]))),
        convention="ros",
    ),
    depth_clipping_behavior="max",
    pattern_cfg=PinholeCameraPatternCfg(
        focal_length=11.041,
        horizontal_aperture=20.955,
        vertical_aperture=12.240,
        height=60,
        width=106,
    ),
    mesh_prim_paths=["/World/ground"],
    max_distance=2.0,
)

## DogV2 相机 USD 模型配置（用于可视化）
CAMERA_USD_CFG = AssetBaseCfg(
    prim_path="{ENV_REGEX_NS}/Robot/base_link/d435",
    spawn=sim_utils.UsdFileCfg(
        usd_path=os.path.join(
            agents.__path__[0], "d435.usd"
        )  
    ),
    init_state=AssetBaseCfg.InitialStateCfg(
        pos=(0.31505, 0.00, 0.023),
        rot=quat_from_euler_xyz_tuple(*tuple(torch.tensor([0, 1.57, -1.57]))),
    ),
)
## DogV2 视角配置
VIEWER = ViewerCfg(
    eye=(-0.0, 2.6, 1.6),  # 相机位置
    origin_type="world",  # 自由移动视角（不跟随机器人）
    # asset_name="robot",
    # origin_type="asset_root",
)
