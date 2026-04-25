
## 1. What is this project?

This is an **autonomous maze-solving robot** built in simulation.

- The robot is placed inside a maze
- It has **no GPS, no map, no prior knowledge** of the maze
- It uses only its **3 sensors** to navigate
- It follows the **Left-Wall Following** algorithm to solve the maze
- Everything runs inside **Gazebo** (a physics simulator) with **ROS 2**

Think of it like a person walking through a dark maze with their left hand always touching the left wall — they'll eventually find a way through.

---

## 2. Technology Stack

| Tool | Purpose |
|------|---------|
| **ROS 2 Humble** | Robot Operating System — handles communication between nodes |
| **Gazebo Classic 11** | Physics simulator — simulates the robot, maze, and sensors |
| **Python 3** | Controller logic (the brain of the robot) |
| **URDF** | Describes the physical robot body and sensors |
| **SDF** | Describes the maze world (walls, floor, lighting) |
| **RViz2** | 3D visualizer — shows the robot model and sensor data |

---

## 3. Project Structure

```
maze_ws/
├── src/
│   └── maze_bot/
│       ├── maze_bot/
│       │   └── controller.py      ← THE BRAIN (main logic)
│       ├── urdf/
│       │   └── robot.urdf         ← Robot body + sensors
│       ├── worlds/
│       │   └── maze.world         ← The maze (walls layout)
│       ├── launch/
│       │   └── maze.launch.py     ← Starts everything
│       ├── package.xml            ← ROS 2 package config
│       └── setup.py               ← Python package config
└── install/                       ← Built files (after colcon build)
```

---

## 4. The Robot Hardware (URDF)

The robot is defined in `robot.urdf`. It is a **differential drive robot** — like a wheelchair, it has two independently driven wheels.

```
        Top View:
        
        [caster_front]          ← passive ball wheel (front)
              |
    ┌─────────────────┐
    │                 │
[left_wheel]    [right_wheel]   ← driven wheels
    │                 │
    └─────────────────┘
              |
        [caster_back]           ← passive ball wheel (back)
```

### Physical Dimensions
| Part | Size |
|------|------|
| Body (base_link) | 22cm long × 18cm wide × 6cm tall |
| Wheels | 4cm radius, 2cm thick |
| Wheel separation | 22cm between centres |
| Total weight | ~1kg |

### How it moves
- The **diff_drive plugin** (Gazebo) simulates the motors
- It listens to `/cmd_vel` topic (Twist messages: linear + angular velocity)
- To go **straight**: both wheels same speed
- To turn **left**: right wheel faster than left
- To turn **right**: left wheel faster than right

---

## 5. Sensors Explained

The robot has **3 sensors** — this is ALL the information it uses to navigate.

### Sensor 1: Ultrasonic (Front)
```
         Robot
          ▲  ← facing this direction
    ══════╪══════
          │
    [Ultrasonic]  ← mounted at front center
          │
          ↓ emits sound waves forward
```
| Property | Value |
|----------|-------|
| Type | Ultrasonic (like parking sensors on a car) |
| Location | Front center of robot |
| Range | 3cm to 3.0m |
| Detects | Walls/obstacles AHEAD |
| ROS Topic | `/ultrasonic_front` |
| Used for | Deciding when to turn right (wall ahead) |

### Sensor 2: IR Left
```
    Left Wall
       │
       │← 0.20m →│
       │          [IR Left sensor]
       │              ← mounted on left-front corner
```
| Property | Value |
|----------|-------|
| Type | Infrared (like TV remote) |
| Location | Left-front corner of robot |
| Range | 1cm to 1.5m |
| Detects | Distance to LEFT wall |
| ROS Topic | `/ir_left` |
| Used for | Maintaining ideal distance from left wall |

### Sensor 3: IR Right
| Property | Value |
|----------|-------|
| Type | Infrared |
| Location | Right-front corner of robot |
| Range | 1cm to 1.5m |
| Detects | Distance to RIGHT wall |
| ROS Topic | `/ir_right` |
| Used for | Monitoring right-side clearance |

### Sensor Placement (why sensors are at x=0.09, y=±0.09)
The sensors are placed slightly **forward** (x=0.09) and at the **body edge** (y=±0.09).
This ensures the sensor rays exit cleanly into the corridor and do NOT accidentally detect the robot's own wheels.

---

## 6. The Maze World

Defined in `maze.world` (SDF format).

