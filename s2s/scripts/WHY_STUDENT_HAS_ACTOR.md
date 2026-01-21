# 为什么Student策略还有Actor？

## 核心原因

Student策略使用**Actor-Critic架构**，因为它需要通过**PPO（Proximal Policy Optimization）算法**进行训练。PPO是一种Actor-Critic方法，需要同时有Actor和Critic两个组件。

## 详细解释

### 1. Student策略的训练方法

Student策略不是简单的模仿学习，而是通过**知识蒸馏（Knowledge Distillation）+ 强化学习**的方式训练：

```
┌─────────────────────────────────────────────────────────┐
│ Teacher策略（已训练好）                                    │
│ - 使用privileged信息（完整状态）                           │
│ - 输出：actions_teacher                                   │
└─────────────────────────────────────────────────────────┘
                    ↓ 知识蒸馏
┌─────────────────────────────────────────────────────────┐
│ Student策略（正在训练）                                   │
│ - 使用depth camera（受限观测）                            │
│ - 输出：actions_student                                   │
│ - 通过PPO算法优化，同时模仿Teacher                        │
└─────────────────────────────────────────────────────────┘
```

### 2. Actor-Critic架构的必要性

#### Actor（策略网络）
- **作用**：根据当前观测输出动作
- **输入**：observation (753维) + depth_latent (32维)
- **输出**：动作分布（均值 + 标准差）或确定性动作
- **用途**：
  - 在训练时：与环境交互，收集经验
  - 在推理时：输出最终动作

#### Critic（价值网络）
- **作用**：评估当前状态的价值（V值）
- **输入**：critic observation（通常是完整的observation）
- **输出**：状态价值（标量）
- **用途**：
  - 计算优势函数（Advantage Function）
  - 用于PPO算法的策略更新

### 3. PPO算法需要Actor-Critic

PPO算法的更新公式：

```
L^CLIP(θ) = E[min(
    r(θ) * A,                    # 未裁剪项
    clip(r(θ), 1-ε, 1+ε) * A    # 裁剪项
)]
```

其中：
- `r(θ)` = π_θ(a|s) / π_θ_old(a|s) - 策略比率
- `A` = Q(s,a) - V(s) - 优势函数
- `V(s)` 需要Critic来计算

**因此，PPO算法必须同时有：**
1. **Actor**：计算策略 π_θ(a|s)
2. **Critic**：计算状态价值 V(s)

### 4. Student策略的训练流程

从代码中可以看到，Student策略的训练分为两个阶段：

#### 阶段1：Depth Encoder预训练
```python
# 训练depth_encoder和depth_actor
actions_teacher = policy.act_inference(obs, ...)  # Teacher的动作
actions_student = depth_actor(obs, scandots_latent=depth_latent)  # Student的动作

# 损失函数：让Student的动作接近Teacher的动作
loss = ||actions_teacher - actions_student||
```

#### 阶段2：PPO强化学习训练
```python
# 使用PPO算法训练
# Actor: 输出动作
actions = policy.act(obs, ...)

# Critic: 评估状态价值
values = policy.evaluate(critic_obs)

# PPO更新
ppo_loss = compute_ppo_loss(actions, values, advantages, ...)
```

### 5. 为什么不能只用Actor？

如果只用Actor（纯策略网络），可以：
- ✅ 进行模仿学习（Behavior Cloning）
- ✅ 输出动作

但无法：
- ❌ 使用PPO等Actor-Critic算法
- ❌ 计算优势函数（需要Critic的V值）
- ❌ 进行策略梯度优化（需要价值估计）

### 6. Actor-Critic架构的优势

对于Student策略，Actor-Critic架构提供了：

1. **更好的学习效率**：
   - Critic提供价值估计，帮助Actor更好地学习
   - 比纯策略方法（如Behavior Cloning）更高效

2. **稳定的训练**：
   - PPO算法通过裁剪机制保证训练稳定性
   - Critic的价值估计帮助减少方差

3. **持续优化**：
   - 不仅模仿Teacher，还能通过强化学习继续优化
   - 适应新的环境和任务

### 7. 代码中的体现

从`actor_critic_with_encoder.py`可以看到：

```python
class ActorCriticRMA(nn.Module):
    def __init__(self, ...):
        # Actor: 输出动作
        self.actor: Actor = actor_class(...)
        
        # Critic: 评估状态价值
        self.critic = nn.Sequential(...)
    
    def act(self, observations, ...):
        # Actor输出动作分布
        self.update_distribution(observations, ...)
        return self.distribution.sample()
    
    def evaluate(self, critic_observations, ...):
        # Critic输出状态价值
        return self.critic(critic_observations)
```

### 8. 推理时只使用Actor

虽然训练时需要Actor和Critic，但在**推理时（部署时）只需要Actor**：

```python
# 推理时
actions = policy.act_inference(obs, hist_encoding=True, scandots_latent=depth_latent)
# 只使用Actor，不需要Critic
```

这就是为什么导出的ONNX模型（`policy.onnx`）只包含Actor部分，不包含Critic。

## 总结

Student策略有Actor的原因：

1. **训练需要**：PPO算法是Actor-Critic方法，必须同时有Actor和Critic
2. **学习方式**：通过知识蒸馏 + 强化学习训练，需要价值估计
3. **架构设计**：Actor-Critic架构提供更好的学习效率和稳定性
4. **推理简化**：虽然训练时需要两者，但推理时只需要Actor

**类比**：
- **Actor** = 驾驶员（决定怎么开车）
- **Critic** = 教练（评估驾驶表现，帮助改进）
- 训练时需要两者配合，但实际开车时只需要驾驶员（Actor）
