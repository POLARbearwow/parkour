# SPDX-License-Identifier: BSD-3-Clause
"""
Student策略的Sim2Sim实现
基于s2s_trot_joystick.py，但使用student策略的observation结构
包括depth camera输入
"""
import math
import numpy as np
import mujoco
import mujoco.viewer
from collections import deque
from scipy.spatial.transform import Rotation as R
from pathlib import Path
import onnxruntime as ort
import argparse
import cv2

import sys
sys.path.append(str(Path(__file__).parent.parent))
from joystick_interface import JoystickInterface

# ---------------------------------------------------------------------------- #
#                               Remapping Indices                              #
# ---------------------------------------------------------------------------- #

# 1. Sim (MuJoCo) -> Policy (Isaac Lab)
# MuJoCo 顺序: [LF_A, LF_F, LF_K, LR_A, LR_F, LR_K, RF_A, RF_F, RF_K, RR_A, RR_F, RR_K]
# Policy 顺序: [LF_A, LR_A, RF_A, RR_A, LF_F, LR_F, RF_F, RR_F, LF_K, LR_K, RF_K, RR_K]
sim2policy_indices = np.array(
    [
        0,
        3,
        6,
        9,  # HipA (LF, LR, RF, RR) -> Policy 0, 1, 2, 3
        1,
        4,
        7,
        10,  # HipF (LF, LR, RF, RR) -> Policy 4, 5, 6, 7
        2,
        5,
        8,
        11,  # Knee (LF, LR, RF, RR) -> Policy 8, 9, 10, 11
    ],
    dtype=np.int64,
)

# 2. Policy (Isaac Lab) -> Sim (MuJoCo)
policy2sim_indices = np.array(
    [
        0,
        4,
        8,  # LF Leg (HipA, HipF, Knee) -> Sim 0, 1, 2
        1,
        5,
        9,  # LR Leg (HipA, HipF, Knee) -> Sim 3, 4, 5
        2,
        6,
        10,  # RF Leg (HipA, HipF, Knee) -> Sim 6, 7, 8
        3,
        7,
        11,  # RR Leg (HipA, HipF, Knee) -> Sim 9, 10, 11
    ],
    dtype=np.int64,
)


# ---------------------------------------------------------------------------- #
#                               Configuration                                #
# ---------------------------------------------------------------------------- #


class StudentSim2simCfg:
    class sim_config:
        # 修改为你的 leggedrobot.xml 绝对路径或相对路径
        base_dir = Path(__file__).resolve().parent.parent.parent
        mujoco_model_path = (
            base_dir / "s2s" / "leggedrobot.xml"
        ).as_posix()
        plugin_lib_path = (
            base_dir / "lib" / "libsensor_ray.so"
        ).as_posix()

        sim_duration = 120.0
        dt = 0.005
        decimation = 4

    class robot_config:
        num_actions = 12
        # 注意：这里假设默认姿态全是0。如果不为0，需要确认这个数组是 Policy 顺序
        default_dof_pos = np.zeros(12, dtype=np.double)

        # PD 参数 (MuJoCo Sim 顺序，如果四条腿参数一样则没问题)
        kps = np.full(12, 25.0, dtype=np.double)
        kds = np.full(12, 0.5, dtype=np.double)
        tau_limit = np.array([17, 17, 25] * 4, dtype=np.double)  # LF, LR, RF, RR

    class normalization:
        class isaac_obs_scales:
            lin_vel = 1.0
            ang_vel = 0.25  # 注意：在Isaac Lab中是0.25
            projected_gravity = 1.0
            commands = 1.0
            joint_pos = 1.0
            joint_vel = 0.05  # 注意：在Isaac Lab中是0.05
            actions = 1.0

        clip_observations = 100.0
        clip_actions = 100.0

    class env:
        frame_stack = 10  # 历史长度
        num_single_obs = 53  # 单帧extreme_parkour_observations维度（不含历史）
        depth_image_size = (58, 87)  # depth camera图像尺寸
        depth_buffer_len = 2  # depth buffer长度
        depth_clipping_range = 5.0  # depth camera的最大距离

    class control:
        action_scale = 0.25


