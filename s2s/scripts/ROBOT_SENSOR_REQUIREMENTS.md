# 实机部署所需的机器人本体感知信息

## 概述

根据observation的组成（obs_buf，53维），以下是实机部署时需要从机器人本体获取的实际感知信息。

## obs_buf (53维) 详细组成

### 1. 基座角速度 (3维) ✅ **需要**

**位置**: obs_buf[0:3]  
**内容**: `root_ang_vel_b * 0.25`  
**获取方式**:
- **IMU**: 直接测量角速度（gyroscope）
- **状态估计**: 从其他传感器融合估计
- **坐标系**: Body frame（机器人本体坐标系）

**实机要求**:
- 需要IMU传感器或状态估计系统
- 输出3个轴的角速度（roll, pitch, yaw角速度）

---

### 2. IMU观测 (2维) ✅ **需要**

**位置**: obs_buf[3:5]  
**内容**: `[roll, pitch]` (wrap到[-π, π])  
**获取方式**:
- **IMU**: 直接测量姿态角
- **状态估计**: 从IMU数据融合得到

**实机要求**:
- 需要IMU传感器
- 输出roll和pitch角（yaw通常不准确，所以只用roll和pitch）

---

### 3. Delta Yaw相关 (3维) ⚠️ **部分需要**

**位置**: obs_buf[5:8]
- `obs_buf[5]`: 占位符（通常为0）
- `obs_buf[6]`: `delta_yaw` - 当前yaw与目标yaw的差值
- `obs_buf[7]`: `delta_next_yaw` - 当前yaw与下一个目标yaw的差值

**获取方式**:
- **当前yaw**: 从IMU或状态估计获取（但IMU的yaw通常不准确）
- **目标yaw**: 从路径规划或命令系统获取
- **注意**: 在student策略中，这部分会被depth_encoder预测的yaw更新

**实机要求**:
- 需要定位系统（如视觉里程计、GPS等）获取准确的yaw
- 或者使用depth_encoder预测的yaw（student策略）

---

### 4. Commands (3维) ✅ **需要**

**位置**: obs_buf[8:11]
- `obs_buf[8:9]`: 占位符（通常为0）
- `obs_buf[9]`: `commands[2]` - 命令的yaw角速度

**获取方式**:
- **外部输入**: 遥控器、路径规划系统、上层控制等

**实机要求**:
- 需要接收外部命令的接口
- 通常包括：v_x, v_y, omega_yaw（线速度和角速度）

---

### 5. 环境索引 (2维) ❌ **不需要（模拟环境特有）**

**位置**: obs_buf[11:13]
- `obs_buf[11]`: `env_idx_tensor` - 是否为parkour环境
- `obs_buf[12]`: `invert_env_idx_tensor` - 反转环境索引

**说明**:
- 这是模拟环境特有的，用于区分不同地形
- **实机部署时**: 可以设为固定值（如1.0和0.0）

---

### 6. 关节位置 (12维) ✅ **需要**

**位置**: obs_buf[13:25]  
**内容**: `(joint_pos - default_joint_pos) * scales.joint_pos`  
**获取方式**:
- **关节编码器**: 直接测量每个关节的角度

**实机要求**:
- 需要12个关节编码器（每条腿3个关节：HipA, HipF, Knee）
- 输出相对于默认位置的关节角度

---

### 7. 关节速度 (12维) ✅ **需要**

**位置**: obs_buf[25:37]  
**内容**: `joint_vel * 0.05`  
**获取方式**:
- **关节编码器**: 通过差分或直接测量关节角速度
- **状态估计**: 从位置差分得到

**实机要求**:
- 需要12个关节编码器
- 输出关节角速度（可能需要低通滤波）

---

### 8. 上一帧动作 (12维) ✅ **需要（内部记录）**

**位置**: obs_buf[37:49]  
**内容**: `action_history[-1]` - 上一帧输出的动作

**获取方式**:
- **内部记录**: 记录上一帧policy输出的动作

**实机要求**:
- 需要在控制系统中记录上一帧的动作
- 这是policy的输出，不是传感器数据

---

### 9. 接触力信息 (4维) ⚠️ **可选（推荐）**

**位置**: obs_buf[49:53]  
**内容**: `contact_fill` - 4个脚的接触状态

**获取方式**:
- **接触力传感器**: 直接测量脚部接触力
- **状态估计**: 从关节扭矩、IMU等估计
- **简化方法**: 从关节位置和速度估计（不准确但可用）

**代码实现**:
```python
def _get_contact_fill(self):
    contact_forces = self.contact_sensor.data.net_forces_w_history[:, 0, self.sensor_cfg.body_ids]
    contact = torch.norm(contact_forces, dim=-1) > 2.0  # 阈值2.0N
    previous_contact_forces = self.contact_sensor.data.net_forces_w_history[:, -1, self.sensor_cfg.body_ids]
    last_contacts = torch.norm(previous_contact_forces, dim=-1) > 2.0
    contact_filt = torch.logical_or(contact, last_contacts)
    return (contact_filt.float() - 0.5)  # 转换为[-0.5, 0.5]
```

**实机要求**:
- **推荐**: 使用接触力传感器（如FSR、力/力矩传感器）
- **备选**: 从关节扭矩估计（需要关节扭矩传感器）
- **简化**: 从关节位置和速度估计（准确性较低）

