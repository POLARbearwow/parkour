# Prim Path 名称说明

## 为什么使用 `DOGV2_2_4_SLDASM_base_link`？

### 1. 来源
这个名称来自您的 **URDF文件** (`dogV2.2.4.sep.urdf`)：

```xml
<link name="DOGV2_2_4_SLDASM_base_link">
```

在URDF文件的第513行，确实定义了这个link名称。

### 2. ⚠️ 重要区别：URDF vs USD

**关键问题**：URDF文件中的link名称 **不一定** 等于USD文件中的prim路径！

- **URDF文件**：定义了机器人的结构，link名称是 `DOGV2_2_4_SLDASM_base_link`
- **USD文件**：在Isaac Sim中加载时，prim路径可能不同

### 3. 可能的情况

USD文件中的prim路径可能是：
- ✅ `DOGV2_2_4_SLDASM_base_link` (与URDF一致)
- ✅ `base` (简化名称)
- ✅ `base_link` (简化名称)
- ✅ `DOGV2_2_4_SLDASM` (根节点名称)
- ❌ 其他自定义名称

### 4. 如何确认正确的prim路径？

**方法1：在Isaac Sim中检查**
1. 打开Isaac Sim
2. 加载您的USD文件 (`dogV2.2.4.sep.usd`)
3. 在Stage窗口中查看prim层级结构
4. 找到base link的实际prim路径

**方法2：使用代码检查**
```python
# 在场景加载后打印所有body名称
asset = env.scene["robot"]
print("Body names:", asset.body_names)
# 查找包含"base"的名称
base_bodies = [name for name in asset.body_names if "base" in name.lower()]
print("Base bodies:", base_bodies)
```

### 5. 当前配置的假设

我在配置文件中使用了 `DOGV2_2_4_SLDASM_base_link`，这是基于：
- URDF文件中的link名称
- **假设** USD文件中的prim路径与URDF一致

### 6. 如果prim路径不同怎么办？

如果USD文件中的实际prim路径不同，需要更新以下文件中的prim_path：

1. `parkour_tasks/parkour_tasks/default_cfg_custom.py`
   - `CAMERA_CFG.prim_path`
   - `CAMERA_USD_CFG.prim_path`

2. `parkour_tasks/parkour_tasks/extreme_parkour_task/config/dogv2/parkour_teacher_cfg_custom.py`
   - `height_scanner.prim_path`

3. `parkour_test/test_camera_custom.py`
   - `CAMERA_CFG.prim_path`
   - `CAMERA_USD_CFG.prim_path`

4. `parkour_test/test_terrain_generator_custom.py`
   - `height_scanner.prim_path`

### 7. 推荐的解决方案

**选项A：使用通配符（如果支持）**
```python
prim_path="{ENV_REGEX_NS}/Robot/.*base.*"
```

**选项B：先检查，再配置**
1. 运行测试脚本
2. 打印body名称
3. 根据实际名称更新配置

**选项C：使用更通用的匹配**
如果USD文件中的base link名称是 `base` 或 `base_link`，可以尝试：
```python
prim_path="{ENV_REGEX_NS}/Robot/base"  # 或 base_link
```

## 总结

- `DOGV2_2_4_SLDASM_base_link` 来自URDF文件
- USD文件中的实际prim路径可能不同
- **必须**在Isaac Sim中验证实际的prim路径
- 根据实际路径更新配置文件
