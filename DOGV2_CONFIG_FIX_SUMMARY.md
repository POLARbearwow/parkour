# DogV2 配置文件修复总结

## 📋 修复的问题

### **1. `default_cfg_custom.py` - 主要配置文件**

#### ❌ **修复前的错误**：
```python
# 第 3 行：还在导入 Go2 配置
from isaaclab_assets.robots.unitree import UNITREE_GO2_CFG  # 错误！

# 第 9 行：使用 Go2 的 agents 路径
from parkour_tasks.extreme_parkour_task.config.go2 import agents  # 错误！

# 第 41 行：默认场景使用 Go2
robot: ArticulationCfg = UNITREE_GO2_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")  # 错误！

# 第 102 行：相机模型使用 Go2 路径
spawn=sim_utils.UsdFileCfg(usd_path=os.path.join(agents.__path__[0], "d435.usd"))  # 错误！
```

#### ✅ **修复后的正确配置**：
```python
# 导入 DogV2 agents 和自定义机器人配置
from parkour_tasks.extreme_parkour_task.config.dogv2 import agents  # ✅ DogV2
from parkour_tasks.custom_robot_cfg import CustomRobotCfg  # ✅ 自定义机器人

# 默认场景使用 DogV2 自定义机器人
robot: ArticulationCfg = CustomRobotCfg(prim_path="{ENV_REGEX_NS}/Robot")  # ✅

# 相机模型使用 DogV2 agents 路径
spawn=sim_utils.UsdFileCfg(
    usd_path=os.path.join(agents.__path__[0], "d435.usd")  # ✅ DogV2 agents
)
```

---

## 📂 创建的新文件/目录

### **1. DogV2 agents 目录**
```bash
parkour_tasks/parkour_tasks/extreme_parkour_task/config/dogv2/agents/
├── __init__.py       # 新创建
└── d435.usd          # 从 go2/agents 复制
```

### **2. 新文档**
```bash
/home/ares/IsaacLab/Isaaclab_Parkour/
└── PRIM_PATH_EXPLANATION.md  # Prim Path 路径说明文档
```

---

## 🔑 关键路径说明

### **`prim_path="{ENV_REGEX_NS}/Robot/base_link/d435"`**

这是 **Isaac Sim 场景图中的对象路径**，类似文件系统路径：

#### **路径组成**：
```
{ENV_REGEX_NS}          # 环境命名空间占位符（运行时替换）
    ↓
/World/envs/env_0       # 实际路径（第 0 个环境）
/World/envs/env_1       # 实际路径（第 1 个环境）
...

/Robot                  # 机器人根节点
    ↓
/Robot/base_link        # 基座连杆（父节点）
    ↓
/Robot/base_link/d435   # 相机 USD 模型（子节点）
```

#### **完整实际路径示例**（env_0）：
```
/World/envs/env_0/Robot/base_link/d435
```

#### **为什么用 `{ENV_REGEX_NS}`？**
- ✅ **自动适配多环境**：同时创建 6144 个环境时，每个环境都会有相机
- ✅ **避免硬编码**：不需要手动指定 env_0, env_1, ...
- ✅ **简化配置**：一个配置应用到所有环境

---

## 📊 修复对比表

| 项目 | 修复前（Go2） | 修复后（DogV2） |
|------|--------------|----------------|
| **导入** | `from ...go2 import agents` | `from ...dogv2 import agents` ✅ |
| **机器人配置** | `UNITREE_GO2_CFG` | `CustomRobotCfg` ✅ |
| **agents 路径** | `.../go2/agents/d435.usd` | `.../dogv2/agents/d435.usd` ✅ |
| **BASE_LINK** | `base` | `base_link` ✅ |
| **执行器配置** | Go2 执行器参数 | DogV2 执行器参数 ✅ |
| **关节命名** | `.*_hip/.*_thigh` | `.*_HipA/.*_HipF/.*_Knee` ✅ |

---

## 🎯 文件功能说明

### **1. `default_cfg_custom.py`**
**作用**：DogV2 的默认场景配置
**包含**：
- `ParkourDefaultSceneCfg`：场景配置基类（机器人、地形、光照）
- `CAMERA_CFG`：深度相机功能配置（实际采集数据）
- `CAMERA_USD_CFG`：相机 USD 模型（可视化）
- `VIEWER`：视角配置

### **2. `custom_robot_cfg.py`**
**作用**：DogV2 机器人配置
**包含**：
- USD 文件路径：`dogV2.2.4.sep.usd`
- 初始状态：位置、姿态、速度
- 执行器配置：髋关节、膝关节的 PD 参数

### **3. `agents/__init__.py`**
**作用**：DogV2 agents 包标识
**用途**：让 Python 识别 `agents` 为一个包，可以通过 `agents.__path__[0]` 获取目录路径

### **4. `agents/d435.usd`**
**作用**：Intel RealSense D435 深度相机的 3D 模型
**大小**：16.6 MB
**用途**：在仿真中显示相机的外观（纯视觉，不影响深度数据采集）

---

## ✅ 验证修复

运行以下命令验证配置是否正确：

### **1. 测试地形生成**
```bash
cd /home/ares/IsaacLab/Isaaclab_Parkour
python parkour_test/test_terrain_generator_custom.py --num_envs 1
```

### **2. 测试相机**
```bash
python parkour_test/test_camera_custom.py --num_envs 1
```

### **3. 训练 Teacher Policy**
```bash
python scripts/rsl_rl/train.py \
    --task Isaac-Extreme-Parkour-Teacher-DogV2-v0 \
    --num_envs 4096 \
    --headless
```

### **4. 训练 Student Policy**
```bash
python scripts/rsl_rl/train.py \
    --task Isaac-Extreme-Parkour-Student-DogV2-v0 \
    --num_envs 192 \
    --headless
```

---

## 📖 相关文档

1. **`PRIM_PATH_EXPLANATION.md`** - Prim Path 路径详细说明
2. **`TASK_USAGE_GUIDE.md`** - 任务使用指南
3. **`ROBOT_REPLACEMENT_GUIDE.md`** - 机器人替换指南

---

## 🐛 如果还有问题

### **常见错误 1：找不到 agents 模块**
```bash
ModuleNotFoundError: No module named 'parkour_tasks.extreme_parkour_task.config.dogv2.agents'
```

**解决方案**：确保创建了 `agents/__init__.py` 文件

### **常见错误 2：找不到 d435.usd**
```bash
FileNotFoundError: .../dogv2/agents/d435.usd
```

**解决方案**：从 go2/agents 复制 d435.usd 到 dogv2/agents

### **常见错误 3：body 名称不匹配**
```bash
ValueError: Not all regular expressions are matched! .*_foot.*: []
```

**解决方案**：检查 `parkour_mdp_cfg_custom.py` 中的 body 名称是否与 USD 文件中的名称一致

---

## ✨ 修复完成！

现在 `default_cfg_custom.py` 和 `custom_robot_cfg.py` 已经完全针对 **DogV2 机器人**配置，不再依赖 Go2 的配置。所有路径、命名和参数都已更新为 DogV2 特定的值。

**主要改进**：
- ✅ 移除了所有 Go2 相关的导入和配置
- ✅ 使用 DogV2 自定义机器人配置
- ✅ 创建了独立的 DogV2 agents 目录结构
- ✅ 添加了详细的注释说明
- ✅ 创建了 Prim Path 路径说明文档

现在可以放心地训练和测试 DogV2 机器人了！🚀