# ---------------------------------------------------------------------------- #
#                               Util Functions                                 #
# ---------------------------------------------------------------------------- #


def wrap_to_pi(angle):
    """将角度wrap到[-pi, pi]"""
    return ((angle + np.pi) % (2 * np.pi)) - np.pi


def get_extreme_parkour_obs_buf(data, cfg, parkour_state, action_history):
    """
    从 MuJoCo 数据中提取extreme_parkour_observations的obs_buf部分（53维）
    参考ExtremeParkourObservations的obs_buf构造
    """
    # 1. 读取原始 MuJoCo 数据 (Sim Order)
    q_sim = data.qpos[7:].astype(np.double)
    dq_sim = data.qvel[6:].astype(np.double)

    # 2. 【关键】重排为 Policy Order
    q_policy = q_sim[sim2policy_indices]
    dq_policy = dq_sim[sim2policy_indices]

    # MuJoCo Quat [w, x, y, z] -> Scipy [x, y, z, w]
    mj_quat = data.qpos[3:7]
    quat = np.array([mj_quat[1], mj_quat[2], mj_quat[3], mj_quat[0]])

    # 角速度 (Base Frame) - 需要转换到body frame
    omega_world = data.qvel[3:6].astype(np.double)
    r = R.from_quat(quat)
    omega_body = r.apply(omega_world, inverse=True)

    # 计算roll, pitch (IMU观测)
    roll, pitch, yaw = r.as_euler('xyz')
    imu_obs = np.array([wrap_to_pi(roll), wrap_to_pi(pitch)])

    # 获取parkour相关状态
    delta_yaw = parkour_state.get('delta_yaw', 0.0)
    delta_next_yaw = parkour_state.get('delta_next_yaw', 0.0)
    env_idx_tensor = parkour_state.get('env_idx_tensor', 1.0)  # 假设是parkour环境
    invert_env_idx_tensor = parkour_state.get('invert_env_idx_tensor', 0.0)

    # 获取commands
    commands = np.array([parkour_state.get('cmd_x', 0.0),
                        parkour_state.get('cmd_y', 0.0),
                        parkour_state.get('cmd_yaw', 0.0)])

    # 模拟contact forces（简化）
    contact_fill = np.zeros(4)  # LF, LR, RF, RR

    # 构造obs_buf (53维)
    scales = cfg.normalization.isaac_obs_scales
    obs_buf = np.concatenate([
        omega_body * scales.ang_vel,  # [3] 0~2
        imu_obs,  # [2] 3~4
        np.array([0.0]),  # [1] 5 (0 * delta_yaw)
        np.array([delta_yaw]),  # [1] 6
        np.array([delta_next_yaw]),  # [1] 7
        np.zeros(2),  # [2] 8~9 (0 * commands[:2])
        np.array([commands[2]]) * scales.commands,  # [1] 10 (commands yaw)
        np.array([env_idx_tensor]),  # [1] 11
        np.array([invert_env_idx_tensor]),  # [1] 12
        (q_policy - cfg.robot_config.default_dof_pos) * scales.joint_pos,  # [12] 13~24
        dq_policy * scales.joint_vel,  # [12] 25~36
        action_history * scales.actions,  # [12] 37~48
        contact_fill,  # [4] 49~52
    ])

    return obs_buf


def get_measured_heights(data, cfg):
    """获取measured heights (132维) - 简化版本"""
    # 实际应该从ray caster sensor获取
    # 这里返回零数组作为占位符
    return np.zeros(132, dtype=np.float32)


def get_priv_explicit(data, cfg):
    """获取priv_explicit (9维) - 简化版本"""
    # 实际应该从机器人状态获取
    # 返回零数组作为占位符
    return np.zeros(9, dtype=np.float32)


def get_priv_latent(data, cfg):
    """获取priv_latent (29维) - 简化版本"""
    # 实际应该从机器人参数获取
    # 返回零数组作为占位符
    return np.zeros(29, dtype=np.float32)


