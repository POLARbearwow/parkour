# Student Policy 推理时输入 - 代码位置说明

## 关键代码位置

### 1. Actor的forward函数定义

**文件**: `scripts/rsl_rl/modules/actor_critic_with_encoder.py`

**行数**: 89-111

```python
def forward(
    self, 
    obs,                    # 输入1: observation (753维)
    hist_encoding: bool,    # 输入2: 是否使用历史编码
    scandots_latent: Optional[torch.Tensor] = None  # 输入3: depth_latent (32维)
    ):
    if self.if_scan_encode:
        obs_scan = obs[:, self.num_prop:self.num_prop + self.num_scan]
        if scandots_latent is None:
            scan_latent = self.scan_encoder(obs_scan)   
        else:
            scan_latent = scandots_latent  # 使用传入的depth_latent
        obs_prop_scan = torch.cat([obs[:, :self.num_prop], scan_latent], dim=1)
    # ... 后续处理
```

**说明**：
- `obs`: 753维的observation向量
- `scandots_latent`: 32维的depth_latent（从depth_encoder得到）
- `hist_encoding`: 布尔值，表示是否使用历史编码

---

### 2. Policy的act_inference函数

**文件**: `scripts/rsl_rl/modules/actor_critic_with_encoder.py`

**行数**: 224-226

```python
def act_inference(self, observations, hist_encoding=False, scandots_latent=None, **kwargs):
    actions_mean = self.actor(observations, hist_encoding, scandots_latent)
    return actions_mean
```

**说明**：
- 这是推理时调用的函数
- 直接调用actor的forward函数
- 参数与actor的forward一致

---

### 3. 实际推理调用 - play.py

**文件**: `scripts/rsl_rl/play.py`

**行数**: 186

```python
# Student策略推理
actions = policy(obs, hist_encoding=True, scandots_latent=depth_latent)
```

**完整上下文** (175-186行):
```python
else:
    depth_camera = extras["observations"]['depth_camera'].to(env.device)
    with torch.inference_mode():
        if env.unwrapped.common_step_counter %5 == 0:
            obs_student = obs[:, :num_prop].clone()
            obs_student[:, 6:8] = 0
            depth_latent_and_yaw = depth_encoder(depth_camera, obs_student)
            depth_latent = depth_latent_and_yaw[:, :-2]
            yaw = depth_latent_and_yaw[:, -2:]
        obs[:, 6:8] = 1.5*yaw
        # 关键：这里调用policy，传入obs和depth_latent
        actions = policy(obs, hist_encoding=True, scandots_latent=depth_latent)
```

**说明**：
- `obs`: 753维的observation（已更新delta_yaw部分）
- `hist_encoding=True`: 使用历史编码
- `scandots_latent=depth_latent`: 32维的depth_latent

---

### 4. 实际推理调用 - demo.py

**文件**: `scripts/rsl_rl/demo.py`

**行数**: 242

```python
# Student策略推理
action = demo_go2.policy(obs, hist_encoding=True, scandots_latent=depth_latent)
```

**完整上下文** (234-242行):
```python
else:
    depth_camera = extras["observations"]['depth_camera'].to(demo_go2.device)
    obs_student = obs[:, :num_prop].clone()
    obs_student[:, 6:8] = 0
    depth_latent_and_yaw = demo_go2.depth_encoder(depth_camera, obs_student)
    depth_latent = depth_latent_and_yaw[:, :-2]
    yaw = depth_latent_and_yaw[:, -2:]
    obs[:, 6:8] = 1.5*yaw
    # 关键：这里调用policy，传入obs和depth_latent
    action = demo_go2.policy(obs, hist_encoding=True, scandots_latent=depth_latent)
```

---

### 5. ONNX模型导出时的输入定义

**文件**: `scripts/rsl_rl/exporter.py`

**行数**: 157-176

```python
def forward(self, x, scandots_latent):
    x[:,self._start : self._end] \
        = self.estimator(x[:,:self._num_prop])
    return self.actor(self.normalizer(x), hist_encoding=True, scandots_latent = scandots_latent )

def export(self, path, filename):
    self.to("cpu")
    obs = torch.zeros(1, self.actor.in_features)  # 753维
    scandots_latent = torch.zeros(1, 32)          # 32维
    torch.onnx.export(
        self,
        (obs, scandots_latent),  # 两个输入
        os.path.join(path, filename),
        export_params=True,
        opset_version=11,
        verbose=self.verbose,
        input_names=["obs","scandots_latent"],  # 输入名称
        output_names=["actions"],
        dynamic_axes={},
    )
```

**说明**：
- ONNX模型定义了两个输入：
  - `obs`: observation (753维)
  - `scandots_latent`: depth_latent (32维)
- 这与实际推理时的调用一致

---

### 6. 推理策略获取函数

**文件**: `scripts/rsl_rl/modules/on_policy_runner_with_extractor.py`

**行数**: 607-615

```python
def get_inference_depth_policy(self, device=None):
    """获取student策略的推理函数"""
    policy = self.alg.depth_actor.act_inference
    if device is not None:
        policy = lambda x, **kwargs: self.alg.depth_actor.act_inference(
            x.to(device), **kwargs
        )
    if self.obs_normalizer is not None:
        # 注意：这里只对obs进行归一化，scandots_latent不归一化
        policy = lambda x, **kwargs: self.alg.depth_actor.act_inference(
            self.obs_normalizer(x), **kwargs
        )
    return policy
```

**说明**：
- 返回的policy函数接收两个参数：
  - `x`: observation (会被归一化)
  - `**kwargs`: 包括`scandots_latent`和`hist_encoding`

---

## 输入总结

### Student Policy推理时的输入

1. **obs** (753维)
   - 类型: `torch.Tensor`
   - 形状: `(batch_size, 753)`
   - 内容: 完整的observation向量

2. **hist_encoding** (布尔值)
   - 类型: `bool`
   - 值: `True` (推理时总是True)
   - 作用: 启用历史编码

3. **scandots_latent** (32维)
   - 类型: `torch.Tensor`
   - 形状: `(batch_size, 32)`
   - 内容: 从depth_encoder得到的depth_latent
   - 可选: 如果为None，会使用obs中的scan部分通过scan_encoder编码

### 调用示例

```python
# 方式1: 直接调用
actions = policy(obs, hist_encoding=True, scandots_latent=depth_latent)

# 方式2: 使用act_inference
actions = policy.act_inference(obs, hist_encoding=True, scandots_latent=depth_latent)

# 方式3: 通过ONNX模型
actions = onnx_session.run(
    None,
    {
        "obs": obs.numpy(),
        "scandots_latent": depth_latent.numpy()
    }
)[0]
```

---

## 关键代码路径

```
推理调用链：
play.py/demo.py
  ↓
policy(obs, hist_encoding=True, scandots_latent=depth_latent)
  ↓
ActorCriticRMA.act_inference()
  ↓
Actor.forward(obs, hist_encoding, scandots_latent)
  ↓
处理输入并输出动作
```

---

## 注意事项

1. **obs的delta_yaw部分会被更新**：
   ```python
   obs[:, 6:8] = 1.5 * yaw  # 在调用policy之前更新
   ```

2. **depth_latent每5步更新一次**：
   ```python
   if env.unwrapped.common_step_counter % 5 == 0:
       # 更新depth_latent
   ```

3. **hist_encoding在推理时总是True**：
   - 使用历史编码模式
   - 从obs的末尾提取历史帧

4. **ONNX模型的输入顺序**：
   - 第一个输入: `obs` (753维)
   - 第二个输入: `scandots_latent` (32维)
