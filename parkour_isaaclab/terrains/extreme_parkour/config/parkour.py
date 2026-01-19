from parkour_isaaclab.terrains.parkour_terrain_generator_cfg import (
    ParkourTerrainGeneratorCfg,
)
from parkour_isaaclab.terrains.extreme_parkour import *

EXTREME_PARKOUR_TERRAINS_CFG = ParkourTerrainGeneratorCfg(
    size=(16.0, 4.0),
    border_width=20.0,
    num_rows=10,
    num_cols=40,
    horizontal_scale=0.08,  ## original scale is 0.05, But Computing issue in IsaacLab see this issue in https://github.com/isaac-sim/IsaacLab/issues/2187
    vertical_scale=0.005,
    slope_threshold=1.5,
    difficulty_range=(0.0, 1.0),
    use_cache=False,
    curriculum=True,
    sub_terrains={
        "parkour_gap": ExtremeParkourGapTerrainCfg(
            proportion=0.2,
            apply_roughness=True,
            x_range=(0.8, 1.5),
            half_valid_width=(0.6, 1.2),
            gap_size="0.1 + 0.7*difficulty",
        ),
        "parkour_hurdle": ExtremeParkourHurdleTerrainCfg(
            proportion=0.15,
            apply_roughness=True,
            x_range=(1.2, 2.2),  # 跨栏之间的纵向距离范围 (米)
            half_valid_width=(
                0.4,
                0.8,
            ),  # 通道的半宽度 (米)，实际宽度 = 2 * half_valid_width
            # hurdle_height_range 设置跨栏高度范围（单位：米）
            # 格式: "min_height, max_height"，可以使用 difficulty 变量
            # 当前设置：
            #   - 难度 0: 0.1m ~ 0.15m (10cm ~ 15cm)
            #   - 难度 1: 0.2m ~ 0.4m (20cm ~ 40cm)
            # 示例：如果要设置固定高度 0.3m，使用 "0.3, 0.3"
            # 示例：如果要设置随难度线性增加，使用 "0.1 + 0.2*difficulty, 0.15 + 0.25*difficulty"
            hurdle_height_range="0.1+0.1*difficulty, 0.15+0.15*difficulty",
        ),
        "parkour_flat": ExtremeParkourHurdleTerrainCfg(
            proportion=0.1,
            apply_roughness=True,
            apply_flat=True,
            x_range=(1.2, 2.2),
            half_valid_width=(0.4, 0.8),
            hurdle_height_range="0.1+0.1*difficulty, 0.15+0.15*difficulty",
        ),
        "parkour_step": ExtremeParkourStepTerrainCfg(
            proportion=0.2,
            apply_roughness=True,
            x_range=(0.8, 1.5),  # 每个台阶面的宽度范围：最小0.8m，最大1.5m
            half_valid_width=(
                0.5,
                1.0,
            ),  # 楼梯通道的半宽度：0.5-1.0m（实际宽度1.0-2.0m）
            step_height="0.1 + 0.35*difficulty",
        ),
        "parkour": ExtremeParkourTerrainCfg(
            proportion=0.15,
            apply_roughness=True,
            x_range="-0.1, 0.1+0.3*difficulty",
            y_range="0.2, 0.3+0.1*difficulty",
            stone_len="0.9 - 0.3*difficulty, 1 - 0.2*difficulty",
            incline_height="0.25*difficulty",
            last_incline_height="incline_height + 0.1 - 0.1*difficulty",
        ),
        "parkour_slope": ExtremeParkourSlopeTerrainCfg(
            proportion=0.2,  # 斜坡地形占比 20%
            apply_roughness=True,  # 保持粗糙表面以增加挑战
            # 斜率范围（沿 y 方向的高度变化，单位：m/m，即米高度/米宽度）
            # 斜率转换为角度：angle = arctan(slope) * 180 / π
            # 当前设置（增加后的斜率）：
            #   - 难度 0: ±0.25 (约 ±14度)
            #   - 难度 1: ±0.5 (约 ±26.6度)
            # 示例：如果要更陡的斜坡，可以设置为 "-0.3 - 0.2 * difficulty, 0.3 + 0.2 * difficulty"
            slope_range="-0.25 - 0.25 * difficulty, 0.25 + 0.25 * difficulty",
            # 每一段斜坡在 x 方向（机器人行走方向）的长度范围（单位：米）
            # 难度越高，段长略增加，让机器人有更多时间适应斜坡
            segment_width_range="1.0 + 0.3 * difficulty, 2.0 + 0.5 * difficulty",
        ),
        "parkour_demo": ExtremeParkourDemoTerrainCfg(
            proportion=0.0,
            apply_roughness=True,
        ),
    },
)