def get_depth_camera_obs(depth_image, cfg):
    """处理depth camera observation"""
    if depth_image is not None:
        # 处理depth图像
        depth_processed = process_depth_image(depth_image, cfg.env.depth_image_size, cfg)
        return depth_processed
    else:
        # 返回零数组
        return np.zeros(cfg.env.depth_image_size, dtype=np.float32)


def process_depth_image(depth_image, target_size, cfg):
    """
    处理depth图像，类似Isaac Lab的image_features处理
    1. crop (去掉底部2行，左右各4列)
    2. resize到target_size
    3. 归一化
    """
    h, w = target_size
    
    # 1. Crop: 去掉底部2行，左右各4列
    if depth_image.shape[0] > 2 and depth_image.shape[1] > 8:
        depth_cropped = depth_image[:-2, 4:-4]
    else:
        depth_cropped = depth_image

    # 2. Resize到target_size
    if depth_cropped.shape != target_size:
        depth_resized = cv2.resize(
            depth_cropped.astype(np.float32),
            (w, h),
            interpolation=cv2.INTER_LINEAR
        )
    else:
        depth_resized = depth_cropped.astype(np.float32)

    # 3. 归一化: (depth / clipping_range) - 0.5
    depth_normalized = (depth_resized / cfg.env.depth_clipping_range) - 0.5

    return depth_normalized


def get_delta_yaw_ok_obs(delta_yaw, threshold=0.6):
    """计算delta yaw是否ok"""
    return 1.0 if abs(delta_yaw) < threshold else 0.0


def construct_student_obs(obs_buf, measured_heights, priv_explicit, priv_latent,
                          hist_obs_buf):
    """
    构造student策略的observation（不含depth image）
    顺序：
    1. obs_buf (53维) - num_prop
    2. measured_heights (132维) - num_scan (会被depth_latent替换)
    3. priv_explicit (9维)
    4. priv_latent (29维)
    5. hist_obs_buf (10帧 * 53维 = 530维)
    总共: 53 + 132 + 9 + 29 + 530 = 753维
    
    注意：depth image通过单独的depth_encoder处理，得到depth_latent（32维）
    depth_latent会替换measured_heights（132维）中的scan部分
    """
    # 构造extreme_parkour_observations
    obs = np.concatenate([
        obs_buf,  # 53
        measured_heights,  # 132 (会被depth_latent替换)
        priv_explicit,  # 9
        priv_latent,  # 29
        hist_obs_buf.flatten(),  # 530 (10 * 53)
    ]).astype(np.float32)

    return obs


def pd_control(target_q, q, kp, target_dq, dq, kd, default_pos):
    """计算 PD 扭矩 (输入全部为 Sim Order)"""
    return (target_q - q) * kp + (target_dq - dq) * kd


def get_ray_caster_info(model, data, sensor_name):
    """从sensor_data_viewer.py复制的函数，获取ray caster信息"""
    data_ps = []
    sensor_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SENSOR, sensor_name)
    if sensor_id == -1:
        print(f"Sensor '{sensor_name}' not found")
        return 0, 0, data_ps
    sensor_plugin_id = model.sensor_plugin[sensor_id]
    state_idx = model.plugin_stateadr[sensor_plugin_id]
    state_num = model.plugin_statenum[sensor_plugin_id]
    for i in range(state_idx + 2, state_idx + state_num, 2):
        if i + 1 < len(data.plugin_state):
            data_ps.append((int(data.plugin_state[i]), int(data.plugin_state[i + 1])))
    h_ray_num = (
        int(data.plugin_state[state_idx]) if state_idx < len(data.plugin_state) else 0
    )
    v_ray_num = (
        int(data.plugin_state[state_idx + 1])
        if state_idx + 1 < len(data.plugin_state)
        else 0
    )
    return h_ray_num, v_ray_num, data_ps


# ---------------------------------------------------------------------------- #
#                                 Main Loop                                    #
# ---------------------------------------------------------------------------- #


