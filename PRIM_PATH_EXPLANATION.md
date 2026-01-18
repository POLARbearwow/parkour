# Isaac Sim Prim Path 路径说明

## 什么是 Prim Path？

在 Isaac Sim（基于 NVIDIA Omniverse）中，**Prim Path** 是场景图（Scene Graph）中对象的**唯一标识符路径**，类似于文件系统的路径。

## 路径结构

### 基础结构
```
/World                          # 场景根节点
├── /World/envs                 # 所有环境的容器
│   ├── /World/envs/env_0       # 第 0 个环境
│   │   ├── /World/envs/env_0/Robot          # 机器人根节点
│   │   │   ├── /World/envs/env_0/Robot/base_link      # 基座连杆
│   │   │   │   └── /World/envs/env_0/Robot/base_link/d435   # 相机模型
│   │   │   ├── /World/envs/env_0/Robot/LF_HipA_link
│   │   │   ├── /World/envs/env_0/Robot/LF_HipF_link
│   │   │   └── ...
│   │   └── /World/envs/env_0/Terrain
│   ├── /World/envs/env_1       # 第 1 个环境
│   │   └── ...
│   └── /World/envs/env_N       # 第 N 个环境
├── /World/ground               # 全局地形
└── /World/skyLight             # 天空光照
```

## 特殊占位符

### `{ENV_REGEX_NS}` - 环境命名空间占位符

这是一个**正则表达式占位符**，在运行时会被替换为实际的环境路径。

#### 原理：
```python
# 配置时使用占位符
prim_path="{ENV_REGEX_NS}/Robot/base_link/d435"

# 运行时自动展开为多个环境：
# env_0: /World/envs/env_0/Robot/base_link/d435
# env_1: /World/envs/env_1/Robot/base_link/d435
# env_2: /World/envs/env_2/Robot/base_link/d435
# ...
# env_N: /World/envs/env_N/Robot/base_link/d435
```

#### 为什么使用占位符？

**❌ 不使用占位符**（错误）：
```python
# 只能指定一个环境
prim_path="/World/envs/env_0/Robot/base_link/d435"
# 问题：只会在 env_0 创建相机，其他环境没有！
```

**✅ 使用占位符**（正确）：
```python
# 自动适配所有环境
prim_path="{ENV_REGEX_NS}/Robot/base_link/d435"
# 效果：所有环境都会创建相机！
```

## DogV2 项目中的路径示例

### 1. 机器人配置
```python
# custom_robot_cfg.py
class CustomRobotCfg(ArticulationCfg):
    prim_path = "{ENV_REGEX_NS}/Robot"  # ⬅️ 机器人的根路径
```

**实际路径**：
- env_0: `/World/envs/env_0/Robot`
- env_1: `/World/envs/env_1/Robot`
- ...

### 2. 高度扫描仪（Height Scanner）
```python
# parkour_teacher_cfg_custom.py
height_scanner = RayCasterCfg(
    prim_path=f"{ENV_REGEX_NS}/Robot/{BASE_LINK_NAME}",
)
```

**实际路径**（BASE_LINK_NAME="base_link"）：
- env_0: `/World/envs/env_0/Robot/base_link`

**含义**：高度扫描仪挂载在机器人的 `base_link` 上

### 3. 接触力传感器（Contact Sensor）
```python
# parkour_teacher_cfg_custom.py
contact_forces = ContactSensorCfg(
    prim_path="{ENV_REGEX_NS}/Robot/.*",  # ⬅️ 注意正则表达式
)
```

**实际路径**（使用正则表达式）：
- 匹配：`/World/envs/env_0/Robot/` 下的**所有连杆**
- 包括：`base_link`, `LF_HipA_link`, `LF_Foot_link`, ...

### 4. 深度相机（Depth Camera）
```python
# default_cfg_custom.py

# 功能相机（实际采集深度数据）
CAMERA_CFG = RayCasterCameraCfg(
    prim_path="{ENV_REGEX_NS}/Robot/base_link",  # 挂载点
)

# 视觉模型（只是 3D 模型，用于显示）
CAMERA_USD_CFG = AssetBaseCfg(
    prim_path="{ENV_REGEX_NS}/Robot/base_link/d435",  # USD 模型路径
)
```

**层级关系**：
```
/World/envs/env_0/Robot/base_link        # 基座连杆（父节点）
└── /World/envs/env_0/Robot/base_link/d435   # 相机模型（子节点）
```

### 5. 地形（Terrain）
```python
# default_cfg_custom.py
terrain = TerrainImporterCfg(
    prim_path="/World/ground",  # ⬅️ 没有 {ENV_REGEX_NS}！
)
```

**为什么不用占位符？**
- 地形是**全局共享**的，所有环境使用同一个地形
- 只需要一个实例，不需要为每个环境创建

## 路径规则总结

| 路径格式 | 用途 | 示例 |
|---------|------|------|
| `{ENV_REGEX_NS}/...` | 每个环境独立的对象 | 机器人、传感器 |
| `/World/...` | 全局共享的对象 | 地形、光照 |
| `{ENV_REGEX_NS}/.../.*` | 正则匹配多个子对象 | 所有连杆、所有关节 |

## 常见错误

### ❌ 错误 1：忘记使用占位符
```python
# 错误：硬编码环境编号
prim_path="/World/envs/env_0/Robot"

# 正确：使用占位符
prim_path="{ENV_REGEX_NS}/Robot"
```

### ❌ 错误 2：路径不匹配 USD 结构
```python
# 错误：USD 中的连杆名称是 "base_link"，但配置中写成 "base"
prim_path="{ENV_REGEX_NS}/Robot/base"  # ❌

# 正确：必须与 USD/URDF 中的名称一致
prim_path="{ENV_REGEX_NS}/Robot/base_link"  # ✅
```

### ❌ 错误 3：混淆相对路径和绝对路径
```python
# 错误：相对路径（缺少 / 开头）
prim_path="Robot/base_link"  # ❌

# 正确：绝对路径（占位符或 /World 开头）
prim_path="{ENV_REGEX_NS}/Robot/base_link"  # ✅
prim_path="/World/ground"  # ✅
```

## 调试技巧

### 1. 查看实际路径
在 Isaac Sim 中打开 **Stage** 窗口（Window > Stage），可以看到完整的场景图：
```
/World
└── envs
    └── env_0
        └── Robot
            ├── base_link
            │   └── d435
            ├── LF_HipA_link
            └── ...
```

### 2. 检查路径是否存在
```python
# 在代码中打印实际路径
print(f"Robot path: {self.scene.robot.cfg.prim_path}")
print(f"Available bodies: {self.scene.robot.body_names}")
```

### 3. 使用正则表达式测试
```python
import re

# 测试正则表达式是否匹配
pattern = ".*_Foot_link"
bodies = ["LF_Foot_link", "LR_Foot_link", "RF_Foot_link", "RR_Foot_link"]
matches = [b for b in bodies if re.match(pattern, b)]
print(f"Matched bodies: {matches}")
```

## 参考资料

- [Isaac Sim USD 文档](https://docs.omniverse.nvidia.com/app_isaacsim/app_isaacsim/overview.html)
- [Isaac Lab Scene 文档](https://isaac-sim.github.io/IsaacLab/main/source/api/lab/isaaclab.scene.html)