### Layout
```
y=+3.15 ┌──────────────────────────────────────┐
        │                          GOAL (green) │
y=+2.20 │   ┌────────── h4 ──────────────┐      │
        │   v1                           v2     │
y=+1.00 │   │   ┌──────── h3 ────────────┘      │
        │   │   │  (gap right)                  │
y=-0.20 │   │   └──────── h2 ────────┐          │
        │   │             (gap right) │          │
y=-2.25 │   └──── h1 ──────┐        v2          │
        │  START (blue)     │  gap               │
y=-3.15 └──────────────────┴────────────────────┘
       -3.15  -1.5  -0.5   0.8     2.0     3.15
```

### Walls
| Wall | Position | Direction | Gap side |
|------|----------|-----------|----------|
| outer_north/south/east/west | ±3.2m | all sides | none (boundary) |
| h1 | y = -2.25 | horizontal | right |
| v1 | x = -1.50 | vertical | connects h1 to h4 |
| h2 | y = -0.20 | horizontal | right |
| h3 | y = +1.00 | horizontal | right |
| v2 | x = +2.00 | vertical | connects h1 to outer_north |
| h4 | y = +2.20 | horizontal | right |

### Markers
- **Blue tile** at (-2.0, -2.6) = START position
- **Green tile** at (+2.6, +2.8) = GOAL position

---

## 7. The Brain — Controller Logic

File: `maze_bot/controller.py`

The controller is a **ROS 2 Node** called `maze_solver`.

### What it does every 0.1 seconds (10 Hz):
1. **Read sensors** — get latest F (front), L (left), R (right) distances
2. **Decide state** — which of the 4 states applies right now?
3. **Calculate speed** — compute linear and angular velocity
4. **Publish command** — send Twist message to `/cmd_vel`

### Subscriptions (inputs)
```
/ultrasonic_front  →  self.front  (float, metres)
/ir_left           →  self.left   (float, metres)
/ir_right          →  self.right  (float, metres)
```

### Publisher (output)
```
/cmd_vel  →  Twist message { linear.x, angular.z }
```

### Resilience Design
The controller uses a **full rclpy context reset loop**:
```
while True:
    rclpy.init()         ← fresh ROS 2 context
    run node...          ← navigate maze
    if RuntimeError:     ← Gazebo sent bad sensor data
        rclpy.shutdown() ← completely reset DDS
        sleep(0.15s)     ← wait for cleanup
        loop again       ← restart cleanly
```
This prevents the robot from permanently freezing if Gazebo sends a corrupted sensor message.

---

## 8. The Algorithm — Left-Wall Following

**Core Principle:** The robot always tries to keep the LEFT wall at exactly 0.20m distance.

This is one of the oldest and most reliable maze-solving algorithms.

### Why it works
In a **simply-connected maze** (all walls connected to the outer boundary), left-wall following GUARANTEES that the robot will eventually visit every reachable corridor. It's mathematically proven.

### The rule in plain English:
```
IF something is blocking me ahead:
    → Turn RIGHT (get away from the obstacle)

ELSE IF there's no wall on my left:
    → Curve LEFT (find the wall again)

ELSE IF I'm dangerously close to the left wall:
    → Emergency turn RIGHT

ELSE:
    → Drive forward, keeping left wall at 0.20m
```

---

## 9. State Machine — 4 States

```
                    ┌─────────────────┐
                    │                 │
              F < 0.30m         L > 1.20m
                    │                 │
                    ▼                 ▼
    ┌───────────┐  TURN_RIGHT    SEEK_WALL  ┌───────────┐
    │ FOLLOW    │←──────────────────────────│ SEEK_WALL │
    │ (normal)  │                           │ (find wall)│
    └───────────┘                           └───────────┘
          │
       L < 0.06m
          │
          ▼
    ┌───────────┐
    │  RESCUE   │
    │(too close)│
    └───────────┘
```

### State 1: FOLLOW (Normal navigation)
- **Condition:** Left wall detected (0.06m < L < 1.20m) AND front clear (F > 0.30m)
- **Action:** Drive forward at 0.10 m/s, use P-controller to steer
- **Log example:** `[FOLLOW left=0.20 err=+0.00] F=1.50 L=0.20 R=0.47 v=0.10 w=0.00`

### State 2: SEEK_WALL (Find the left wall)
- **Condition:** Left wall too far away (L > 1.20m) — robot went past a gap
- **Action:** Drive at 70% speed (0.07 m/s) while curving LEFT continuously
- **Why:** Robot lost its left wall (passed a corner/gap), needs to find it again
- **Log example:** `[SEEK_WALL] F=2.50 L=1.35 R=0.60 v=0.07 w=+0.23`

