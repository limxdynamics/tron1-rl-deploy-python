# 中文 | [English](README.md)
# rl-deploy-with-python



## 1. 运行仿真

- 打开一个 Bash 终端。

- 下载 MuJoCo 仿真器代码：

  ```
  git clone --recurse https://github.com/limxdynamics/pointfoot-mujoco-sim.git
  ```

- 安装运动控制开发库（如果尚未安装）：

  - Linux x86_64 环境

    ```
    pip install pointfoot-mujoco-sim/limxsdk-lowlevel/python3/amd64/limxsdk-*-py3-none-any.whl
    ```

  - Linux aarch64 环境

    ```
    pip install pointfoot-mujoco-sim/limxsdk-lowlevel/python3/aarch64/limxsdk-*-py3-none-any.whl
    ```

- 设置机器人类型

  - 通过 Shell 命令 `tree -L 1 pointfoot-mujoco-sim/robot-description/pointfoot` 列出可用的机器人类型：
  
    ```
    limx@limx:~$ tree -L 1 pointfoot-mujoco-sim/robot-description/pointfoot
    pointfoot-mujoco-sim/robot-description/pointfoot
    ├── PF_P441A
    ├── PF_P441B
    ├── PF_P441C
    └── PF_P441C2
    
    ```
  
  - 以`PF_P441C`（请根据实际机器人类型进行替换）为例，设置机器人型号类型：
  
    ```
    echo 'export ROBOT_TYPE=PF_P441C' >> ~/.bashrc && source ~/.bashrc
    ```
  
- 运行 MuJoCo 仿真器：

  ```
  python pointfoot-mujoco-sim/simulator.py
  ```
  


## 2. 运行控制算法

- 打开一个 Bash 终端。

- 下载控制算法代码：

  ```
  git clone --recurse https://github.com/limxdynamics/rl-deploy-with-python.git
  ```
  
- 安装运动控制开发库（如果尚未安装）：

  - Linux x86_64 环境

    ```
    pip install rl-deploy-with-python/limxsdk-lowlevel/python3/amd64/limxsdk-*-py3-none-any.whl
    ```

  - Linux aarch64 环境

    ```
    pip install rl-deploy-with-python/limxsdk-lowlevel/python3/aarch64/limxsdk-*-py3-none-any.whl
    ```

- 设置机器人类型

  - 通过 Shell 命令 `tree -L 1 rl-deploy-with-python/controllers/model` 列出可用的机器人类型：

    ```
    limx@limx:~$ tree -L 1 rl-deploy-with-python/controllers/model
    rl-deploy-with-python/controllers/model
    ├── PF_P441A
    ├── PF_P441B
    ├── PF_P441C
    ├── PF_P441C2
    ├── PF_TRON1A
    ├── SF_TRON1A
    └── WF_TRON1A
    
    ```

  - 以`PF_P441C`（请根据实际机器人类型进行替换）为例，设置机器人型号类型：

    ```
    echo 'export ROBOT_TYPE=PF_P441C' >> ~/.bashrc && source ~/.bashrc
    ```

- 选择训练环境
  
  目前支持的训练环境有`isaacgym`和`isaaclab`，以`isaacgym`为例，设置训练环境类型
  
  ```
  echo 'export RL_TYPE=isaacgym' >> ~/.bashrc && source ~/.bashrc
  ```
  
- 运行控制算法：

  ```
  python rl-deploy-with-python/main.py
  ```

## 3. 虚拟遥控器

- 打开一个 Bash 终端。

- 运行 robot-joystick：

  ```
  ./pointfoot-mujoco-sim/robot-joystick/robot-joystick
  ```

## 4. 效果展示
![](doc/simulator.gif)

