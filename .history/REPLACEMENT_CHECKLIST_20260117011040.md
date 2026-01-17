# 机器人替换检查清单

使用此清单确保所有必要的步骤都已完成。

## 准备工作

- [ ] 确认USD文件已准备好（`dogV2.2.4.sep.usd`）
- [ ] 在Isaac Sim中打开USD文件，检查：
  - [ ] 关节名称
  - [ ] 身体（link）名称
  - [ ] 基座（base）的prim路径
  - [ ] 物理属性是否正确设置

## 步骤 1: 创建机器人配置

- [ ] 创建 `parkour_tasks/parkour_tasks/custom_robot_cfg.py`
- [ ] 确认USD文件路径正确
- [ ] 调整初始位置（Z轴高度）

## 步骤 2: 更新默认配置

- [ ] 修改 `parkour_tasks/parkour_tasks/default_cfg.py`:
  - [ ] 替换导入语句（`UNITREE_GO2_CFG` → `CustomRobotCfg`）
  - [ ] 替换机器人配置
  - [ ] 更新执行器配置中的关节名称匹配规则

## 步骤 3: 更新关节名称

- [ ] 检查USD文件中的实际关节名称
- [ ] 更新 `default_cfg.py` 中的 `joint_names_expr`
- [ ] 更新 `effort_limit`、`saturation_effort`、`velocity_limit`
- [ ] 根据URDF文件中的限制值调整参数

## 步骤 4: 更新身体名称

- [ ] 检查USD文件中的实际身体名称
- [ ] 更新 `parkour_mdp_cfg.py` 中的奖励配置：
  - [ ] `reward_feet_edge` 的 `body_names`
  - [ ] `reward_collision` 的 `body_names`
- [ ] 更新观察配置中的 `body_names`

## 步骤 5: 更新传感器配置

- [ ] 检查相机配置中的 `prim_path`（基座路径）
- [ ] 确认接触力传感器的 `prim_path` 正确
- [ ] 如果基座名称不同，更新所有相关路径

## 步骤 6: 更新测试文件

- [ ] 更新 `parkour_test/test_camera.py`
- [ ] 更新 `parkour_test/test_terrain_generator.py`

## 步骤 7: 验证

- [ ] 运行测试脚本检查场景加载
- [ ] 打印并验证关节名称列表
- [ ] 打印并验证身体名称列表
- [ ] 检查关节数量是否正确（应该是12个，每条腿3个）
- [ ] 检查脚部身体数量（应该是4个）

## 常见问题检查

- [ ] 关节名称匹配是否正确？
- [ ] 身体名称匹配是否正确？
- [ ] 执行器配置是否匹配所有关节？
- [ ] 传感器prim_path是否正确？
- [ ] 初始高度是否合适（机器人不会掉入地面）？

## 测试命令

```bash
# 测试场景加载
python parkour_test/test_terrain_generator.py

# 如果配置了训练脚本，可以尝试运行
# python scripts/rsl_rl/train.py task=extreme_parkour_task ...
```

## 调试技巧

1. **打印关节和身体名称：**
   ```python
   asset = env.scene["robot"]
   print("Joint names:", asset.joint_names)
   print("Body names:", asset.body_names)
   ```

2. **检查关节数量：**
   ```python
   print("Number of joints:", asset.num_joints)
   ```

3. **检查身体数量：**
   ```python
   print("Number of bodies:", asset.num_bodies)
   ```

4. **验证正则表达式匹配：**
   ```python
   import re
   joint_names = asset.joint_names
   pattern = ".*HipA_joint"
   matched = [name for name in joint_names if re.match(pattern, name)]
   print(f"Matched joints with '{pattern}':", matched)
   ```
