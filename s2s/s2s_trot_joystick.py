# SPDX-License-Identifier: BSD-3-Clause
import math
import numpy as np
import mujoco
import mujoco.viewer
from collections import deque
from scipy.spatial.transform import Rotation as R
from pathlib import Path
import onnxruntime as ort
import argparse
from pynput import keyboard

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
#                                 Control Input                                #
# ---------------------------------------------------------------------------- #

# ---------------------------------------------------------------------------- #
#                                 Configuration                                #
# ---------------------------------------------------------------------------- #


class Sim2simCfg:
    class sim_config:
        # 修改为你的 leggedrobot.xml 绝对路径或相对路径
        base_dir = Path(__file__).resolve().parent.parent
        mujoco_model_path = (
            base_dir / "assets" / "ares" / "a1" / "leggedrobot.xml"
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
            ang_vel = 1.0
            projected_gravity = 1.0
            commands = 1.0
            joint_pos = 1.0
            joint_vel = 1.0
            actions = 1.0

        clip_observations = 100.0
        clip_actions = 100.0

    class env:
        frame_stack = 10  # 历史长度
        num_single_obs = 45  # 单帧维度

    class control:
        action_scale = 0.25


# ---------------------------------------------------------------------------- #
#                               Util Functions                                 #
# ---------------------------------------------------------------------------- #


def get_gravity_orientation(quat):
    """计算重力在基座坐标系下的投影 (Isaac Lab 标准)"""
    r = R.from_quat(quat)  # [x, y, z, w]
    gravity_vec = np.array([0.0, 0.0, -1.0])
    return r.apply(gravity_vec, inverse=True)


def get_obs(data):
    """从 MuJoCo 数据中提取原始观测值，并映射到 Policy 顺序"""
    # 1. 读取原始 MuJoCo 数据 (Sim Order)
    q_sim = data.qpos[7:].astype(np.double)
    dq_sim = data.qvel[6:].astype(np.double)

    # 2. 【关键】重排为 Policy Order
    q_policy = q_sim[sim2policy_indices]
    dq_policy = dq_sim[sim2policy_indices]

    # MuJoCo Quat [w, x, y, z] -> Scipy [x, y, z, w]
    mj_quat = data.qpos[3:7]
    quat = np.array([mj_quat[1], mj_quat[2], mj_quat[3], mj_quat[0]])

    # 角速度 (Base Frame)
    omega = data.sensor("angular-velocity").data.astype(np.double)

    return q_policy, dq_policy, quat, omega


def pd_control(target_q, q, kp, target_dq, dq, kd, default_pos):
    """计算 PD 扭矩 (输入全部为 Sim Order)"""
    # 注意：这里的 target_q 已经是通过 default_pos 还原后的绝对位置
    return (target_q - q) * kp + (target_dq - dq) * kd


# ---------------------------------------------------------------------------- #
#                                 Main Loop                                    #
# ---------------------------------------------------------------------------- #


def run_mujoco(onnx_session, cfg):
    # 初始化键盘监听
    # cmd = Command()
    # listener = keyboard.Listener(on_press=cmd.on_press)
    # listener.start()
    joy = JoystickInterface(device_path="/dev/input/js0", max_v_x=2.0, max_v_y=1.0, max_omega=1.5)

    # 加载模型
    model = mujoco.MjModel.from_xml_path(cfg.sim_config.mujoco_model_path)
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
        # 注意：
        # 1. MuJoCo 的 hfield 数据范围通常是 [0, 1]
        # 2. 实际高度 = 数据值 * XML中size的第3个参数(0.5)
        # 3. 这里设置 0.0 ~ 0.2，意味着最大高度约 0.1米 (10cm)
        #    如果地形太高，机器人可能会卡死或翻倒，请根据效果调整这个 0.2
        import numpy as np

        random_heights = np.random.uniform(0, 0.6, num_points)

        # (可选) 如果觉得地形太尖锐，可以用 scipy 进行平滑
        # from scipy.ndimage import gaussian_filter
        # random_heights = gaussian_filter(random_heights.reshape(nrow, ncol), sigma=1.0).flatten()

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
        # viewer.opt.flags[mujoco.mjtVisFlag.mjVIS_CONTACTFORCE] = 1
        viewer.cam.distance = 3.0
        viewer.cam.azimuth = 90
        viewer.cam.elevation = -45
        viewer.cam.lookat[:] = np.array([0.0, -0.25, 0.824])

        # 状态变量初始化 (Policy Order)
        action_policy = np.zeros(cfg.robot_config.num_actions, dtype=np.double)
        target_q_sim = np.zeros(cfg.robot_config.num_actions, dtype=np.double)

        hist_obs = deque(maxlen=cfg.env.frame_stack)
        for _ in range(cfg.env.frame_stack):
            hist_obs.append(np.zeros(cfg.env.num_single_obs, dtype=np.float32))

        count_lowlevel = 0
        scales = cfg.normalization.isaac_obs_scales

        while viewer.is_running():

            # 1. 获取物理数据 (已转为 Policy Order)
            q_policy, dq_policy, quat, omega = get_obs(data)

            # --- [新增] 实时速度计算 (用于显示) ---
            # data.qvel 的前3位是世界坐标系线速度
            vel_world = data.qvel[:3]
            r_temp = R.from_quat(quat)
            # 旋转到基座坐标系：Real Body Velocity
            vel_body = r_temp.apply(vel_world, inverse=True)
            # -------------------------------------

            # 2. 策略推理 (50Hz)
            if count_lowlevel % cfg.sim_config.decimation == 0:
                obs_list = []
                # (1) 角速度
                obs_list.append(omega * scales.ang_vel)
                # (2) 重力投影
                obs_list.append(
                    get_gravity_orientation(quat) * scales.projected_gravity
                )

                cmd_x, cmd_y, cmd_yaw = joy.get_command()
                current_cmd = np.array([cmd_x, cmd_y, cmd_yaw], dtype=np.double)

                obs_list.append(current_cmd * scales.commands)
                # (4) 关节位置 (Policy Order)
                dof_pos_rel = q_policy - cfg.robot_config.default_dof_pos
                obs_list.append(dof_pos_rel * scales.joint_pos)
                # (5) 关节速度 (Policy Order)
                obs_list.append(dq_policy * scales.joint_vel)
                # (6) 上一帧动作 (Policy Order)
                obs_list.append(action_policy * scales.actions)

                # 构造 Observation
                current_obs = np.concatenate(obs_list).astype(np.float32)
                current_obs = np.clip(
                    current_obs,
                    -cfg.normalization.clip_observations,
                    cfg.normalization.clip_observations,
                )
                hist_obs.append(current_obs)

                # 推理
                policy_input = np.concatenate(hist_obs)[None, :]
                input_name = onnx_session.get_inputs()[0].name
                raw_action = onnx_session.run(None, {input_name: policy_input})[0][0]

                # 处理输出 (Policy Order)
                action_policy = np.clip(
                    raw_action,
                    -cfg.normalization.clip_actions,
                    cfg.normalization.clip_actions,
                )

                # 3. 【关键】Action 重排 Policy -> Sim
                action_sim = action_policy[policy2sim_indices]

                # 计算 Sim 端的目标位置 (绝对位置)
                target_q_sim = (
                    action_sim * cfg.control.action_scale
                    + cfg.robot_config.default_dof_pos
                )

            # 4. PD 控制 (Sim Order)
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

            # --- [新增] 实时状态打印 ---
            # 降低打印频率
            if count_lowlevel % 10 == 0:  # 每10次循环打印一次
                print(
                    f"\r"
                    f"Cmd: x={cmd_x:.2f} y={cmd_y:.2f} yaw={cmd_yaw:.2f} | "
                    f"Real(Body): x={vel_body[0]:.2f} y={vel_body[1]:.2f} z={vel_body[2]:.2f}"
                    f"\033[K",  
                    end="",
                    flush=True,
                )
            # --------------------------

            count_lowlevel += 1

    joy.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--load_model", type=str, required=True, help="Path to ONNX model"
    )
    args = parser.parse_args()

    try:
        ort_session = ort.InferenceSession(args.load_model)
        print("ONNX model loaded successfully.")
    except Exception as e:
        print(f"Error loading ONNX model: {e}")
        exit()

    run_mujoco(ort_session, Sim2simCfg())
