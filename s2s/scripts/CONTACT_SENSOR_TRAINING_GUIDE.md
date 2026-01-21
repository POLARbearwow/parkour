# 实机没有足端力传感器时的训练策略

## 问题分析

如果实机没有足端力传感器，训练时需要决定：
1. **Teacher和Student都去掉contact sensor？**
2. **还是只去掉Student的？**

## 答案：**两者都应该去掉或模拟**

### 原因

1. **训练-部署一致性**：
   - 如果实机没有contact sensor，训练时也不应该使用真实的contact信息
   - 否则会出现**domain gap**（训练和部署条件不一致）

2. **Student需要匹配实机条件**：
   - Student策略最终要部署到实机
   - 训练条件应该尽可能接近实机条件

3. **Teacher可以保留，但建议去掉**：
   - Teacher不需要部署到实机，理论上可以保留contact sensor
   - 但为了保持一致性，建议也去掉

## 解决方案

### 方案1：完全去掉Contact Sensor（推荐）

#### 1.1 修改Scene配置

**Teacher配置** (`parkour_teacher_cfg_custom.py`):
```python
@configclass
class ParkourTeacherSceneCfg(ParkourDefaultSceneCfg):
    robot = CustomRobotCfg(prim_path="{ENV_REGEX_NS}/Robot")
    
    height_scanner = RayCasterCfg(...)
    
    # 注释掉或删除contact_forces
    # contact_forces = ContactSensorCfg(
    #     prim_path="{ENV_REGEX_NS}/Robot/.*",
    #     history_length=2,
    #     track_air_time=True,
    #     debug_vis=False,
    #     force_threshold=1.0,
    # )
    contact_forces = None  # 或者直接设为None
```

**Student配置** (`parkour_student_cfg_custom.py`):
```python
@configclass
class ParkourStudentSceneCfg(ParkourTeacherSceneCfg):
    # Student继承Teacher，所以也会去掉contact_forces
    depth_camera = CAMERA_CFG
    ...
```

#### 1.2 修改Observation配置

**Teacher和Student的Observation配置** (`parkour_mdp_cfg_custom.py`):
```python
@configclass
class TeacherObservationsCfg:
    @configclass
    class PolicyCfg(ObsGroup):
        extreme_parkour_observations = ObsTerm(
            func=observations.ExtremeParkourObservations,
            params={
                "asset_cfg": SceneEntityCfg("robot"),
                # 注释掉sensor_cfg或设为None
                # "sensor_cfg": SceneEntityCfg(
                #     "contact_forces", body_names=".*_Foot_link"
                # ),
                "sensor_cfg": None,  # 或者不提供这个参数
                "parkour_name": "base_parkour",
                "history_length": 10,
            },
            clip=(-100, 100),
        )
```

#### 1.3 修改Observation函数

**文件**: `parkour_isaaclab/envs/mdp/observations.py`

修改`_get_contact_fill`函数，当没有contact sensor时返回零：

```python
def _get_contact_fill(self):
    # 如果没有contact sensor，返回零数组
    if self.contact_sensor is None:
        return torch.zeros(self.num_envs, 4, device=self.device) - 0.5
    
    # 原有的contact sensor逻辑
    contact_forces = self.contact_sensor.data.net_forces_w_history[:, 0, self.sensor_cfg.body_ids]
    contact = torch.norm(contact_forces, dim=-1) > 2.0
    previous_contact_forces = self.contact_sensor.data.net_forces_w_history[:, -1, self.sensor_cfg.body_ids]
    last_contacts = torch.norm(previous_contact_forces, dim=-1) > 2.0
    contact_filt = torch.logical_or(contact, last_contacts)
    return (contact_filt.float() - 0.5).to(self.device)
```

### 方案2：模拟Contact信息（备选）

如果不想完全去掉，可以模拟contact信息：

#### 2.1 从关节位置和速度估计

```python
def _get_contact_fill_simulated(self):
    """从关节位置和速度估计contact状态"""
    # 简化的contact检测：如果脚部关节位置接近地面，认为接触
    foot_positions = self.asset.data.body_pos_w[:, self.foot_body_ids, 2]  # z坐标
    ground_height = 0.0  # 假设地面高度为0
    
    # 如果脚部接近地面（阈值0.05m），认为接触
    contact_threshold = 0.05
    contact = (foot_positions - ground_height) < contact_threshold
    
    return (contact.float() - 0.5).to(self.device)
```

#### 2.2 从关节扭矩估计

```python
def _get_contact_fill_from_torque(self):
    """从关节扭矩估计contact状态"""
    # 如果关节扭矩大于阈值，认为有接触
    joint_torques = self.asset.data.joint_torques
    torque_threshold = 5.0  # N·m
    
    # 简化：如果膝关节扭矩较大，可能表示脚部接触
    knee_torques = joint_torques[:, [2, 5, 8, 11]]  # 4个膝关节
    contact = knee_torques.abs() > torque_threshold
    
    return (contact.float() - 0.5).to(self.device)
```

