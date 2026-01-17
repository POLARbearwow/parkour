# 自定义配置文件说明

## 📁 文件结构

所有原始文件已恢复，新的自定义配置文件已创建在以下位置：

### 核心配置文件

1. **`parkour_tasks/parkour_tasks/custom_robot_cfg.py`** ✅
   - 自定义机器人配置（dogV2.2.4）
   - 使用您的USD文件
   - 配置了ImplicitActuatorCfg执行器

2. **`parkour_tasks/parkour_tasks/default_cfg_custom.py`** ✅
   - 自定义默认场景配置
   - 原始文件: `default_cfg.py` (保留作为参考)
   - 使用CustomRobotCfg
   - 更新了相机prim_path

### MDP配置文件

3. **`parkour_tasks/parkour_tasks/extreme_parkour_task/config/dogv2/parkour_mdp_cfg_custom.py`** ✅
   - 自定义MDP配置
   - 原始文件: `../go2/parkour_mdp_cfg.py` (保留作为参考)
   - 更新了关节和身体名称匹配规则

4. **`parkour_tasks/parkour_tasks/extreme_parkour_task/config/dogv2/parkour_teacher_cfg_custom.py`** ✅
   - 自定义Teacher配置
   - 原始文件: `../go2/parkour_teacher_cfg.py` (保留作为参考)
   - 更新了传感器prim_path

5. **`parkour_tasks/parkour_tasks/extreme_parkour_task/config/dogv2/parkour_student_cfg_custom.py`** ✅
   - 自定义Student配置
   - 原始文件: `../go2/parkour_student_cfg.py` (保留作为参考)

### 测试文件

6. **`parkour_test/test_camera_custom.py`** ✅
   - 自定义相机测试
   - 原始文件: `test_camera.py` (保留作为参考)

7. **`parkour_test/test_terrain_generator_custom.py`** ✅
   - 自定义地形生成器测试
   - 原始文件: `test_terrain_generator.py` (保留作为参考)

## 🔧 主要修改内容

### 1. 关节名称匹配
- **原始**: `.*_hip_joint`, `.*_thigh_joint`, `.*_calf_joint`
- **自定义**: `.*_HipA_joint`, `.*_HipF_joint`, `.*_Knee_joint`

### 2. 身体名称匹配
- **原始**: `FL_foot`, `FR_foot`, `RL_foot`, `RR_foot`, `base`
- **自定义**: `.*LF_Foot.*`, `.*RF_Foot.*`, `.*LR_Foot.*`, `.*RR_Foot.*`, `.*base.*`

### 3. 传感器prim_path
- **原始**: `{ENV_REGEX_NS}/Robot/base`
- **自定义**: `{ENV_REGEX_NS}/Robot/DOGV2_2_4_SLDASM_base_link`
  - ⚠️ **注意**: 请根据USD文件中的实际prim路径调整

## 📝 使用方法

### 方法1: 直接导入自定义配置

```python
# 在您的代码中导入自定义配置
from parkour_tasks.default_cfg_custom import ParkourDefaultSceneCfg
from parkour_tasks.extreme_parkour_task.config.dogv2.parkour_teacher_cfg_custom import DogV2TeacherParkourEnvCfg
```

### 方法2: 替换原始文件（不推荐）

如果您想直接使用自定义配置，可以：
1. 备份原始文件
2. 将 `*_custom.py` 文件重命名或复制到原始位置

## ⚠️ 重要注意事项

### 1. USD文件路径验证
所有配置中使用的prim_path基于URDF文件中的名称。**请务必**：
- 在Isaac Sim中打开您的USD文件
- 确认实际的prim路径
- 如果不同，更新所有配置文件中的prim_path

### 2. 关节和身体名称验证
运行测试脚本后，打印并验证：
```python
asset = env.scene["robot"]
print("Joint names:", asset.joint_names)
print("Body names:", asset.body_names)
```

### 3. 配置类名称
自定义配置使用了新的类名（如 `DogV2TeacherParkourEnvCfg`），避免与原始配置冲突。

## 🧪 测试

运行自定义测试文件：
```bash
# 测试相机
python parkour_test/test_camera_custom.py

# 测试地形生成器
python parkour_test/test_terrain_generator_custom.py
```

## 📋 文件对比

| 原始文件 | 自定义文件 | 状态 |
|---------|-----------|------|
| `default_cfg.py` | `default_cfg_custom.py` | ✅ 已创建 |
| `go2/parkour_mdp_cfg.py` | `dogv2/parkour_mdp_cfg_custom.py` | ✅ 已创建 |
| `go2/parkour_teacher_cfg.py` | `dogv2/parkour_teacher_cfg_custom.py` | ✅ 已创建 |
| `go2/parkour_student_cfg.py` | `dogv2/parkour_student_cfg_custom.py` | ✅ 已创建 |
| `test_camera.py` | `test_camera_custom.py` | ✅ 已创建 |
| `test_terrain_generator.py` | `test_terrain_generator_custom.py` | ✅ 已创建 |

所有原始文件已恢复，可以继续作为参考使用！
