# 机器人模型替换指南

本文档说明如何将项目中的 Unitree Go2 机器人替换为您自己的机器人模型（dogV2.2.4）。

## 概述

项目当前使用 `UNITREE_GO2_CFG` 作为机器人配置。要替换为您的机器人模型，需要：

1. 创建自定义的机器人配置（使用您的USD文件）
2. 更新关节和身体名称的匹配规则
3. 调整执行器配置
4. 更新传感器配置（如果需要）
5. 验证所有引用机器人的地方

---

## 步骤 1: 创建自定义机器人配置

### 1.1 创建机器人配置文件

在 `parkour_tasks/parkour_tasks/` 目录下创建新文件 `custom_robot_cfg.py`：

```python
from isaaclab.assets import ArticulationCfg
from isaaclab.utils import configclass
import isaaclab.sim as sim_utils
import os

# 获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

@configclass
class CustomRobotCfg(ArticulationCfg):
    """自定义机器人配置 - 使用您的USD文件"""
    
    def __post_init__(self):
        super().__post_init__()
        # 设置USD文件路径
        self.spawn = sim_utils.UsdFileCfg(
            usd_path=os.path.join(PROJECT_ROOT, "dogV2.2.4.sep.usd")
        )
        # 设置初始状态
        self.init_state.pos = (0.0, 0.0, 0.5)  # 根据您的机器人调整初始高度
        self.init_state.rot = (1.0, 0.0, 0.0, 0.0)  # 单位四元数
```

### 1.2 更新默认配置

修改 `parkour_tasks/parkour_tasks/default_cfg.py`：

**替换：**
```python
from isaaclab_assets.robots.unitree import UNITREE_GO2_CFG  # isort: skip
```

**为：**
```python
from parkour_tasks.custom_robot_cfg import CustomRobotCfg  # isort: skip
```

**替换：**
```python
robot: ArticulationCfg = UNITREE_GO2_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")
```

**为：**
```python
robot: ArticulationCfg = CustomRobotCfg(prim_path="{ENV_REGEX_NS}/Robot")
```

---

## 步骤 2: 更新关节名称匹配规则

### 2.1 分析您的机器人关节名称

根据您的URDF文件 (`dogV2.2.4.sep.urdf`)，关节命名规则为：
- `LF_HipA_joint`, `LF_HipF_joint`, `LF_Knee_joint` (左前腿)
- `RF_HipA_joint`, `RF_HipF_joint`, `RF_Knee_joint` (右前腿)
- `LR_HipA_joint`, `LR_HipF_joint`, `LR_Knee_joint` (左后腿)
- `RR_HipA_joint`, `RR_HipF_joint`, `RR_Knee_joint` (右后腿)

而当前代码使用的命名规则是：
- `.*_hip_joint` - 髋关节
- `.*_thigh_joint` - 大腿关节
- `.*_calf_joint` - 小腿关节

### 2.2 更新执行器配置

修改 `parkour_tasks/parkour_tasks/default_cfg.py` 中的 `__post_init__` 方法：

**当前配置：**
```python
self.robot.actuators['base_legs'] = ParkourDCMotorCfg(
    joint_names_expr=[".*_hip_joint", ".*_thigh_joint", ".*_calf_joint"],
    ...
)
```

**需要根据您的关节名称调整：**

**选项A：如果您的USD文件中关节名称与URDF不同，需要先检查USD文件中的实际关节名称**

**选项B：如果关节名称匹配，可以这样配置：**
```python
self.robot.actuators['base_legs'] = ParkourDCMotorCfg(
    joint_names_expr=[".*HipA_joint", ".*HipF_joint", ".*Knee_joint"],
    effort_limit={
        '.*HipA_joint': 17.0,  # 根据URDF中的effort值调整
        '.*HipF_joint': 17.0,
        '.*Knee_joint': 25.0,
    },
    saturation_effort={
        '.*HipA_joint': 17.0,
        '.*HipF_joint': 17.0,
        '.*Knee_joint': 25.0,
    },
    velocity_limit={
        '.*HipA_joint': 50.0,  # 根据URDF中的velocity值调整
        '.*HipF_joint': 50.0,
        '.*Knee_joint': 50.0,
    },
    stiffness=40.0,
    damping=1.0,
    friction=0.0,
)
```

---

## 步骤 3: 更新身体（Body）名称匹配规则

### 3.1 分析身体名称

根据您的URDF，身体（link）名称可能为：
- `DOGV2_2_4_SLDASM_base_link` - 基座
- `DOGV2_2_4_SLDASM_LF_Foot_link` - 左前脚
- `DOGV2_2_4_SLDASM_RF_Foot_link` - 右前脚
- `DOGV2_2_4_SLDASM_LR_Foot_link` - 左后脚
- `DOGV2_2_4_SLDASM_RR_Foot_link` - 右后脚

而代码中使用的匹配规则：
- `base` - 基座
- `FL_foot`, `FR_foot`, `RL_foot`, `RR_foot` - 四只脚
- `.*_calf`, `.*_thigh` - 小腿和大腿

### 3.2 更新奖励配置

修改 `parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/parkour_mdp_cfg.py`：

**在 `TeacherRewardsCfg` 中：**

**当前配置：**
```python
reward_feet_edge = RewTerm(
    ...
    params={
        "asset_cfg":SceneEntityCfg(name="robot", body_names=["FL_foot","FR_foot","RL_foot","RR_foot"]),
        ...
    },
)
```

