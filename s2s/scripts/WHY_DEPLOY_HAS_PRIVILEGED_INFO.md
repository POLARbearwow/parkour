# 为什么Deploy网络还有Privileged Information？

## 核心答案

虽然deploy的网络**结构上**仍然包含privileged information的位置，但在**实际运行时**，这些位置会被**Estimator（估计器）**的输出替换，而不是使用真实的privileged information。

## 关键机制

### 1. Estimator的作用

**Estimator**是一个神经网络，用于从**可观测的状态**（proprioception）**估计**privileged information。

```
训练时：
  Proprioception (53维) → Estimator → 估计的Privileged Info (9维)
  
  损失函数：||估计值 - 真实值||²
```

### 2. Deploy时的处理流程

**文件**: `scripts/rsl_rl/exporter.py`

**行数**: 157-160

```python
def forward(self, x, scandots_latent):
    # 关键：用estimator的输出替换observation中的priv_explicit部分
    x[:,self._start : self._end] \
        = self.estimator(x[:,:self._num_prop])
    return self.actor(self.normalizer(x), hist_encoding=True, scandots_latent = scandots_latent )
```

**说明**：
- `self._start` = `num_prop + num_scan` = 53 + 132 = 185
- `self._end` = `self._start + num_priv_explicit` = 185 + 9 = 194
- 这个范围是`priv_explicit`在observation中的位置
- **在输入actor之前，这个位置被estimator的输出替换**

### 3. Priv_Latent的处理

对于`priv_latent`（29维），处理方式不同：

**文件**: `scripts/rsl_rl/modules/actor_critic_with_encoder.py`

**行数**: 105-108

```python
if hist_encoding:
    latent = self.infer_hist_latent(obs)  # 从历史帧推断
else:
    latent = self.infer_priv_latent(obs)  # 使用真实的priv_latent
```

**在deploy时**：
- `hist_encoding=True`（总是True）
- 使用`infer_hist_latent`，从**历史帧**中推断latent
- **不使用真实的priv_latent**

### 4. 完整的Deploy流程

```
实机观测 (可获取的信息)
  ↓
构造Observation (753维)
  ├─ num_prop (53维): 真实值 ✓
  ├─ num_scan (132维): 占位符（会被depth_latent替换）
  ├─ num_priv_explicit (9维): ❌ 实机无法获取
  ├─ num_priv_latent (29维): ❌ 实机无法获取
  └─ num_hist (530维): 历史帧
  ↓
Estimator处理
  ├─ 输入: obs[:53] (proprioception)
  └─ 输出: 估计的priv_explicit (9维)
  ↓
替换Observation
  ├─ obs[185:194] = estimator(obs[:53])  # 替换priv_explicit
  └─ obs中的priv_latent部分会被忽略（使用hist_encoding）
  ↓
Actor处理
  ├─ 提取priv_explicit: obs[185:194] (估计值)
  ├─ 提取priv_latent: 从历史帧推断（不使用obs中的值）
  └─ 输出动作
```

## 为什么结构上还保留Privileged Information？

### 1. 保持网络结构一致性

- Actor网络在训练时接收完整的observation（包含privileged information）
- 如果改变网络结构，需要重新训练
- 保持结构不变，只需要在输入时替换值

### 2. 使用Estimator估计

- Estimator在训练时学习从proprioception估计privileged information
- 在deploy时，用estimator的输出替换真实的privileged information
- 这样网络结构不变，但输入的是估计值

### 3. 历史编码替代Priv_Latent

- 对于priv_latent，使用历史编码（hist_encoding）从历史帧推断
- 不需要真实的priv_latent值
- 这是RMA（Recurrent Memory Augmentation）方法的核心

## 代码证据

### 1. Estimator的定义

**文件**: `scripts/rsl_rl/modules/feature_extractors/estimator.py`

```python
class DefaultEstimator(nn.Module):
    def __init__(self, num_prop, num_priv_explicit, ...):
        # 输入：num_prop (53维)
        # 输出：num_priv_explicit (9维)
        self.estimator = nn.Sequential(...)
    
    def forward(self, input):
        return self.estimator(input)  # 从proprioception估计privileged info
```

### 2. Estimator的训练

**文件**: `scripts/rsl_rl/modules/ppo_with_extractor.py`

**行数**: 191-196

```python
# Estimator训练
priv_states_predicted = self.estimator(obs_batch[:, :self.num_prop])
estimator_loss = (priv_states_predicted - obs_batch[:, self.num_prop+self.num_scan:self.num_prop+self.num_scan+self.priv_states_dim]).pow(2).mean()
# 损失：估计值 vs 真实值
```

### 3. Deploy时的使用

**文件**: `scripts/rsl_rl/exporter.py`

**行数**: 157-160

```python
def forward(self, x, scandots_latent):
    # 在输入actor之前，用estimator替换priv_explicit
    x[:,self._start : self._end] = self.estimator(x[:,:self._num_prop])
    return self.actor(self.normalizer(x), hist_encoding=True, scandots_latent = scandots_latent )
```

## 实际部署时的输入

虽然observation结构上包含privileged information的位置，但实际输入时：

1. **priv_explicit (9维)**：
   - 位置：obs[185:194]
   - 值：`estimator(obs[:53])`的输出（估计值）
   - **不是真实的privileged information**

2. **priv_latent (29维)**：
   - 位置：obs[194:223]
   - 值：**不被使用**
   - Actor使用`infer_hist_latent`从历史帧推断

3. **历史帧**：
   - 位置：obs[-530:]
   - 值：真实的10帧历史obs_buf
   - 用于推断priv_latent

## 总结

### 为什么结构上还有Privileged Information？

1. **保持网络结构不变**：避免重新训练
2. **使用Estimator估计**：从可观测状态估计privileged information
3. **使用历史编码**：从历史帧推断priv_latent，而不是使用真实值

### 实际运行时

- **priv_explicit**: 被estimator的输出替换（估计值）
- **priv_latent**: 从历史帧推断（不使用obs中的值）
- **网络结构**: 保持不变，但输入的是估计值，不是真实值

### 类比

就像：
- **训练时**：给网络看完整的"答案"（privileged information）
- **部署时**：网络自己"猜答案"（estimator估计），但网络结构不变

这样既保持了网络性能，又能在实机上运行（因为不需要真实的privileged information）。