---

## 总结：实机必需的传感器

### ✅ 必需传感器

1. **IMU**:
   - 角速度（3轴）
   - 姿态角（roll, pitch）
   - 可选：yaw（但通常不准确）

2. **关节编码器** (12个):
   - 关节位置（12个关节）
   - 关节速度（通过差分或直接测量）

3. **命令接收系统**:
   - 接收外部命令（v_x, v_y, omega_yaw）

4. **定位系统**（用于yaw）:
   - 视觉里程计
   - GPS（室外）
   - 或其他定位方法
   - **或**: 使用depth_encoder预测的yaw（student策略）

### ⚠️ 推荐传感器

5. **接触力传感器** (4个脚):
   - 直接测量脚部接触力
   - 或从关节扭矩估计

### ❌ 不需要（模拟环境特有）

6. **环境索引**: 可以设为固定值

---

## 实机部署时的处理

### 1. 可以直接获取的（传感器数据）

```python
# 从传感器获取
root_ang_vel_b = imu.get_angular_velocity()  # 3维
roll, pitch = imu.get_roll_pitch()  # 2维
joint_pos = encoders.get_positions()  # 12维
joint_vel = encoders.get_velocities()  # 12维
contact_forces = contact_sensors.get_forces()  # 4维（如果有）
```

### 2. 需要计算的

```python
# Delta yaw（需要定位系统）
current_yaw = localization.get_yaw()
target_yaw = path_planner.get_target_yaw()
delta_yaw = target_yaw - current_yaw

# 或使用depth_encoder预测（student策略）
delta_yaw = depth_encoder_predicted_yaw
```

### 3. 可以设为固定值的

```python
# 环境索引（模拟环境特有）
env_idx_tensor = 1.0  # 固定值
invert_env_idx_tensor = 0.0  # 固定值
```

### 4. 内部记录的

```python
# 上一帧动作（policy输出）
action_history = last_action  # 12维
```

---

## 传感器配置示例

### 最小配置（基本功能）

```
IMU: 1个
  - 角速度（3轴）
  - 姿态角（roll, pitch）

关节编码器: 12个
  - 位置编码器
  - 速度编码器（或通过差分）

命令接收: 1个接口
  - 接收v_x, v_y, omega_yaw

定位系统: 1个（用于yaw）
  - 或使用depth_encoder预测
```

### 推荐配置（更好性能）

```
IMU: 1个
关节编码器: 12个
接触力传感器: 4个（每个脚）
命令接收: 1个接口
定位系统: 1个
```

---

## 注意事项

1. **坐标系转换**:
   - 角速度需要转换到body frame
   - 关节顺序需要映射到Policy顺序

2. **数据预处理**:
   - 角速度需要乘以0.25
   - 关节速度需要乘以0.05
   - 关节位置需要减去默认位置

3. **Contact Fill**:
   - 如果没有接触力传感器，可以从关节扭矩估计
   - 或使用简化的接触检测（如关节位置阈值）

4. **Delta Yaw**:
   - 在student策略中，这部分会被depth_encoder预测的yaw更新
   - 如果使用depth_encoder，可以不需要准确的定位系统

5. **历史帧**:
   - 需要保存10帧历史obs_buf
   - 用于历史编码（hist_encoding）

---

## 代码示例：构造obs_buf

```python
def construct_obs_buf(imu_data, encoders, commands, contact_sensors, last_action):
    """从实机传感器数据构造obs_buf"""
    
    # 1. 基座角速度 (3维)
    root_ang_vel_b = imu_data['angular_velocity'] * 0.25
    
    # 2. IMU观测 (2维)
    roll, pitch = imu_data['roll'], imu_data['pitch']
    imu_obs = np.array([wrap_to_pi(roll), wrap_to_pi(pitch)])
    
    # 3. Delta yaw (3维) - 需要定位或depth_encoder
    delta_yaw = calculate_delta_yaw()  # 或使用depth_encoder预测
    delta_next_yaw = calculate_delta_next_yaw()
    
    # 4. Commands (3维)
    cmd_yaw = commands['omega_yaw']
    
    # 5. 环境索引 (2维) - 固定值
    env_idx_tensor = 1.0
    invert_env_idx_tensor = 0.0
    
    # 6. 关节位置 (12维)
    joint_pos = encoders['positions'] - default_joint_pos
    
    # 7. 关节速度 (12维)
    joint_vel = encoders['velocities'] * 0.05
    
    # 8. 上一帧动作 (12维)
    action_history = last_action
    
    # 9. 接触力信息 (4维)
    contact_fill = calculate_contact_fill(contact_sensors)
    
    # 拼接
    obs_buf = np.concatenate([
        root_ang_vel_b,      # 3
        imu_obs,             # 2
        np.array([0.0]),     # 1
        np.array([delta_yaw]),  # 1
        np.array([delta_next_yaw]),  # 1
        np.zeros(2),         # 2
        np.array([cmd_yaw]), # 1
        np.array([env_idx_tensor]),  # 1
        np.array([invert_env_idx_tensor]),  # 1
        joint_pos,           # 12
        joint_vel,           # 12
        action_history,      # 12
        contact_fill,        # 4
    ])
    
    return obs_buf  # 总共53维
```
