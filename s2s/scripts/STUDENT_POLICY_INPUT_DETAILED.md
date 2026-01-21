# Student Policy 输入详细说明

## 概述

Student Policy需要**两个输入**：
1. **obs**: 753维的observation向量
2. **scandots_latent**: 32维的depth latent（从depth_encoder得到）

## 输入1: Observation (obs) - 753维

Observation向量按以下顺序组成：

### 1. num_prop (53维) - Proprioception

这是`obs_buf`部分，包含机器人的本体感知信息：

```
索引  维度  内容                        说明
0-2   3     root_ang_vel_b * 0.25      基座角速度（body frame，已缩放）
3-4   2     imu_obs                     IMU观测（roll, pitch）
5     1     0 * delta_yaw               占位符（通常为0）
6     1     delta_yaw                   当前yaw与目标yaw的差值
7     1     delta_next_yaw             当前yaw与下一个目标yaw的差值
8-9   2     0 * commands[:2]            占位符（通常为0）
10    1     commands[2] * scales        命令的yaw角速度
11    1     env_idx_tensor              环境索引（是否为parkour环境）
12    1     invert_env_idx_tensor       反转环境索引
13-24 12    joint_pos - default_pos     关节位置（相对于默认位置）
25-36 12    joint_vel * 0.05            关节速度（已缩放）
37-48 12    action_history[-1]          上一帧的动作
49-52 4     contact_fill                接触力信息（4个脚）
```

**注意**：
- 在student策略中，`obs_buf[6:8]`（delta_yaw部分）会被depth_encoder预测的yaw更新
- 更新方式：`obs[:, 6:8] = 1.5 * yaw`（其中yaw来自depth_encoder的输出）

### 2. num_scan (132维) - Measured Heights

高度扫描数据，来自ray caster传感器：
- 132个高度测量点
- 在实际推理时，**这部分会被depth_latent（32维）替换**

### 3. num_priv_explicit (9维) - Explicit Privileged Information

显式特权信息：
```
索引  维度  内容
0-2   3     base_lin_vel * 2.0          基座线速度（body frame，已缩放）
3-5   3     0 * base_lin_vel            占位符（通常为0）
6-8   3     0 * base_lin_vel            占位符（通常为0）
```

### 4. num_priv_latent (29维) - Latent Privileged Information

隐式特权信息（通过encoder编码）：
```
索引  维度  内容
0     1     body_mass                   基座质量
1-3   3     body_com                    基座质心位置
4     1     friction_coeff              摩擦系数
5-16  12    joint_stiffness_ratio       关节刚度比例（相对于默认值）
17-28 12    joint_damping_ratio         关节阻尼比例（相对于默认值）
```

### 5. num_hist (530维) - History

历史帧数据：
- 10帧历史obs_buf
- 每帧53维（num_prop）
- 总共：10 × 53 = 530维

历史帧按时间顺序排列（最旧的在前面，最新的在后面）

## 输入2: scandots_latent (32维) - Depth Latent

这是从`depth_encoder`（depth_latest.onnx）得到的编码特征：

### Depth Encoder的输入：
1. **depth_image**: (1, 87, 58) - depth camera图像
   - 形状：(height, width) = (87, 58)
   - 已经过预处理：crop、resize、归一化
   
2. **proprioception**: (1, 53) - obs的前53维（num_prop）
   - **重要**：在输入depth_encoder之前，`proprioception[6:8]`（delta_yaw部分）会被设为0

### Depth Encoder的输出：
- **depth_latent_and_yaw**: (depth_latent_dim + 2)
  - `depth_latent`: 32维 - 用于替换observation中的scan部分
  - `yaw`: 2维 - 用于更新observation中的delta_yaw部分

### Depth Latent的作用：
- 替换observation中的132维scan数据
- 通过scan_encoder编码后，输出32维的latent
- 这个32维latent与53维proprioception拼接，形成85维的输入进入actor backbone

## Actor网络的处理流程

### 1. 输入处理

```python
# 1. 提取proprioception (53维)
obs_prop = obs[:, :53]

# 2. 处理scan部分
# 如果提供了scandots_latent，使用它；否则使用obs中的scan部分（132维）通过scan_encoder编码
if scandots_latent is not None:
    scan_latent = scandots_latent  # 32维（从depth_encoder得到）
else:
    obs_scan = obs[:, 53:53+132]  # 132维
    scan_latent = scan_encoder(obs_scan)  # 编码为32维

# 3. 拼接proprioception和scan_latent
obs_prop_scan = concat([obs_prop, scan_latent])  # 53 + 32 = 85维
```