## 推荐方案

### ✅ **方案1：完全去掉Contact Sensor（推荐）**

**优点**：
- 训练和部署条件完全一致
- 避免domain gap
- 实现简单

**缺点**：
- 失去contact信息，可能影响性能
- 需要重新训练

**实施步骤**：
1. 在Scene配置中删除或注释掉`contact_forces`
2. 在Observation配置中删除`sensor_cfg`
3. 修改`_get_contact_fill`函数，返回零数组
4. 重新训练Teacher和Student

### ⚠️ **方案2：模拟Contact信息（备选）**

**优点**：
- 保留部分contact信息
- 可能性能更好

**缺点**：
- 模拟的contact信息可能不准确
- 仍然存在domain gap
- 实现更复杂

## 具体修改步骤

### 步骤1：修改Scene配置

**文件**: `parkour_tasks/parkour_tasks/extreme_parkour_task/config/dogv2/parkour_teacher_cfg_custom.py`

```python
@configclass
class ParkourTeacherSceneCfg(ParkourDefaultSceneCfg):
    robot = CustomRobotCfg(prim_path="{ENV_REGEX_NS}/Robot")

    height_scanner = RayCasterCfg(...)
    
    # 删除或注释掉contact_forces
    # contact_forces = ContactSensorCfg(...)
    
    def __post_init__(self):
        super().__post_init__()
        # 删除contact_forces的更新
        # self.scene.contact_forces.update_period = ...
```

### 步骤2：修改Observation配置

**文件**: `parkour_tasks/parkour_tasks/extreme_parkour_task/config/dogv2/parkour_mdp_cfg_custom.py`

```python
@configclass
class TeacherObservationsCfg:
    @configclass
    class PolicyCfg(ObsGroup):
        extreme_parkour_observations = ObsTerm(
            func=observations.ExtremeParkourObservations,
            params={
                "asset_cfg": SceneEntityCfg("robot"),
                # 删除sensor_cfg参数
                # "sensor_cfg": SceneEntityCfg(
                #     "contact_forces", body_names=".*_Foot_link"
                # ),
                "parkour_name": "base_parkour",
                "history_length": 10,
            },
            clip=(-100, 100),
        )
```

### 步骤3：修改Observation函数

**文件**: `parkour_isaaclab/envs/mdp/observations.py`

```python
def __init__(self, cfg: ObservationTermCfg, env: ParkourManagerBasedRLEnv):
    super().__init__(cfg, env)
    # 检查是否有contact sensor
    if "contact_forces" in env.scene.sensors:
        self.contact_sensor: ContactSensor = env.scene.sensors["contact_forces"]
        self.sensor_cfg = cfg.params.get("sensor_cfg")
    else:
        self.contact_sensor = None
        self.sensor_cfg = None
    # ... 其他初始化

def _get_contact_fill(self):
    """获取contact信息，如果没有sensor则返回零"""
    if self.contact_sensor is None or self.sensor_cfg is None:
        # 返回零数组（4个脚，值在[-0.5, 0.5]范围）
        return torch.zeros(self.num_envs, 4, device=self.device) - 0.5
    
    # 原有的contact sensor逻辑
    contact_forces = self.contact_sensor.data.net_forces_w_history[:, 0, self.sensor_cfg.body_ids]
    contact = torch.norm(contact_forces, dim=-1) > 2.0
    previous_contact_forces = self.contact_sensor.data.net_forces_w_history[:, -1, self.sensor_cfg.body_ids]
    last_contacts = torch.norm(previous_contact_forces, dim=-1) > 2.0
    contact_filt = torch.logical_or(contact, last_contacts)
    return (contact_filt.float() - 0.5).to(self.device)
```

### 步骤4：修改Reward配置（如果需要）

**文件**: `parkour_tasks/parkour_tasks/extreme_parkour_task/config/dogv2/parkour_mdp_cfg_custom.py`

如果reward中使用了contact_forces，也需要修改：

```python
@configclass
class TeacherRewardsCfg:
    reward_collision = RewTerm(
        func=rewards.reward_collision,
        weight=-10.0,
        params={
            # 如果没有contact sensor，可能需要修改或删除
            "sensor_cfg": SceneEntityCfg(
                "contact_forces",
                body_names=[".*base_link", ".*HipF_link", ".*Knee_link"],
            ),
        },
    )
```

## 总结

### 推荐做法

1. **Teacher和Student都去掉contact sensor**
2. **修改observation函数，返回零数组**
3. **重新训练Teacher和Student**

### 原因

- **训练-部署一致性**：避免domain gap
- **实机条件匹配**：训练条件应该匹配实机条件
- **简单可靠**：实现简单，避免复杂的模拟逻辑

### 注意事项

1. **需要重新训练**：去掉contact sensor后需要重新训练
2. **性能可能下降**：失去contact信息可能影响性能
3. **可以逐步迁移**：先训练没有contact sensor的Teacher，再用它训练Student
