# Student策略Sim2Sim实现

## 文件说明

`s2s_student_parkour.py` - Student策略的Sim2Sim实现，用于在MuJoCo环境中运行训练好的student策略模型。

## 主要特性

1. **Observation映射**: 正确映射MuJoCo的关节顺序到Isaac Lab的Policy顺序
2. **Depth Camera支持**: 集成depth camera传感器数据（使用ray caster插件）
3. **完整的Observation构造**: 包括extreme_parkour_observations、depth camera和delta_yaw_ok

## Observation结构

Student策略使用**两个独立的ONNX模型**：

### 1. Policy模型 (policy.onnx)
**输入**：
- `obs`: 753维
  - num_prop (53维): obs_buf - 角速度、IMU、delta_yaw、commands、关节位置/速度、动作历史、contact
  - num_scan (132维): measured_heights - 高度扫描数据（**会被depth_latent替换**）
  - num_priv_explicit (9维): 显式特权信息
  - num_priv_latent (29维): 隐式特权信息
  - num_hist (530维): 10帧历史obs_buf (10 × 53)
- `scandots_latent`: 32维 - 从depth_encoder得到的depth_latent（替换scan部分）

**输出**：
- `actions`: 12维动作

### 2. Depth Encoder模型 (depth_latest.onnx)
**输入**：
- `depth_image`: (1, 87, 58) - depth camera图像
- `proprioception`: (1, 53) - obs的前53维（num_prop），但delta_yaw部分设为0

**输出**：
- `depth_latent_and_yaw`: (depth_latent_dim + 2)
  - depth_latent: 32维（用于替换policy输入中的scan部分）
  - yaw: 2维（用于更新obs中的delta_yaw部分）

### 推理流程

1. 每5步更新一次depth_encoder
2. depth_encoder处理depth_image和proprioception，得到depth_latent和yaw
3. 用yaw更新obs中的delta_yaw部分（obs[:, 6:8] = 1.5 * yaw）
4. policy使用obs（753维）和depth_latent（32维，替换scan部分）进行推理

## 使用方法

```bash
cd s2s/scripts
python s2s_student_parkour.py \
    --policy_model /path/to/policy.onnx \
    --depth_model /path/to/depth_latest.onnx
```

例如：
```bash
python s2s_student_parkour.py \
    --policy_model ../../logs/rsl_rl/dogv2_parkour/2026-01-21_06-17-52/exported_deploy/policy.onnx \
    --depth_model ../../logs/rsl_rl/dogv2_parkour/2026-01-21_06-17-52/exported_deploy/depth_latest.onnx
```

## 配置说明

主要配置在`StudentSim2simCfg`类中：

- `sim_config.mujoco_model_path`: MuJoCo模型路径
- `sim_config.plugin_lib_path`: Ray caster插件路径
- `env.depth_image_size`: Depth camera图像尺寸 (58, 87)
- `env.frame_stack`: 历史帧数 (10)
- `env.depth_buffer_len`: Depth buffer长度 (2)

## 注意事项

1. **两个ONNX模型**: Student策略需要两个独立的ONNX模型：
   - `policy.onnx`: 处理observation和depth_latent
   - `depth_latest.onnx`: 处理depth image和proprioception

2. **关节顺序映射**: 代码中已经处理了MuJoCo和Isaac Lab之间的关节顺序差异

3. **Depth Camera**: 需要正确配置ray caster插件和传感器

4. **Depth Encoder更新频率**: depth_encoder每5步更新一次（类似Isaac Lab）

5. **Yaw更新**: depth_encoder输出的yaw用于更新obs中的delta_yaw部分（obs[:, 6:8] = 1.5 * yaw）

6. **Parkour状态**: 目前使用简化的parkour状态，实际应用时可能需要更复杂的实现

7. **Privileged信息**: 目前返回零数组，实际应用时应该从机器人状态获取

8. **Depth Image形状**: 注意depth_image的输入形状，根据agent.yaml应该是(87, 58)，即(height, width)

## 与s2s_trot_joystick.py的区别

1. **两个ONNX模型**: Student策略需要两个模型（policy和depth_encoder），而teacher只需要一个
2. **Observation结构**: Student策略的observation是753维（不含depth image），depth image通过单独的encoder处理
3. **Depth Latent**: depth_encoder将depth image编码为32维的latent，替换observation中的scan部分
4. **Yaw预测**: depth_encoder还预测yaw，用于更新observation中的delta_yaw部分
5. **更新频率**: depth_encoder每5步更新一次

## 依赖

- mujoco
- mujoco-viewer
- onnxruntime
- numpy
- scipy
- opencv-python
- joystick_interface (来自s2s目录)