### State 3: TURN_RIGHT (Avoid front obstacle)
- **Condition:** Front obstacle within 0.30m (F < 0.30m)
- **Action:** Slow forward (0.025 m/s) while spinning RIGHT at full speed (0.45 rad/s)
- **Why:** Wall is directly ahead — must turn to find a new path
- **Log example:** `[TURN_RIGHT] F=0.15 L=0.12 R=0.44 v=0.03 w=-0.45`

### State 4: RESCUE (Emergency)
- **Condition:** Dangerously close to left wall (L < 0.06m)
- **Action:** Spin RIGHT aggressively (full turn speed, no forward motion)
- **Why:** Robot is about to collide with the left wall — emergency correction
- **Log example:** `[RESCUE] F=1.20 L=0.04 R=0.80 v=0.00 w=-0.45`

---

## 10. P-Controller — Smooth Steering

In FOLLOW state, the robot doesn't just drive straight. It uses a **Proportional Controller (P-controller)** to smoothly maintain the ideal gap to the left wall.

### Formula
```
error       = left_sensor_reading - LEFT_IDEAL
            = L - 0.20

angular_vel = Kp × error
            = 2.5 × error

# Positive error (L > 0.20): robot drifted right → steer LEFT (positive angular_z)
# Negative error (L < 0.20): robot too close    → steer RIGHT (negative angular_z)
```

### Example
```
L = 0.25m  →  error = +0.05  →  angular_z = 2.5 × 0.05 = +0.125 rad/s  (steer left)
L = 0.20m  →  error = 0.00   →  angular_z = 0.00 rad/s                  (go straight)
L = 0.15m  →  error = -0.05  →  angular_z = 2.5 × -0.05 = -0.125 rad/s (steer right)
```

The steering is **proportional to the error** — small deviation = gentle correction, large deviation = sharp correction. This gives smooth, natural-looking navigation.

---

## 11. How All Nodes Connect

```
┌──────────────────────────────────────────────────────┐
│                     ROS 2 Network                    │
│                                                      │
│  ┌─────────────┐    /ultrasonic_front                │
│  │   Gazebo    │───────────────────────┐             │
│  │  Simulator  │    /ir_left           │             │
│  │             │───────────────────┐   │             │
│  │  (physics   │    /ir_right      │   │             │
│  │   + sensors │─────────────┐     │   │             │
│  │   + motors) │             ▼     ▼   ▼             │
│  │             │      ┌──────────────────┐           │
│  │             │      │  controller.py   │           │
│  │             │      │  (maze_solver)   │           │
│  │             │      └────────┬─────────┘           │
│  │             │               │ /cmd_vel             │
│  │             │◄──────────────┘                     │
│  └─────────────┘                                     │
│                                                      │
│  ┌──────────────────────┐  ┌──────────────────────┐  │
│  │  robot_state_publisher│  │       RViz2          │  │
│  │  (publishes TF tree) │  │  (3D visualization)  │  │
│  └──────────────────────┘  └──────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

---

## 12. How to Run

### Start the project
```bash
cd /home/maze_ws
source /opt/ros/humble/setup.bash
colcon build --packages-select maze_bot
source install/setup.bash
ros2 launch maze_bot maze.launch.py
```

### Stop the project
```bash
# Option 1: In the same terminal
Ctrl + C

# Option 2: Force kill from any terminal
killall -9 gzserver gzclient rviz2
```

### What launches (maze.launch.py starts these 5 processes):
| Process | What it does |
|---------|-------------|
| `gzserver` | Gazebo physics engine — runs the simulation |
| `gzclient` | Gazebo GUI — the window you see |
| `robot_state_publisher` | Publishes robot's TF (transform tree) |
| `spawn_entity` | Places the robot in the maze |
| `rviz2` | Opens the 3D visualizer |
| `controller` | Runs the Python navigation brain |

---

## 13. Key Parameters

All tunable values in `controller.py`:

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `LINEAR_SPEED` | 0.10 m/s | Normal forward speed |
| `TURN_SPEED` | 0.45 rad/s | Maximum rotation speed |
| `FRONT_BLOCK` | 0.30 m | Turn right if wall closer than this |
| `LEFT_IDEAL` | 0.20 m | Target distance from left wall |
| `LEFT_FAR` | 1.20 m | Seek wall if left gap larger than this |
| `RESCUE_DIST` | 0.06 m | Emergency if this close to left wall |
| `Kp` | 2.5 | P-controller gain (steering sensitivity) |

---
