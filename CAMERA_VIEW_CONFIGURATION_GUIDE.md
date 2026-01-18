# Isaac Sim 相机视角配置详解

Isaac Sim 中有**两种不同的"相机"**概念，很容易混淆。让我详细解释：

---

## 🎥 两种相机类型

### **1. 观察视角（Viewer/Viewport Camera）** - 你在屏幕上看到的
### **2. 传感器相机（Sensor Camera）** - 机器人用来"看"的

---

## 👁️ 类型 1: 观察视角（Viewer Camera）

**作用**：控制**你在 Isaac Sim 窗口中看到的视角**，相当于"观众的眼睛"

### **配置方式 A：在环境配置中（用于 RL 训练）**

```python
# default_cfg_custom.py

from isaaclab.envs import ViewerCfg

VIEWER = ViewerCfg(
    eye=(-0.0, 2.6, 1.6),       # 相机位置 (x, y, z)
    origin_type="world",         # 参考坐标系
    # lookat=(0.0, 0.0, 0.0),   # 可选：看向的目标点
)
```

#### **参数详解**：

| 参数 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `eye` | tuple[float, float, float] | 相机位置 (x, y, z) | `(-0.0, 2.6, 1.6)` |
| `lookat` | tuple[float, float, float] | 相机看向的目标点 (x, y, z) | `(0.0, 0.0, 0.0)` |
| `origin_type` | str | 参考坐标系类型 | `"world"`, `"asset_root"`, `"env"` |
| `asset_name` | str | 当 `origin_type="asset_root"` 时，跟随的资产名称 | `"robot"` |
| `env_index` | int | 当 `origin_type="env"` 时，观察的环境索引 | `0` |

#### **`origin_type` 选项详解**：

##### **A. `origin_type="world"` - 世界坐标系（固定视角）**
```python
VIEWER = ViewerCfg(
    eye=(0.0, 5.0, 2.0),    # 相对于世界原点的位置
    origin_type="world",
)
```
- ✅ 相机位置固定在世界坐标系中
- ✅ 不会跟随机器人移动
- ✅ 适合：观察全局场景、调试多个机器人

**坐标系**：
```
        Z (up)
        ↑
        |
        |_____ Y
       /
      /
     X
原点 = /World 根节点
```

##### **B. `origin_type="asset_root"` - 跟随资产根节点**
```python
VIEWER = ViewerCfg(
    eye=(0.0, 2.0, 1.0),        # 相对于机器人的位置
    asset_name="robot",          # 跟随 "robot"
    origin_type="asset_root",
)
```
- ✅ 相机跟随机器人移动
- ✅ 始终保持相对位置
- ✅ 适合：观察单个机器人的动作细节

**效果**：
```
机器人移动 → 相机也移动
机器人转向 → 相机也转向（保持相对位置）
```

##### **C. `origin_type="env"` - 跟随特定环境中心**
```python
VIEWER = ViewerCfg(
    eye=(0.0, 3.0, 2.0),
    env_index=0,                 # 观察第 0 个环境
    origin_type="env",
)
```
- ✅ 相机固定在某个环境的中心
- ✅ 适合：多环境训练时观察特定环境

---

### **配置方式 B：在测试脚本中（用于测试）**

```python
# test_camera_custom.py

import isaaclab.sim as sim_utils

# 创建仿真上下文
sim_cfg = sim_utils.SimulationCfg(dt=0.005, device="cuda:0")
sim = sim_utils.SimulationContext(sim_cfg)

# 设置初始相机视角
sim.set_camera_view(
    eye=[3.5, 3.5, 3.5],      # 相机位置 [x, y, z]
    target=[0.0, 0.0, 0.0]    # 看向的目标点 [x, y, z]
)
```

#### **参数详解**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `eye` | list[float, float, float] | 相机位置（世界坐标系）|
| `target` | list[float, float, float] | 相机看向的目标点 |

#### **示例位置**：

```python
# 俯视视角（从上往下看）
sim.set_camera_view(eye=[0.0, 0.0, 5.0], target=[0.0, 0.0, 0.0])

# 侧视视角（从侧面看）
sim.set_camera_view(eye=[5.0, 0.0, 1.0], target=[0.0, 0.0, 0.0])

# 斜视视角（45度角）
sim.set_camera_view(eye=[3.5, 3.5, 3.5], target=[0.0, 0.0, 0.0])

# 跟随机器人（从后方看）
sim.set_camera_view(eye=[0.0, 2.0, 1.0], target=[0.0, 0.0, 0.5])
```

---

