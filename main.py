import os
import sys
import limxsdk.robot.Robot as Robot
import limxsdk.robot.RobotType as RobotType
import controllers as controllers

if __name__ == '__main__':
    # Get the robot type from the environment variable
    robot_type = os.getenv("ROBOT_TYPE")
    
    # Check if the ROBOT_TYPE environment variable is set, otherwise exit with an error
    if not robot_type:
        print("\033[31mError: Please set the ROBOT_TYPE using 'export ROBOT_TYPE=<robot_type>'.\033[0m")
        sys.exit(1)
    # get rl type
    rl_type = os.getenv("RL_TYPE")
    if not rl_type:
        print("\033[31mError: Please set the RL_TYPE using 'export RL_TYPE=isaacgym/isaaclab'.\033[0m")
        sys.exit(1)
    if rl_type != "isaacgym" and rl_type != "isaaclab":
        print("\033[31mError: RL_TYPE {} is not supported, choose between 'isaacgym' and 'isaaclab'.\033[0m".format(rl_type))
        sys.exit(1)

    # Create a Robot instance of the specified type
    robot = Robot(RobotType.PointFoot)

    # Default IP address for the robot
    robot_ip = "127.0.0.1"
    
    # Check if command-line argument is provided for robot IP
    if len(sys.argv) > 1:
        robot_ip = sys.argv[1]

    # Initialize the robot with the provided IP address
    if not robot.init(robot_ip):
        sys.exit()

    # Determine if the simulation is running
    start_controller = robot_ip == "127.0.0.1"

    # Create and run the controller
    if robot_type.startswith("PF"):
      controller = controllers.PointfootController(f'{os.path.dirname(os.path.abspath(__file__))}/controllers/model', robot, robot_type, rl_type, start_controller)
      controller.run()
    elif robot_type.startswith("WF"):
      controller = controllers.WheelfootController(f'{os.path.dirname(os.path.abspath(__file__))}/controllers/model', robot, robot_type, rl_type, start_controller)
      controller.run()
    elif robot_type.startswith("SF"):
      controller = controllers.SolefootController(f'{os.path.dirname(os.path.abspath(__file__))}/controllers/model', robot, robot_type, rl_type, start_controller)
      controller.run()
    else:
      print(f"Error: unknow robot type '{robot_type}'")