### 2. 提取其他部分

```python
# 4. 提取显式特权信息
obs_priv_explicit = obs[:, 53+132:53+132+9]  # 9维

# 5. 处理隐式特权信息（通过history encoder）
hist = obs[:, -530:]  # 530维（10帧历史）
hist_latent = history_encoder(hist.view(-1, 10, 53))  # 编码为20维（priv_encoder_dims[-1]）
```

### 3. Actor Backbone输入

```python
# 6. 拼接所有部分
backbone_input = concat([
    obs_prop_scan,      # 85维 (53 + 32)
    obs_priv_explicit,  # 9维
    hist_latent         # 20维
])  # 总共：85 + 9 + 20 = 114维
```

### 4. Actor Backbone结构

```
输入: 114维
  ↓
Linear(114 → 512) + ELU
  ↓
Linear(512 → 256) + ELU
  ↓
Linear(256 → 128) + ELU
  ↓
Linear(128 → 12)  # 输出12维动作
```

## 完整的数据流

```
┌─────────────────────────────────────────────────────────┐
│ 1. 获取Observation (753维)                              │
│    - num_prop: 53维                                      │
│    - num_scan: 132维 (占位，会被替换)                    │
│    - num_priv_explicit: 9维                              │
│    - num_priv_latent: 29维                               │
│    - num_hist: 530维                                      │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 2. Depth Encoder处理 (每5步更新一次)                     │
│    输入:                                                  │
│      - depth_image: (87, 58)                             │
│      - proprioception: obs[:53] (delta_yaw部分设为0)     │
│    输出:                                                  │
│      - depth_latent: 32维                                 │
│      - yaw: 2维                                          │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 3. 更新Observation                                       │
│    - obs[6:8] = 1.5 * yaw  # 更新delta_yaw部分          │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ 4. Policy推理                                            │
│    输入:                                                  │
│      - obs: 753维                                        │
│      - scandots_latent: 32维 (depth_latent)              │
│    处理:                                                  │
│      - obs_prop_scan = concat([obs[:53], scandots_latent]) │
│      - obs_priv_explicit = obs[53+132:53+132+9]          │
│      - hist_latent = history_encoder(obs[-530:])         │
│      - backbone_input = concat([obs_prop_scan,           │
│                                  obs_priv_explicit,       │
│                                  hist_latent])           │
│    输出:                                                  │
│      - actions: 12维                                     │
└─────────────────────────────────────────────────────────┘
```

## 关键配置参数

根据`agent.yaml`：

```yaml
actor:
  num_prop: 53              # proprioception维度
  num_scan: 132             # scan维度（会被depth_latent替换）
  num_priv_explicit: 9      # 显式特权信息维度
  num_priv_latent: 29       # 隐式特权信息维度
  num_hist: 10              # 历史帧数

scan_encoder_dims: [128, 64, 32]  # scan编码器输出32维
priv_encoder_dims: [64, 20]        # priv编码器输出20维
```

## 注意事项

1. **Delta Yaw更新**：
   - depth_encoder输出的yaw用于更新obs中的delta_yaw部分
   - 更新公式：`obs[:, 6:8] = 1.5 * yaw`
   - 这发生在depth_encoder推理之后，policy推理之前

2. **Depth Encoder更新频率**：
   - depth_encoder每5步更新一次（类似Isaac Lab的实现）
   - 在非更新步骤，使用上一次的depth_latent和yaw

3. **Proprioception输入depth_encoder**：
   - 输入depth_encoder的proprioception是obs的前53维
   - **重要**：在输入之前，`proprioception[6:8]`会被设为0

4. **Scan部分替换**：
   - observation中的132维scan部分在policy推理时不会被使用
   - 实际使用的是depth_encoder输出的32维depth_latent
   - 这32维latent通过`scandots_latent`参数传入actor

5. **历史帧处理**：
   - 历史帧包含10帧的obs_buf（每帧53维）
   - 通过StateHistoryEncoder编码为20维的latent
   - 这个latent与proprioception、scan_latent、priv_explicit一起输入actor backbone

## 总结

Student Policy的输入结构：
- **obs**: 753维 = 53(prop) + 132(scan占位) + 9(priv_explicit) + 29(priv_latent) + 530(hist)
- **scandots_latent**: 32维（从depth_encoder得到，替换scan部分）

实际进入actor backbone的输入：
- **backbone_input**: 114维 = 85(prop+scan_latent) + 9(priv_explicit) + 20(hist_latent)