## 🤖 类型 2: 传感器相机（Sensor Camera）

**作用**：机器人用来采集**深度图像、RGB 图像**等数据的传感器

### **功能相机配置（实际采集数据）**

```python
# default_cfg_custom.py

from isaaclab.sensors import RayCasterCameraCfg
from isaaclab.sensors.ray_caster.patterns import PinholeCameraPatternCfg

CAMERA_CFG = RayCasterCameraCfg(
    prim_path="{ENV_REGEX_NS}/Robot/base_link",  # 挂载位置
    data_types=["distance_to_camera"],            # 采集深度数据
    
    # 相机相对于 base_link 的位置和姿态
    offset=RayCasterCameraCfg.OffsetCfg(
        pos=(0.31505, 0.0175, 0.023),  # 相对位置 (x, y, z) 米
        rot=quat_from_euler_xyz_tuple(
            torch.tensor([0, 0, 0])     # 旋转角度 (roll, pitch, yaw) 弧度
        ),
        convention="ros",               # 坐标系约定（ROS 或 world）
    ),
    
    # 相机内参（针孔相机模型）
    pattern_cfg=PinholeCameraPatternCfg(
        focal_length=11.041,            # 焦距 (mm)
        horizontal_aperture=20.955,     # 水平光圈 (mm)
        vertical_aperture=12.240,       # 垂直光圈 (mm)
        height=60,                      # 图像高度 (像素)
        width=106,                      # 图像宽度 (像素)
    ),
    
    # 深度范围
    max_distance=2.0,                   # 最大检测距离 (米)
    depth_clipping_behavior="max",      # 超出范围的处理方式
    
    # 检测目标
    mesh_prim_paths=["/World/ground"],  # 检测地面
)
```

#### **关键参数详解**：

##### **1. `prim_path` - 挂载位置**
```python
prim_path="{ENV_REGEX_NS}/Robot/base_link"
```
- 相机挂载在机器人的 `base_link` 上
- 相机会跟随机器人移动和旋转

##### **2. `offset` - 相对位置和姿态**

```python
offset=RayCasterCameraCfg.OffsetCfg(
    pos=(0.31505, 0.0175, 0.023),  # 相对 base_link 的位置
    rot=quat_from_euler_xyz_tuple(
        torch.tensor([0, 0, 0])     # 旋转：roll, pitch, yaw (弧度)
    ),
    convention="ros",               # 坐标系约定
)
```

**位置 `pos=(x, y, z)` 解释**：
```
你的配置: pos=(0.31505, 0.0175, 0.023)

x = 0.31505 米  # 相机在 base_link **前方** 31.5 cm
y = 0.0175 米   # 相机在 base_link **左侧** 1.75 cm
z = 0.023 米    # 相机在 base_link **上方** 2.3 cm
```

**姿态 `rot` 解释**（使用欧拉角）：
```python
# 示例 1: 相机朝前（默认）
rot=quat_from_euler_xyz_tuple(torch.tensor([0, 0, 0]))

# 示例 2: 相机向下倾斜 30 度
rot=quat_from_euler_xyz_tuple(torch.tensor([0, np.deg2rad(30), 0]))

# 示例 3: 相机向左旋转 90 度
rot=quat_from_euler_xyz_tuple(torch.tensor([0, 0, np.deg2rad(90)]))
```

**`convention` 选项**：
- `"ros"`: 使用 ROS 坐标系约定（x前, y左, z上）
- `"world"`: 使用世界坐标系约定（x右, y后, z上）

##### **3. `pattern_cfg` - 相机内参**

```python
pattern_cfg=PinholeCameraPatternCfg(
    focal_length=11.041,            # 焦距 (mm)
    horizontal_aperture=20.955,     # 水平光圈 (mm)
    vertical_aperture=12.240,       # 垂直光圈 (mm)
    height=60,                      # 图像高度 (像素)
    width=106,                      # 图像宽度 (像素)
)
```

**参数说明**：
- `focal_length`：焦距，控制视野大小（焦距越大，视野越窄）
- `horizontal_aperture`：水平光圈，控制水平视野范围
- `vertical_aperture`：垂直光圈，控制垂直视野范围
- `height`, `width`：输出图像的分辨率

**计算视野角度（FOV）**：
```python
import numpy as np

# 水平 FOV
h_fov = 2 * np.arctan(horizontal_aperture / (2 * focal_length))
h_fov_deg = np.rad2deg(h_fov)

# 对于你的配置：
# h_fov = 2 * arctan(20.955 / (2 * 11.041)) ≈ 87.3°
```