**需要根据您的身体名称调整：**
```python
reward_feet_edge = RewTerm(
    ...
    params={
        "asset_cfg":SceneEntityCfg(name="robot", body_names=[".*LF_Foot.*", ".*RF_Foot.*", ".*LR_Foot.*", ".*RR_Foot.*"]),
        # 或者使用正则表达式匹配所有脚部
        # "asset_cfg":SceneEntityCfg(name="robot", body_names=[".*_Foot_link"]),
        ...
    },
)
```

**在 `reward_collision` 中：**

**当前配置：**
```python
reward_collision = RewTerm(
    ...
    params={
        "sensor_cfg":SceneEntityCfg("contact_forces", body_names=["base",".*_calf",".*_thigh"]),
    },
)
```

**需要调整：**
```python
reward_collision = RewTerm(
    ...
    params={
        "sensor_cfg":SceneEntityCfg("contact_forces", body_names=[".*base.*",".*HipF.*",".*Knee.*"]),
        # 根据您的实际身体名称调整
    },
)
```

### 3.3 更新观察配置

修改 `parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/parkour_mdp_cfg.py`：

**在观察配置中，检查 `sensor_cfg` 的 `body_names`：**

```python
extreme_parkour_observations = ObsTerm(
    ...
    params={            
        "sensor_cfg":SceneEntityCfg("contact_forces", body_names=".*_foot"),
        # 可能需要改为：body_names=".*_Foot.*" 或 body_names=".*Foot_link"
        ...
    },
)
```

---

## 步骤 4: 更新传感器配置

### 4.1 相机配置

相机配置依赖于机器人的 `base` 身体。检查您的USD文件中基座身体的名称。

**在 `parkour_tasks/parkour_tasks/default_cfg.py` 中：**

```python
CAMERA_CFG = RayCasterCameraCfg( 
    prim_path= '{ENV_REGEX_NS}/Robot/base',  # 确保这个路径在您的USD中正确
    ...
)
```

**如果您的基座名称不同，需要调整 `prim_path`，例如：**
```python
prim_path= '{ENV_REGEX_NS}/Robot/DOGV2_2_4_SLDASM_base_link',
```

### 4.2 接触力传感器配置

**在 `parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/parkour_teacher_cfg.py` 中：**

```python
contact_forces = ContactSensorCfg(
    prim_path="{ENV_REGEX_NS}/Robot/.*",  # 这个应该可以匹配所有身体
    ...
)
```

---

## 步骤 5: 更新动作配置

### 5.1 关节动作配置

**在 `parkour_tasks/parkour_tasks/extreme_parkour_task/config/go2/parkour_mdp_cfg.py` 中：**

```python
joint_pos = DelayedJointPositionActionCfg(
    asset_name="robot", 
    joint_names=[".*"],  # 匹配所有关节，应该可以工作
    ...
)
```

如果您的关节数量与Go2不同，可能需要调整 `clip` 参数中的关节数量。

---

## 步骤 6: 验证和测试

### 6.1 检查USD文件结构

在Isaac Sim中打开您的USD文件，确认：
1. 关节名称是否与URDF一致
2. 身体（link）名称
3. 基座（base）的prim路径
4. 关节的DOF（自由度）数量

### 6.2 运行测试

1. **测试场景加载：**
   ```bash
   # 运行测试脚本检查场景是否正确加载
   python parkour_test/test_terrain_generator.py
   ```

2. **检查关节和身体名称：**
   在代码中添加调试输出，打印所有关节和身体名称：
   ```python
   asset = env.scene["robot"]
   print("Joint names:", asset.joint_names)
   print("Body names:", asset.body_names)
   ```

### 6.3 常见问题排查

1. **关节名称不匹配：**
   - 检查USD文件中的实际关节名称
   - 使用正则表达式匹配时，确保模式正确

2. **身体名称不匹配：**
   - 检查USD文件中的实际身体名称
   - 更新所有使用身体名称的地方

3. **执行器配置错误：**
   - 确保关节名称表达式能匹配到正确的关节
   - 检查effort_limit和velocity_limit是否合理

4. **传感器配置错误：**
   - 确保prim_path指向正确的身体
   - 检查相机和接触力传感器的配置

---

## 步骤 7: 更新其他配置文件

### 7.1 测试文件

更新以下测试文件中的机器人配置：
- `parkour_test/test_camera.py`
- `parkour_test/test_terrain_generator.py`

将 `UNITREE_GO2_CFG` 替换为 `CustomRobotCfg`。

---

## 重要提示

1. **USD文件要求：**
   - USD文件必须包含完整的物理属性
   - 关节必须正确定义
   - 身体（link）必须有碰撞体

2. **命名约定：**
   - 如果可能，建议在USD文件中使用与代码期望一致的命名
   - 或者使用正则表达式灵活匹配

3. **关节数量：**
   - 确保您的机器人关节数量与动作空间匹配
   - Go2有12个关节（每条腿3个），如果您的机器人不同，需要调整

4. **身体数量：**
   - 确保脚部身体数量为4个（四足机器人）
   - 确保有基座（base）身体

---

## 总结

替换机器人的主要步骤：
1. ✅ 创建自定义机器人配置（使用您的USD文件）
2. ✅ 更新关节名称匹配规则（执行器配置）
3. ✅ 更新身体名称匹配规则（奖励和观察配置）
4. ✅ 更新传感器配置（相机和接触力传感器）
5. ✅ 验证和测试

完成这些步骤后，您的机器人模型应该可以在项目中使用。