def run_mujoco_student(policy_session, depth_encoder_session, cfg):
    # 初始化joystick
    joy = JoystickInterface(device_path="/dev/input/js0", max_v_x=2.0, max_v_y=1.0, max_omega=1.5)

    # 加载ray caster插件
    try:
        mujoco.mj_loadPluginLibrary(cfg.sim_config.plugin_lib_path)
        print(f"Loaded plugin from {cfg.sim_config.plugin_lib_path}")
    except Exception as e:
        print(f"Warning: Could not load plugin: {e}")
        print("Depth camera may not work properly")

    # 加载模型
    model = mujoco.MjModel.from_xml_path(cfg.sim_config.mujoco_model_path)
    print(f"Loaded model from {cfg.sim_config.mujoco_model_path}")

    # ================= terrain =================
    # 获取 hfield 的 ID
    hfield_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_HFIELD, "terrain")

    if hfield_id != -1:
        # 获取该 hfield 的内存地址和尺寸
        hfield_adr = model.hfield_adr[hfield_id]
        nrow = model.hfield_nrow[hfield_id]
        ncol = model.hfield_ncol[hfield_id]
        num_points = nrow * ncol

        # 生成随机高度数据
        random_heights = np.random.uniform(0, 0.6, num_points)

        # 将数据填入模型
        model.hfield_data[hfield_adr : hfield_adr + num_points] = random_heights

        print(f"Generated rough terrain with {num_points} points.")
    # ================= terrain =================

    model.opt.timestep = cfg.sim_config.dt
    data = mujoco.MjData(model)

    # 初始化关节位置 (Sim Order)
    data.qpos[7:] = cfg.robot_config.default_dof_pos
    mujoco.mj_step(model, data)

    with mujoco.viewer.launch_passive(model, data) as viewer:
        # --- 开启可视化选项 ---
        viewer.cam.distance = 3.0
        viewer.cam.azimuth = 90
        viewer.cam.elevation = -45
        viewer.cam.lookat[:] = np.array([0.0, -0.25, 0.824])

        # 状态变量初始化 (Policy Order)
        action_policy = np.zeros(cfg.robot_config.num_actions, dtype=np.double)
        target_q_sim = np.zeros(cfg.robot_config.num_actions, dtype=np.double)

        # 初始化observation历史 (obs_buf历史)
        hist_obs_buf = deque(maxlen=cfg.env.frame_stack)
        for _ in range(cfg.env.frame_stack):
            hist_obs_buf.append(np.zeros(cfg.env.num_single_obs, dtype=np.float32))

        # 初始化depth buffer
        depth_buffer = deque(maxlen=cfg.env.depth_buffer_len)
        for _ in range(cfg.env.depth_buffer_len):
            depth_buffer.append(np.zeros(cfg.env.depth_image_size, dtype=np.float32))

        # 模拟parkour状态
        parkour_state = {
            'delta_yaw': 0.0,
            'delta_next_yaw': 0.0,
            'env_idx_tensor': 1.0,
            'invert_env_idx_tensor': 0.0,
            'cmd_x': 0.0,
            'cmd_y': 0.0,
            'cmd_yaw': 0.0
        }

        count_lowlevel = 0
        cmd_x, cmd_y, cmd_yaw = 0.0, 0.0, 0.0
        
        # 初始化depth_latent和yaw
        depth_latent = np.zeros(32, dtype=np.float32)  # scan_encoder_dims[-1] = 32
        yaw = np.zeros(2, dtype=np.float32)

        while viewer.is_running():
            # 1. 获取物理数据
            obs_buf = get_extreme_parkour_obs_buf(data, cfg, parkour_state, action_policy)
            measured_heights = get_measured_heights(data, cfg)
            priv_explicit = get_priv_explicit(data, cfg)
            priv_latent = get_priv_latent(data, cfg)

            # 2. 获取depth camera数据
            depth_obs = None
            try:
                # 尝试从raycastercamera获取数据
                h_rays, v_rays, pairs = get_ray_caster_info(model, data, "raycastercamera")
                if pairs and len(pairs) > 0:
                    img = data.sensor("raycastercamera").data
                    # 获取第一对数据（正常图像）
                    depth_image_raw = np.array(
                        img[pairs[0][0]:pairs[0][0]+pairs[0][1]],
                        dtype=np.float32
                    ).reshape(v_rays, h_rays)
                    # 转换为深度值（假设数据范围是0-1，需要转换为实际深度）
                    # 这里需要根据实际的sensor数据格式调整
                    depth_obs = get_depth_camera_obs(depth_image_raw, cfg)
                else:
                    depth_obs = get_depth_camera_obs(None, cfg)
            except Exception as e:
                if count_lowlevel % 100 == 0:  # 每100次打印一次错误
                    print(f"\nWarning: Could not get depth camera data: {e}")
                depth_obs = get_depth_camera_obs(None, cfg)

            # 更新depth buffer（每5步更新一次，类似Isaac Lab）
            if count_lowlevel % 5 == 0:
                depth_buffer.append(depth_obs)

            # 3. 获取delta_yaw_ok
            delta_yaw_ok_obs = get_delta_yaw_ok_obs(parkour_state['delta_yaw'])

            # 4. 策略推理 (50Hz)
            if count_lowlevel % cfg.sim_config.decimation == 0:
                # 获取控制命令
                cmd_x, cmd_y, cmd_yaw = joy.get_command()
                parkour_state['cmd_x'] = cmd_x
                parkour_state['cmd_y'] = cmd_y
                parkour_state['cmd_yaw'] = cmd_yaw

                # 更新obs_buf以包含最新的commands
                obs_buf = get_extreme_parkour_obs_buf(data, cfg, parkour_state, action_policy)

                # 更新历史
                hist_obs_buf.append(obs_buf.copy())

                # 构造observation（753维，不含depth image）
                hist_obs_buf_array = np.array(list(hist_obs_buf))
                current_obs = construct_student_obs(
                    obs_buf,
                    measured_heights,
                    priv_explicit,
                    priv_latent,
                    hist_obs_buf_array
                )

                # 处理depth encoder（每5步更新一次）
                if count_lowlevel % 5 == 0:
                    try:
                        # 获取depth image（使用buffer的最后一帧）
                        if len(depth_buffer) >= 1:
                            depth_frame = depth_buffer[-1]  # 最后一帧
                        else:
                            depth_frame = np.zeros(cfg.env.depth_image_size, dtype=np.float32)
                        
                        # 准备depth encoder输入
                        # depth_image: (1, 87, 58) 或 (1, 58, 87) - 需要确认顺序
                        # proprioception: obs的前53维，但delta_yaw部分设为0
                        obs_student = current_obs[:53].copy()  # num_prop = 53
                        obs_student[6:8] = 0  # 将delta_yaw部分设为0
                        
                        # 调用depth encoder
                        depth_input_name = depth_encoder_session.get_inputs()[0].name
                        proprioception_input_name = depth_encoder_session.get_inputs()[1].name
                        
                        # 注意：depth_image的形状可能是(87, 58)或(58, 87)，需要根据实际模型调整
                        # 根据agent.yaml，depth_shape是(87, 58)，所以应该是(height, width)
                        depth_image_input = depth_frame.reshape(1, *depth_frame.shape)
                        proprioception_input = obs_student.reshape(1, -1)
                        
                        depth_latent_and_yaw = depth_encoder_session.run(
                            None,
                            {
                                depth_input_name: depth_image_input.astype(np.float32),
                                proprioception_input_name: proprioception_input.astype(np.float32)
                            }
                        )[0][0]  # shape: (depth_latent_dim + 2,)
                        
                        # 提取depth_latent和yaw
                        depth_latent = depth_latent_and_yaw[:-2]  # 32维
                        yaw = depth_latent_and_yaw[-2:]  # 2维
                        
                    except Exception as e:
                        if count_lowlevel % 100 == 0:
                            print(f"\nError in depth encoder inference: {e}")
                        # 使用零数组作为fallback
                        depth_latent = np.zeros(32, dtype=np.float32)  # scan_encoder_dims[-1] = 32
                        yaw = np.zeros(2, dtype=np.float32)
                
                # 用yaw更新obs中的delta_yaw部分（类似Isaac Lab的obs[:, 6:8] = 1.5*yaw）
                current_obs[6:8] = 1.5 * yaw

                current_obs = np.clip(
                    current_obs,
                    -cfg.normalization.clip_observations,
                    cfg.normalization.clip_observations,
                )

                # 推理policy
                try:
                    obs_input_name = policy_session.get_inputs()[0].name
                    scandots_latent_input_name = policy_session.get_inputs()[1].name
                    
                    raw_action = policy_session.run(
                        None,
                        {
                            obs_input_name: current_obs[None, :].astype(np.float32),
                            scandots_latent_input_name: depth_latent[None, :].astype(np.float32)
                        }
                    )[0][0]

                    # 处理输出 (Policy Order)
                    action_policy = np.clip(
                        raw_action,
                        -cfg.normalization.clip_actions,
                        cfg.normalization.clip_actions,
                    )

                    # 5. 【关键】Action 重排 Policy -> Sim
                    action_sim = action_policy[policy2sim_indices]

                    # 计算 Sim 端的目标位置 (绝对位置)
                    target_q_sim = (
                        action_sim * cfg.control.action_scale
                        + cfg.robot_config.default_dof_pos
                    )
                except Exception as e:
                    print(f"\nError in policy inference: {e}")
                    # 使用零动作作为fallback
                    action_policy = np.zeros(cfg.robot_config.num_actions, dtype=np.double)
                    target_q_sim = cfg.robot_config.default_dof_pos

            # 6. PD 控制 (Sim Order)
            q_sim_raw = data.qpos[7:]
            dq_sim_raw = data.qvel[6:]

            tau = pd_control(
                target_q_sim,  # Sim Order
                q_sim_raw,  # Sim Order
                cfg.robot_config.kps,  # Sim Order
                np.zeros_like(dq_sim_raw),
                dq_sim_raw,  # Sim Order
                cfg.robot_config.kds,  # Sim Order
                0.0,
            )
            tau = np.clip(tau, -cfg.robot_config.tau_limit, cfg.robot_config.tau_limit)

            data.ctrl[:] = tau
            mujoco.mj_step(model, data)

            viewer.sync()

            # --- 实时状态打印 ---
            if count_lowlevel % 10 == 0:  # 每10次循环打印一次
                print(
                    f"\r"
                    f"Cmd: x={cmd_x:.2f} y={cmd_y:.2f} yaw={cmd_yaw:.2f} | "
                    f"Delta yaw: {parkour_state['delta_yaw']:.2f} | "
                    f"Delta yaw ok: {delta_yaw_ok_obs:.1f} | "
                    f"Obs dim: {current_obs.shape[0] if 'current_obs' in locals() else 0}"
                    f"\033[K",
                    end="",
                    flush=True,
                )
            # --------------------------

            count_lowlevel += 1

    joy.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Student策略Sim2Sim实现")
    parser.add_argument(
        "--policy_model", type=str, required=True, help="Path to ONNX policy model (policy.onnx)"
    )
    parser.add_argument(
        "--depth_model", type=str, required=True, help="Path to ONNX depth encoder model (depth_latest.onnx)"
    )
    args = parser.parse_args()

    try:
        policy_session = ort.InferenceSession(args.policy_model)
        print("ONNX policy model loaded successfully.")
        print(f"Policy input names: {[inp.name for inp in policy_session.get_inputs()]}")
        print(f"Policy input shapes: {[inp.shape for inp in policy_session.get_inputs()]}")
        print(f"Policy output shape: {policy_session.get_outputs()[0].shape}")
    except Exception as e:
        print(f"Error loading policy ONNX model: {e}")
        exit(1)

    try:
        depth_encoder_session = ort.InferenceSession(args.depth_model)
        print("ONNX depth encoder model loaded successfully.")
        print(f"Depth encoder input names: {[inp.name for inp in depth_encoder_session.get_inputs()]}")
        print(f"Depth encoder input shapes: {[inp.shape for inp in depth_encoder_session.get_inputs()]}")
        print(f"Depth encoder output shape: {depth_encoder_session.get_outputs()[0].shape}")
    except Exception as e:
        print(f"Error loading depth encoder ONNX model: {e}")
        exit(1)

    run_mujoco_student(policy_session, depth_encoder_session, StudentSim2simCfg())