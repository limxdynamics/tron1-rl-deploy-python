<p align="center">
  <img src="doc/banner.png" alt="tron1-rl-deploy-python：本仓库可部署 RL 策略的点足、足板、轮足 TRON1" width="100%">
</p>

<p align="center">
  <a href="README.md">English</a> | <b>中文</b>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-2f6feb" alt="License: Apache-2.0"></a>
  <img src="https://img.shields.io/badge/Python-3-2f6feb" alt="Python 3">
  <img src="https://img.shields.io/badge/ONNX%20Runtime-CPU-2f6feb" alt="ONNX Runtime">
  <img src="https://img.shields.io/badge/simulator-MuJoCo-2f6feb" alt="MuJoCo">
  <img src="https://img.shields.io/badge/ROS-not%20required-2f6feb" alt="ROS not required">
</p>

# tron1-rl-deploy-python

> **TRON1 开源生态的一部分。** TRON1 全部开源仓库和上手路线：[TRON1 开源生态](https://github.com/limxdynamics/tron1-rl-isaacgym/blob/master/README_cn.md#tron1-开源生态)。

用 Python 在 TRON1 双足机器人上部署强化学习运动策略，支持点足（`PF_*`）、足板（`SF_*`）和轮足（`WF_*`）。`main.py` 用 `onnxruntime` 加载 ONNX 策略和历史编码器，通过 LimX 底层 SDK 下发关节目标，既可对接 [tron1-mujoco-sim](https://github.com/limxdynamics/tron1-mujoco-sim) 仿真器，也可直接驱动真机。

## 亮点

- **十种机型，一个入口。** `ROBOT_TYPE` 选择机型，前缀 `PF_` / `SF_` / `WF_` 决定使用点足、足板还是轮足控制器。
- **Isaac Gym 和 Isaac Lab 策略都有。** 每个机型都附带两套策略，用 `RL_TYPE=isaacgym` 或 `RL_TYPE=isaaclab` 选择。
- **仿真和真机同一条命令。** 不带参数连接本机仿真；`python main.py <robot-ip>` 驱动真机。
- **纯 Python。** 依赖 NumPy、PyYAML、SciPy 和 CPU 版 ONNX Runtime，不需要 ROS，不需要 GPU。

## 支持的机型

| | 类型 | `ROBOT_TYPE` | 关节数 / 策略动作数 |
|:-:|---|---|:-:|
| <img src="doc/model_pf.png" width="260"> | 点足 | `PF_TRON1A`、`PF_TRON1B`、`PF_P441A`、`PF_P441B`、`PF_P441C`、`PF_P441C2` | 6 / 6 |
| <img src="doc/model_sf.png" width="260"> | 足板 | `SF_TRON1A`、`SF_TRON1B` | 8 / 8 |
| <img src="doc/model_wf.png" width="260"> | 轮足 | `WF_TRON1A`、`WF_TRON1B` | 8 / 8 |

`controllers/model/` 下每个机型目录包含 `params.yaml`，以及 `policy/$RL_TYPE/policy.onnx` 和 `policy/$RL_TYPE/encoder.onnx`。控制循环 500 Hz，策略推理 50 Hz（`loop_frequency: 500`、`decimation: 10`）。

## 工作原理

<p align="center">
  <img src="doc/sim2real_zh.png" alt="同一份 ONNX 策略：默认驱动 MuJoCo 中的 TRON1，传入机器人 IP 后驱动真机" width="100%">
</p>

<p align="center">
  <img src="doc/simulator.gif" alt="TRON1 在 tron1-mujoco-sim 中由本控制器驱动行走" width="400">
</p>

## 快速开始

Linux x86_64 或 aarch64，Python 3，仅用 CPU。以下命令在同时包含两个克隆的目录下执行。

**1. 克隆本仓库和仿真器。** 子模块带 SDK、机器人描述文件和虚拟遥控器。

```bash
git clone --recurse-submodules https://github.com/limxdynamics/tron1-rl-deploy-python.git
git clone --recurse-submodules https://github.com/limxdynamics/tron1-mujoco-sim.git
```

**2. 安装运动控制开发库**，wheel 在 `limxsdk-lowlevel` 子模块里；如果克隆时没带 `--recurse-submodules`，先执行 `git submodule update --init`：

```bash
# Linux x86_64
pip install tron1-rl-deploy-python/limxsdk-lowlevel/python3/amd64/limxsdk-*.whl
# Linux aarch64
pip install tron1-rl-deploy-python/limxsdk-lowlevel/python3/aarch64/limxsdk-*.whl
```

**3. 安装控制器的 Python 依赖：**

```bash
pip install numpy pyyaml scipy onnxruntime mujoco
```

**4. 选择机型和策略来源。** `ROBOT_TYPE` 取自上表，`RL_TYPE` 取 `isaacgym` 或 `isaaclab`。两个终端都要设置这两个变量。

```bash
export ROBOT_TYPE=PF_TRON1A
export RL_TYPE=isaacgym
```

**5. 先启动仿真器，再启动控制器**，各占一个终端：

```bash
python tron1-mujoco-sim/simulator.py      # 终端 1
python tron1-rl-deploy-python/main.py     # 终端 2
```

控制器启动前，机器人在仿真里会摔倒。`main.py` 运行后，在 MuJoCo 窗口按 **Backspace** 重置机器人，它会站起来并开始原地踏步。用下面的虚拟遥控器控制行走。

如果 `pip` 提示不能在虚拟环境外安装（`externally-managed-environment`），或仿真器还需要其他配置，见 [tron1-mujoco-sim README](https://github.com/limxdynamics/tron1-mujoco-sim)。

## 虚拟遥控器

```bash
./tron1-mujoco-sim/robot-joystick/robot-joystick
```

控制器读取的摇杆轴：

| 轴 | 指令 | 范围 |
|:-:|---|---|
| `axes[1]` | 前进 / 后退 | ±0.5 m/s |
| `axes[0]` | 横移 | ±0.5 m/s |
| `axes[2]` | 转向（偏航） | ±0.5 rad/s |

## 真机运行

按第 4 步设置好 `ROBOT_TYPE` 和 `RL_TYPE`，把机器人 IP 传给 `main.py`：

```bash
python main.py <robot-ip>
```

真机上控制器不会自行启动：要等机器人上报标定状态 `0`（终端打印 `Calibration state: 0`），再在遥控器上按 **L1 + Y** 才开始控制。按 **L1 + X** 停止：所有关节刚度置零、只保留阻尼，然后程序退出。

| 按键 | 作用 |
|:-:|---|
| L1 + Y | 启动控制器（需标定状态为 `0`） |
| L1 + X | 停止：刚度置零、只保留阻尼，然后退出 |
| 摇杆 | 速度指令，见「虚拟遥控器」一节 |

## 验证

在 MuJoCo 仿真中验证，环境为 `tron1-mujoco-sim`、limxsdk 3.4.0、ONNX Runtime 1.31，Linux x86_64。每个 `ROBOT_TYPE` 都分别用 `RL_TYPE=isaacgym` 和 `RL_TYPE=isaaclab` 运行，摇杆指令为零。重置后所有组合都能站起并在 10 s 内保持机身高度。点足机型会原地踏步，10 s 内漂移 0.7 到 1.7 m；足板和轮足机型漂移不超过 0.4 m。真机路径（`main.py <robot-ip>`）未在硬件上测试。

## 许可证

Apache License 2.0，见 [LICENSE](LICENSE) 和 [NOTICE](NOTICE)。
