import os
import sys
import copy
import numpy as np
import yaml
import time
import onnxruntime as ort
from scipy.spatial.transform import Rotation as R
from functools import partial
import limxsdk
import limxsdk.robot.Rate as Rate
import limxsdk.robot.Robot as Robot
import limxsdk.robot.RobotType as RobotType
import limxsdk.datatypes as datatypes

class SolefootController:
    def __init__(self, model_dir, robot, robot_type, rl_type, start_controller):
        # Initialize robot and type information
        self.robot = robot
        self.robot_type = robot_type
        self.rl_type = rl_type

        # Load configuration and model file paths based on robot type
        self.config_file = f'{model_dir}/{self.robot_type}/params.yaml'
        self.model_policy = f'{model_dir}/{self.robot_type}/policy/{self.rl_type}/policy.onnx'
        self.model_encoder = f'{model_dir}/{self.robot_type}/policy/{self.rl_type}/encoder.onnx'

        # Load configuration settings from the YAML file
        self.load_config(self.config_file)
        
        # Load the ONNX model
        self.initialize_onnx_models()

        # Prepare robot command structure with default values for mode, q, dq, tau, Kp, Kd
        self.robot_cmd = datatypes.RobotCmd()
        self.robot_cmd.mode = [0. for x in range(0, self.joint_num)]
        self.robot_cmd.q = [0. for x in range(0, self.joint_num)]
        self.robot_cmd.dq = [0. for x in range(0, self.joint_num)]
        self.robot_cmd.tau = [0. for x in range(0, self.joint_num)]
        self.robot_cmd.Kp = [self.control_cfg['stiffness'] for x in range(0, self.joint_num)]
        self.robot_cmd.Kd = [self.control_cfg['damping'] for x in range(0, self.joint_num)]

        # Prepare robot state structure
        self.robot_state = datatypes.RobotState()
        self.robot_state.tau = [0. for x in range(0, self.joint_num)]
        self.robot_state.q = [0. for x in range(0, self.joint_num)]
        self.robot_state.dq = [0. for x in range(0, self.joint_num)]
        self.robot_state_tmp = copy.deepcopy(self.robot_state)

        # Initialize IMU (Inertial Measurement Unit) data structure
        self.imu_data = datatypes.ImuData()
        self.imu_data.quat[0] = 0
        self.imu_data.quat[1] = 0
        self.imu_data.quat[2] = 0
        self.imu_data.quat[3] = 1
        self.imu_data_tmp = copy.deepcopy(self.imu_data)

        # Set up a callback to receive updated robot state data
        self.robot_state_callback_partial = partial(self.robot_state_callback)
        self.robot.subscribeRobotState(self.robot_state_callback_partial)

        # Set up a callback to receive updated IMU data
        self.imu_data_callback_partial = partial(self.imu_data_callback)
        self.robot.subscribeImuData(self.imu_data_callback_partial)

        # Set up a callback to receive updated SensorJoy
        self.sensor_joy_callback_partial = partial(self.sensor_joy_callback)
        self.robot.subscribeSensorJoy(self.sensor_joy_callback_partial)

        # Set up a callback to receive diagnostic data
        self.robot_diagnostic_callback_partial = partial(self.robot_diagnostic_callback)
        self.robot.subscribeDiagnosticValue(self.robot_diagnostic_callback_partial)

        # Initialize the calibration state to -1, indicating no calibration has occurred.
        self.calibration_state = -1

        # Flag to start the controller
        self.start_controller = start_controller

        # Gait index
        self.gait_index = 0

        # Flag indicating first received observation
        self.is_first_rec_obs = True
    
    def initialize_onnx_models(self):
        # Configure ONNX Runtime session options to optimize CPU usage
        session_options = ort.SessionOptions()
        # Limit the number of threads used for parallel computation within individual operators
        session_options.intra_op_num_threads = 1
        # Limit the number of threads used for parallel execution of different operators
        session_options.inter_op_num_threads = 1
        # Enable all possible graph optimizations to improve inference performance
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # Disable CPU memory arena to reduce memory fragmentation
        session_options.enable_cpu_mem_arena = False
        # Disable memory pattern optimization to have more control over memory allocation
        session_options.enable_mem_pattern = False

        # Define execution providers to use CPU only, ensuring no GPU inference
        cpu_providers = ['CPUExecutionProvider']
        
        # Load the ONNX model and set up input and output names
        self.policy_session = ort.InferenceSession(self.model_policy, sess_options=session_options, providers=cpu_providers)
        self.policy_input_names = [self.policy_session.get_inputs()[i].name for i in range(self.policy_session.get_inputs().__len__())]
        self.policy_output_names = [self.policy_session.get_outputs()[i].name for i in range(self.policy_session.get_outputs().__len__())]
        self.policy_input_shapes = [self.policy_session.get_inputs()[i].shape for i in range(self.policy_session.get_inputs().__len__())]
        self.policy_output_shapes = [self.policy_session.get_outputs()[i].shape for i in range(self.policy_session.get_outputs().__len__())]

        self.encoder_session = ort.InferenceSession(self.model_encoder, sess_options=session_options, providers=cpu_providers)
        self.encoder_input_names = [self.encoder_session.get_inputs()[i].name for i in range(self.encoder_session.get_inputs().__len__())]
        self.encoder_output_names = [self.encoder_session.get_outputs()[i].name for i in range(self.encoder_session.get_outputs().__len__())]
        self.encoder_input_shapes = [self.encoder_session.get_inputs()[i].shape for i in range(self.encoder_session.get_inputs().__len__())]
        self.encoder_output_shapes = [self.encoder_session.get_outputs()[i].shape for i in range(self.encoder_session.get_outputs().__len__())]

    # Load the configuration from a YAML file
    def load_config(self, config_file):
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        # Assign configuration parameters to controller variables
        self.joint_names = config['PointfootCfg']['joint_names']
        self.init_state = config['PointfootCfg']['init_state']['default_joint_angle']
        self.stand_duration = config['PointfootCfg']['stand_mode']['stand_duration']
        self.control_cfg = config['PointfootCfg']['control']
        self.rl_cfg = config['PointfootCfg']['normalization']
        self.obs_scales = config['PointfootCfg']['normalization']['obs_scales']
        self.actions_size = config['PointfootCfg']['size']['actions_size']
        self.commands_size = config['PointfootCfg']['size']['commands_size']
        self.observations_size = config['PointfootCfg']['size']['observations_size']
        self.obs_history_length = config['PointfootCfg']['size']['obs_history_length']
        self.encoder_output_size = config['PointfootCfg']['size']['encoder_output_size']
        self.imu_orientation_offset = np.array(list(config['PointfootCfg']['imu_orientation_offset'].values()))
        self.user_cmd_cfg = config['PointfootCfg']['user_cmd_scales']
        self.loop_frequency = config['PointfootCfg']['loop_frequency']
        self.encoder_input_size = self.obs_history_length * self.observations_size

        # Initialize variables for actions, observations, and commands
        self.proprio_history_vector = np.zeros(self.obs_history_length * self.observations_size)
        self.encoder_out = np.zeros(self.encoder_output_size)
        self.actions = np.zeros(self.actions_size)
        self.observations = np.zeros(self.observations_size)
        self.last_actions = np.zeros(self.actions_size)
        self.commands = np.zeros(self.commands_size)  # command to the robot (e.g., velocity, rotation)
        self.scaled_commands = np.zeros(self.commands_size)
        self.base_lin_vel = np.zeros(3)  # base linear velocity
        self.base_position = np.zeros(3)  # robot base position
        self.loop_count = 0  # loop iteration count
        self.stand_percent = 0  # percentage of time the robot has spent in stand mode
        self.policy_session = None  # ONNX model session for policy inference
        self.joint_num = len(self.joint_names)  # number of joints

        self.ankle_joint_damping = config['PointfootCfg']['control']['ankle_joint_damping']
        self.ankle_joint_torque_limit = config['PointfootCfg']['control']['ankle_joint_torque_limit']

        self.gait_frequencies = config['PointfootCfg']['gait']['frequencies']
        self.gait_swing_height = config['PointfootCfg']['gait']['swing_height']

        # Initialize joint angles based on the initial configuration
        self.init_joint_angles = np.zeros(len(self.joint_names))
        for i in range(len(self.joint_names)):
            self.init_joint_angles[i] = self.init_state[self.joint_names[i]]
        
        # Set initial mode to "STAND"
        self.mode = "STAND"

    # Main control loop
    def run(self):
        # Wait until the controller is started
        while not self.start_controller:
          time.sleep(1)

        # Initialize default joint angles for standing
        self.default_joint_angles = np.array([0.0] * len(self.joint_names))
        self.stand_percent += 1 / (self.stand_duration * self.loop_frequency)
        self.mode = "STAND"
        self.loop_count = 0

        # Set the loop rate based on the frequency in the configuration
        rate = Rate(self.loop_frequency)
        while self.start_controller:
            self.update()
            rate.sleep()
        
        # Reset robot command values to ensure a safe stop when exiting the loop
        self.robot_cmd.q = [0. for x in range(0, self.joint_num)]
        self.robot_cmd.dq = [0. for x in range(0, self.joint_num)]
        self.robot_cmd.tau = [0. for x in range(0, self.joint_num)]
        self.robot_cmd.Kp = [0. for x in range(0, self.joint_num)]
        self.robot_cmd.Kd = [1.0 for x in range(0, self.joint_num)]
        self.robot.publishRobotCmd(self.robot_cmd)
        time.sleep(1)

    # Handle the stand mode for smoothly transitioning the robot into standing
    def handle_stand_mode(self):
        if self.stand_percent < 1:
            for j in range(len(self.joint_names)):
                # Interpolate between initial and default joint angles during stand mode
                pos_des = self.default_joint_angles[j] * (1 - self.stand_percent) + self.init_state[self.joint_names[j]] * self.stand_percent
                self.set_joint_command(j, pos_des, 0, 0, self.control_cfg['stiffness'], self.control_cfg['damping'])
            # Increment the stand percentage over time
            self.stand_percent += 1 / (self.stand_duration * self.loop_frequency)
        else:
            # Switch to walk mode after standing
            self.mode = "WALK"

    # Handle the walk mode where the robot moves based on computed actions
    def handle_walk_mode(self):
        # Update the temporary robot state and IMU data
        self.robot_state_tmp = copy.deepcopy(self.robot_state)
        self.imu_data_tmp = copy.deepcopy(self.imu_data)

        # Execute actions every 'decimation' iterations
        if self.loop_count % self.control_cfg['decimation'] == 0:
            self.compute_observation()
            self.compute_encoder()
            self.compute_actions()
            # Clip the actions within predefined limits
            action_min = -self.rl_cfg['clip_scales']['clip_actions']
            action_max = self.rl_cfg['clip_scales']['clip_actions']
            self.actions = np.clip(self.actions, action_min, action_max)

            # swap actions positions back to deep first, only when action updated
            if self.rl_type == "isaaclab":
                self.actions = self.swap_positions(self.actions, reverse=True)

        # Iterate over the joints and set commands based on actions
        joint_pos = np.array(self.robot_state_tmp.q)
        joint_vel = np.array(self.robot_state_tmp.dq)

        for i in range(len(joint_pos)):
            if (i + 1) % 4 != 0:
                # Compute the limits for the action based on joint position and velocity
                action_min = (joint_pos[i] - self.init_joint_angles[i] +
                              (self.control_cfg['damping'] * joint_vel[i] - self.control_cfg['user_torque_limit']) /
                              self.control_cfg['stiffness'])
                action_max = (joint_pos[i] - self.init_joint_angles[i] +
                              (self.control_cfg['damping'] * joint_vel[i] + self.control_cfg['user_torque_limit']) /
                              self.control_cfg['stiffness'])

                # Clip action within limits
                self.actions[i] = max(action_min / self.control_cfg['action_scale_pos'],
                                      min(action_max / self.control_cfg['action_scale_pos'], self.actions[i]))

                # Compute the desired joint position and set it
                pos_des = self.actions[i] * self.control_cfg['action_scale_pos'] + self.init_joint_angles[i]
                self.set_joint_command(i, pos_des, 0, 0, self.control_cfg['stiffness'], self.control_cfg['damping'])

                # Save the last action for reference
                self.last_actions[i] = self.actions[i]
            else:
                action_min = joint_vel[i] - self.ankle_joint_torque_limit / self.ankle_joint_damping
                action_max = joint_vel[i] + self.ankle_joint_torque_limit / self.ankle_joint_damping
                self.last_actions[i] = self.actions[i]
                self.actions[i] = max(action_min / self.ankle_joint_damping,
                                      min(action_max / self.ankle_joint_damping, self.actions[i]))
                velocity_des = self.actions[i] * self.ankle_joint_damping
                self.set_joint_command(i, 0, velocity_des, 0, 0, self.ankle_joint_damping)

    def swap_positions(self, initial_array, reverse=False):
        joint_idx_lab = [0, 4, 1, 5, 2, 6, 3, 7]
        new_array = np.zeros(initial_array.shape)
        for i in range(len(joint_idx_lab)):
            if not reverse:
                new_array[i] = initial_array[joint_idx_lab[i]]
            else:
                new_array[joint_idx_lab[i]] = initial_array[i]
        return new_array
    
    def compute_observation(self):
        # Convert IMU orientation from quaternion to Euler angles (ZYX convention)
        imu_orientation = np.array(self.imu_data_tmp.quat)
        q_wi = R.from_quat(imu_orientation).as_euler('zyx')  # Quaternion to Euler ZYX conversion
        inverse_rot = R.from_euler('zyx', q_wi).inv().as_matrix()  # Get the inverse rotation matrix

        # Project the gravity vector (pointing downwards) into the body frame
        gravity_vector = np.array([0, 0, -1])  # Gravity in world frame (z-axis down)
        projected_gravity = np.dot(inverse_rot, gravity_vector)  # Transform gravity into body frame

        # Retrieve base angular velocity from the IMU data
        base_ang_vel = np.array(self.imu_data_tmp.gyro)
        # Apply IMU orientation offset correction (using Euler angles)
        rot = R.from_euler('zyx', self.imu_orientation_offset).as_matrix()  # Rotation matrix for offset correction
        base_ang_vel = np.dot(rot, base_ang_vel)  # Apply correction to angular velocity
        projected_gravity = np.dot(rot, projected_gravity)  # Apply correction to projected gravity

        # Retrieve joint positions and velocities from the robot state
        joint_positions = np.array(self.robot_state_tmp.q)
        joint_velocities = np.array(self.robot_state_tmp.dq)

        gait = np.array([self.gait_frequencies, 0.5, 0.5, self.gait_swing_height])
        self.gait_index += 0.02 * gait[0]
        if self.gait_index > 1.0:
            self.gait_index = 0.0
        gait_clock = np.array([np.sin(self.gait_index * 2 * np.pi), np.cos(self.gait_index * 2 * np.pi)])

        # Retrieve the last actions that were applied to the robot
        actions = np.array(self.last_actions)

        # Create a command scaler matrix for linear and angular velocities
        command_scaler = np.diag([
            self.user_cmd_cfg['lin_vel_x'],  # Scale factor for linear velocity in x direction
            self.user_cmd_cfg['lin_vel_y'],  # Scale factor for linear velocity in y direction
            self.user_cmd_cfg['ang_vel_yaw'],  # Scale factor for yaw (angular velocity)
            1.0, 1.0
        ])

        # Apply scaling to the command inputs (velocity commands)
        self.scaled_commands = np.dot(command_scaler, self.commands)
        if self.rl_type == "isaaclab":
            self.scaled_commands = self.scaled_commands[:-2]

        # Populate observation vector
        joint_pos_input = (joint_positions - self.init_joint_angles) * self.obs_scales['dof_pos']
        # swap positions in joint_pos, joint_vel and actions if mode is isaaclab
        if self.rl_type == "isaaclab":
            joint_pos_input = self.swap_positions(joint_pos_input)
            joint_velocities = self.swap_positions(joint_velocities)
            actions = self.swap_positions(actions)

        # Create the observation vector by concatenating various state variables:
        # - Base angular velocity (scaled)
        # - Projected gravity vector
        # - Joint positions (difference from initial angles, scaled)
        # - Joint velocities (scaled)
        # - Last actions applied to the robot
        # - gait_clock: A clock signal related to the gait of the robot.
        # - gait: Information about the current gait of the robot.
        obs = np.concatenate([
            base_ang_vel * self.obs_scales['ang_vel'],  # Scaled base angular velocity
            projected_gravity,  # Projected gravity vector in body frame
            joint_pos_input,  # Scaled joint positions
            joint_velocities * self.obs_scales['dof_vel'],  # Scaled joint velocities
            actions,  # Last actions taken by the robot
            gait_clock,  # A clock signal related to the robot's gait
            gait  # Information about the current gait pattern of the robot
        ])

        # Check if this is the first recorded observation
        if self.is_first_rec_obs:
            # Calculate the total size of the encoder input
            input_size = np.prod(self.encoder_input_shapes[0])
            
            # Initialize the proprioceptive history buffer with zeros
            self.proprio_history_buffer = np.zeros(input_size)

            # Fill the proprioceptive history buffer with the current observation for the entire history length
            for i in range(self.obs_history_length):
                self.proprio_history_buffer[i * self.observations_size:(i + 1) * self.observations_size] = obs

            # Update the flag to indicate that the first observation has been processed
            self.is_first_rec_obs = False
        
        # Shift the existing proprioceptive history buffer to the left
        self.proprio_history_buffer[:-self.observations_size] = self.proprio_history_buffer[self.observations_size:]

        # Add the current observation to the end of the proprioceptive history buffer
        self.proprio_history_buffer[-self.observations_size:] = obs

        # Convert the proprioceptive history buffer to a numpy array
        self.proprio_history_vector = np.array(self.proprio_history_buffer)

        # Clip the observation values to within the specified limits for stability
        self.observations = np.clip(
            obs, 
            -self.rl_cfg['clip_scales']['clip_observations'],  # Lower limit for clipping
            self.rl_cfg['clip_scales']['clip_observations']  # Upper limit for clipping
        )

    def compute_actions(self):
        """
        Computes the actions based on the current observations using the policy session.
        """
        # Concatenate observations into a single tensor and convert to float32
        input_tensor = np.concatenate([self.encoder_out, self.observations, self.scaled_commands], axis=0)
        input_tensor = input_tensor.astype(np.float32)
        
        # Create a dictionary of inputs for the policy session
        inputs = {self.policy_input_names[0]: input_tensor}
        
        # Run the policy session and get the output
        output = self.policy_session.run(self.policy_output_names, inputs)
        
        # Flatten the output and store it as actions
        self.actions = np.array(output).flatten()

    def compute_encoder(self):
        """
        Computes the encoder output based on the proprioceptive history buffer.

        This method first concatenates the proprioceptive history buffer into a single input tensor.
        Then it converts the input tensor to the float32 data type. After that, it creates a dictionary
        of inputs for the encoder session and runs the encoder session to get the output. Finally,
        it flattens the output and stores it as the encoder output.
        """
        # Concatenate the proprioceptive history buffer into a single tensor and convert to float32
        input_tensor = np.concatenate([self.proprio_history_buffer], axis=0)
        input_tensor = input_tensor.astype(np.float32)

        # Create a dictionary of inputs for the encoder session
        inputs = {self.encoder_input_names[0]: input_tensor}

        # Run the encoder session and get the output
        output = self.encoder_session.run(self.encoder_output_names, inputs)

        # Flatten the output and store it as the encoder output
        self.encoder_out = np.array(output).flatten()
 
    def set_joint_command(self, joint_index, q, dq, tau, kp, kd):
        """
        Sends a command to configure the state of a specific joint.
        This method updates the joint's desired position, velocity, torque, and control gains.
        Replace this implementation with the actual communication logic for your hardware.

        Parameters:
        joint_index (int): The index of the joint to be controlled.
        q (float): The desired joint position, typically in radians or degrees.
        dq (float): The desired joint velocity, typically in radians/second or degrees/second.
        tau (float): The desired joint torque, typically in Newton-meters (Nm).
        kp (float): The proportional gain for position control.
        kd (float): The derivative gain for velocity control.
        """
        self.robot_cmd.q[joint_index] = q
        self.robot_cmd.dq[joint_index] = dq
        self.robot_cmd.tau[joint_index] = tau
        self.robot_cmd.Kp[joint_index] = kp
        self.robot_cmd.Kd[joint_index] = kd

    def update(self):
        """
        Updates the robot's state based on the current mode and publishes the robot command.
        """
        if self.mode == "STAND":
            self.handle_stand_mode()
        elif self.mode == "WALK":
            self.handle_walk_mode()
        
        # Increment the loop count
        self.loop_count += 1

        # Publish the robot command
        self.robot.publishRobotCmd(self.robot_cmd)
        
    # Callback function for receiving robot command data
    def robot_state_callback(self, robot_state: datatypes.RobotState):
        """
        Callback function to update the robot state from incoming data.
        
        Parameters:
        robot_state (datatypes.RobotState): The current state of the robot.
        """
        self.robot_state = robot_state

    # Callback function for receiving imu data
    def imu_data_callback(self, imu_data: datatypes.ImuData):
        """
        Callback function to update IMU data from incoming data.
        
        Parameters:
        imu_data (datatypes.ImuData): The IMU data containing stamp, acceleration, gyro, and quaternion.
        """
        self.imu_data.stamp = imu_data.stamp
        self.imu_data.acc = imu_data.acc
        self.imu_data.gyro = imu_data.gyro
        
        # Rotate quaternion values
        self.imu_data.quat[0] = imu_data.quat[1]
        self.imu_data.quat[1] = imu_data.quat[2]
        self.imu_data.quat[2] = imu_data.quat[3]
        self.imu_data.quat[3] = imu_data.quat[0]

    # Callback function for receiving sensor joy data
    def sensor_joy_callback(self, sensor_joy: datatypes.SensorJoy):
        # Check if the robot is in the calibration state and both L1 (button index 4) and Y (button index 3) buttons are pressed.
        if not self.start_controller and self.calibration_state == 0 and sensor_joy.buttons[4] == 1 and sensor_joy.buttons[3] == 1:
          print(f"L1 + Y: start_controller...")
          self.start_controller = True

        # Check if both L1 (button index 4) and X (button index 2) are pressed to stop the controller
        if self.start_controller and sensor_joy.buttons[4] == 1 and sensor_joy.buttons[2] == 1:
          print(f"L1 + X: stop_controller...")
          self.start_controller = False

        linear_x  = sensor_joy.axes[1]
        linear_y  = sensor_joy.axes[0]
        angular_z = sensor_joy.axes[2]

        linear_x  = 1.0 if linear_x > 1.0 else (-1.0 if linear_x < -1.0 else linear_x)
        linear_y  = 1.0 if linear_y > 1.0 else (-1.0 if linear_y < -1.0 else linear_y)
        angular_z = 1.0 if angular_z > 1.0 else (-1.0 if angular_z < -1.0 else angular_z)

        self.commands[0] = linear_x * 0.5
        self.commands[1] = linear_y * 0.5
        self.commands[2] = angular_z * 0.5
        self.commands[3] = 0.0
        self.commands[4] = 0.0

    # Callback function for receiving diagnostic data
    def robot_diagnostic_callback(self, diagnostic_value: datatypes.DiagnosticValue):
      # Check if the received diagnostic data is related to calibration.
      if diagnostic_value.name == "calibration":
        print(f"Calibration state: {diagnostic_value.code}")
        self.calibration_state = diagnostic_value.code
