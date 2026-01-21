import os
import struct
import threading
import time
import numpy as np


class JoystickInterface:
    def __init__(
        self, device_path="/dev/input/js0", max_v_x=1.0, max_v_y=0.5, max_omega=1.0
    ):
        self.device_path = device_path
        self.running = True

        # 当前指令缓存 (线程安全)
        self.cmd_x = 0.0
        self.cmd_y = 0.0
        self.cmd_yaw = 0.0

        # 速度限制 (根据你的机器人能力调整)
        self.MAX_V_X = max_v_x  # m/s
        self.MAX_V_Y = max_v_y  # m/s
        self.MAX_OMEGA = max_omega  # rad/s

        # 摇杆原始数值范围
        self.JOY_MAX = 32767.0

        # 启动读取线程
        self.thread = threading.Thread(target=self._read_loop)
        self.thread.daemon = True  # 主程序退出时子线程自动结束
        self.thread.start()

    def _read_loop(self):
        """后台线程：持续读取二进制流"""
        if not os.path.exists(self.device_path):
            print(f"[Joystick] 错误: 未找到设备 {self.device_path}")
            self.running = False
            return

        print(f"[Joystick] 正在监听 {self.device_path}...")

        event_format = "IhBB"  # struct: time, value, type, number
        event_size = struct.calcsize(event_format)

        try:
            with open(self.device_path, "rb") as js_file:
                while self.running:
                    event_data = js_file.read(event_size)
                    if event_data:
                        time_evt, value, type_evt, number = struct.unpack(
                            event_format, event_data
                        )

                        # 过滤掉初始化信号 (0x80)
                        if type_evt & 0x80:
                            continue

                        # 处理轴事件 (Type 2 = Axis)
                        if type_evt == 0x02:
                            # 归一化到 -1.0 ~ 1.0
                            norm_val = value / self.JOY_MAX

                            # 死区处理 (防止漂移)
                            if abs(norm_val) < 0.1:
                                norm_val = 0.0

                            # === Xbox 映射 (根据实际手柄可能微调) ===
                            # Axis 1: 左摇杆上下 (Up是负数, Down是正数) -> 控制前进后退(x)
                            if number == 1:
                                self.cmd_x = -norm_val * self.MAX_V_X

                            # Axis 0: 左摇杆左右 (Left负, Right正) -> 控制左右平移(y)
                            # 机器人坐标系通常左为正(Y+)，所以需要反向
                            elif number == 0:
                                self.cmd_y = -norm_val * self.MAX_V_Y

                            # Axis 3: 右摇杆左右 -> 控制旋转(yaw)
                            # Left(负) -> Turn Left(正)
                            elif number == 3:
                                self.cmd_yaw = -norm_val * self.MAX_OMEGA

        except Exception as e:
            print(f"[Joystick] 读取错误: {e}")

    def get_command(self):
        """主循环调用的接口，返回 (vx, vy, dyaw)"""
        return self.cmd_x, self.cmd_y, self.cmd_yaw

    def stop(self):
        self.running = False
        self.thread.join()


if __name__ == "__main__":
    # 单独测试代码
    joy = JoystickInterface()
    try:
        while True:
            x, y, w = joy.get_command()
            print(f"\rCmd: X={x:.2f}, Y={y:.2f}, W={w:.2f}", end="")
            time.sleep(0.1)
    except KeyboardInterrupt:
        joy.stop()
