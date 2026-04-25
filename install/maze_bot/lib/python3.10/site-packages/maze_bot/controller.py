import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import Range
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy


# ── Tuning ───────────────────────────────────────────────────────────────────────────────
LINEAR_SPEED  = 0.15   # m/s  forward cruise speed (faster – corridors are wider)
TURN_SPEED    = 0.45   # rad/s  maximum turn rate

FRONT_BLOCK   = 0.35   # m  turn right if front obstacle closer than this
LEFT_IDEAL    = 0.25   # m  desired gap to left wall
LEFT_FAR      = 5.00   # m  must exceed widest corridor (~4.4 m middle zone)
RESCUE_DIST   = 0.07   # m  emergency: robot is dangerously close to left wall
Kp            = 2.5    # proportional gain
# ───────────────────────────────────────────────────────────────────────────────


class MazeSolver(Node):

    def __init__(self, init_front=3.0, init_left=LEFT_IDEAL, init_right=LEFT_IDEAL):
        super().__init__('maze_solver')

        # Inherit last known values across restarts so robot keeps its state
        self.front = init_front
        self.left  = init_left
        self.right = init_right
        self._tick = 0

        # BEST_EFFORT + depth=1: drop stale/bad messages immediately
        sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.create_subscription(Range, '/ultrasonic_front', self._cb_front, sensor_qos)
        self.create_subscription(Range, '/ir_left',          self._cb_left,  sensor_qos)
        self.create_subscription(Range, '/ir_right',         self._cb_right, sensor_qos)

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_timer(0.1, self._control_loop)

        self.get_logger().info('MazeSolver ready.')

    # ── Sensor helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _clean(msg: Range) -> float:
        r = msg.range
        if math.isnan(r) or math.isinf(r) or r < msg.min_range:
            return msg.max_range
        return min(r, msg.max_range)

    def _cb_front(self, msg: Range): self.front = self._clean(msg)
    def _cb_left (self, msg: Range): self.left  = self._clean(msg)
    def _cb_right(self, msg: Range): self.right = self._clean(msg)

    # ── Control loop ──────────────────────────────────────────────────────────

    def _control_loop(self):
        cmd = Twist()

        if self.left < RESCUE_DIST:
            # ── RESCUE: dangerously close to left wall.
            #    Stop forward motion and spin hard right to create clearance. ──
            cmd.linear.x  = 0.0
            cmd.angular.z = -TURN_SPEED
            state = f'RESCUE left={self.left:.2f}'

        elif self.front < FRONT_BLOCK:
            # ── Obstacle ahead: arc-turn right (small forward component so
            #    robot clears the wall rather than spinning against it) ──────
            cmd.linear.x  = LINEAR_SPEED * 0.25
            cmd.angular.z = -TURN_SPEED
            state = 'TURN_RIGHT'

        elif self.left >= LEFT_FAR:
            # ── No left wall in range: curve left gently to find wall ────────
            cmd.linear.x  = LINEAR_SPEED * 0.7
            cmd.angular.z = TURN_SPEED * 0.5
            state = 'SEEK_WALL'

        else:
            # ── Left wall present: proportional distance control ──────────────
            # error > 0 → too far  → steer left  (+z)
            # error < 0 → too close → steer right (−z)
            error   = self.left - LEFT_IDEAL
            angular = Kp * error
            angular = max(-TURN_SPEED, min(TURN_SPEED, angular))

            cmd.linear.x  = LINEAR_SPEED
            cmd.angular.z = angular
            state = f'FOLLOW left={self.left:.2f} err={error:+.2f}'

        self.cmd_pub.publish(cmd)
        self._tick += 1
        if self._tick % 10 == 0:   # log once per second
            self.get_logger().info(
                f'[{state}]  F={self.front:.2f}  L={self.left:.2f}  R={self.right:.2f}'
                f'  v={cmd.linear.x:.2f}  w={cmd.angular.z:.2f}'
            )


# Shared state: last known good sensor readings, preserved across restarts
_last_front = 3.0
_last_left  = LEFT_IDEAL
_last_right = LEFT_IDEAL


def _run_once():
    """Spin one MazeSolver node until a RuntimeError kills the executor."""
    global _last_front, _last_left, _last_right
    node = MazeSolver(_last_front, _last_left, _last_right)
    executor = rclpy.executors.SingleThreadedExecutor()
    executor.add_node(node)
    try:
        while rclpy.ok():
            executor.spin_once(timeout_sec=0.05)
            # snapshot current readings so next restart inherits them
            _last_front = node.front
            _last_left  = node.left
            _last_right = node.right
    finally:
        executor.shutdown()
        node.destroy_node()


def main():
    import time
    while True:
        rclpy.init()
        stop = False
        try:
            _run_once()
        except RuntimeError:
            pass          # DDS error → full context reset, loop again
        except KeyboardInterrupt:
            stop = True   # user pressed Ctrl+C → clean exit after shutdown
        finally:
            try:
                rclpy.shutdown()
            except Exception:
                pass      # already shut down – ignore
        if stop:
            break
        time.sleep(0.15)  # allow RMW to fully release resources
