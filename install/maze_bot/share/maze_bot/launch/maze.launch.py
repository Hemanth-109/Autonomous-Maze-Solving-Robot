import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    IncludeLaunchDescription,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():

    pkg_dir       = get_package_share_directory('maze_bot')
    gazebo_ros    = get_package_share_directory('gazebo_ros')

    world_path    = os.path.join(pkg_dir, 'worlds', 'maze.world')
    robot_urdf    = os.path.join(pkg_dir, 'urdf',   'robot.urdf')
    rviz_config   = os.path.join(pkg_dir, 'rviz',   'maze_bot.rviz')

    with open(robot_urdf, 'r') as f:
        robot_description = f.read()

    # ── 1. Gazebo (server + client) ──────────────────────────────────────────
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gazebo_ros, 'launch', 'gazebo.launch.py')
        ),
        launch_arguments={
            'world':   world_path,
            'verbose': 'true',
        }.items(),
    )

    # ── 2. robot_state_publisher – broadcasts URDF + static TF ──────────────
    rsp = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': True,
        }],
    )

    # ── 3. Spawn robot in Gazebo (wait 3 s for Gazebo to fully load) ─────────
    # spawn_z=0.045 ensures wheels (radius 0.04) touch ground and body clears it
    spawn = TimerAction(
        period=3.0,
        actions=[
            Node(
                package='gazebo_ros',
                executable='spawn_entity.py',
                name='spawn_entity',
                output='screen',
                arguments=[
                    '-entity',   'maze_bot',
                    '-file',      robot_urdf,
                    '-x',        '-2.5',
                    '-y',        '-3.3',   # h1 at y=-2.9, left sensor reads 0.4 m → FOLLOW
                    '-z',         '0.045',
                    '-Y',         '0.0',
                ],
            )
        ],
    )

    # ── 4. Maze-solver controller (wait for robot to be fully spawned) ───────
    controller = TimerAction(
        period=8.0,
        actions=[
            Node(
                package='maze_bot',
                executable='controller',
                name='maze_solver',
                output='screen',
                parameters=[{'use_sim_time': True}],
            )
        ],
    )

    # ── 5. RViz ──────────────────────────────────────────────────────────────
    rviz = TimerAction(
        period=5.0,
        actions=[
            Node(
                package='rviz2',
                executable='rviz2',
                name='rviz2',
                output='screen',
                arguments=['-d', rviz_config],
                parameters=[{'use_sim_time': True}],
            )
        ],
    )

    return LaunchDescription([
        gazebo,
        rsp,
        spawn,
        controller,
        rviz,
    ])