---

### **视觉模型配置（仅用于显示）**

```python
# default_cfg_custom.py

CAMERA_USD_CFG = AssetBaseCfg(
    prim_path="{ENV_REGEX_NS}/Robot/base_link/d435",  # USD 模型路径
    spawn=sim_utils.UsdFileCfg(
        usd_path=os.path.join(agents.__path__[0], "d435.usd")
    ),
    init_state=AssetBaseCfg.InitialStateCfg(
        pos=(0.61505, 0.0195, 0.023),  # 你修改为 0.61505（61.5 cm）
        rot=quat_from_euler_xyz_tuple(torch.tensor([0, 0, 0])),
    ),
)
```

**注意**：
- ⚠️ `CAMERA_USD_CFG` 只是 **3D 模型**，用于在仿真中显示相机外观
- ⚠️ **不采集实际数据**！实际数据由 `CAMERA_CFG` 采集
- ⚠️ `pos` 应该与 `CAMERA_CFG` 的 `offset.pos` **保持一致**

**你的修改**：
```python
# 你改成了 0.61505 (前方 61.5 cm)
pos=(0.61505, 0.0195, 0.023)

# 但 CAMERA_CFG 中还是 0.31505 (前方 31.5 cm)
offset=RayCasterCameraCfg.OffsetCfg(
    pos=(0.31505, 0.0175, 0.023),  # ⬅️ 不一致！
)
```

**建议修复**：保持一致
```python
# 方案 1: 都改为 0.61505
CAMERA_CFG = RayCasterCameraCfg(
    offset=RayCasterCameraCfg.OffsetCfg(
        pos=(0.61505, 0.0175, 0.023),  # 改为 0.61505
    ),
)

CAMERA_USD_CFG = AssetBaseCfg(
    init_state=AssetBaseCfg.InitialStateCfg(
        pos=(0.61505, 0.0195, 0.023),  # 保持 0.61505
    ),
)

# 方案 2: 都改回 0.31505
```

---

## 📊 配置对比总结

| 特性 | **Viewer Camera** | **Sensor Camera** |
|------|------------------|-------------------|
| **用途** | 观察视角（你看到的） | 传感器数据（机器人看到的） |
| **配置位置** | `ViewerCfg` 或 `sim.set_camera_view()` | `RayCasterCameraCfg` |
| **跟随机器人** | 可选（`origin_type="asset_root"`） | 自动跟随（挂载在 `base_link`） |
| **采集数据** | ❌ 不采集 | ✅ 采集深度/RGB 图像 |
| **影响训练** | ❌ 仅可视化 | ✅ 作为观测输入 |
| **坐标系** | 世界坐标系 | 相对于挂载点 |

---

## 🎯 常用配置示例

### **示例 1: 固定俯视角度观察训练**
```python
VIEWER = ViewerCfg(
    eye=(0.0, 0.0, 10.0),   # 从正上方 10 米高看下去
    lookat=(0.0, 0.0, 0.0),
    origin_type="world",
)
```

### **示例 2: 跟随机器人第三人称视角**
```python
VIEWER = ViewerCfg(
    eye=(0.0, -3.0, 2.0),   # 机器人后方 3 米，上方 2 米
    asset_name="robot",
    origin_type="asset_root",
)
```

### **示例 3: 相机向下倾斜 30 度**
```python
CAMERA_CFG = RayCasterCameraCfg(
    offset=RayCasterCameraCfg.OffsetCfg(
        pos=(0.3, 0.0, 0.1),
        rot=quat_from_euler_xyz_tuple(
            torch.tensor([0, np.deg2rad(30), 0])  # 向下 30°
        ),
        convention="ros",
    ),
)
```

---

## ⚙️ 如何调试相机位置

1. **运行测试脚本**查看效果：
```bash
python parkour_test/test_camera_custom.py --num_envs 1
```

2. **在 Isaac Sim 中手动调整**：
   - 按住鼠标中键：平移视角
   - 按住鼠标右键：旋转视角
   - 滚动鼠标滚轮：缩放视角

3. **查看相机在场景图中的位置**：
   - 打开 Isaac Sim 的 **Stage** 窗口
   - 找到 `/World/envs/env_0/Robot/base_link/d435`
   - 查看 Transform 属性

4. **打印相机实际位置**：
```python
camera = scene.sensors['depth_camera']
print(f"Camera position: {camera.data.pos_w[0]}")  # 世界坐标系位置
```

---

希望这个详细说明能帮助你理解和配置 Isaac Sim 中的相机视角！🎥
