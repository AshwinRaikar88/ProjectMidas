import socket
import json
import threading
import time
import subprocess
import os
import sys
import yaml
import atexit

from xarm.wrapper import XArmAPI
from fastapi import FastAPI
import uvicorn


# --------------------------------
# Resolve application base path
# --------------------------------

def get_base_path():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


BASE_PATH = get_base_path()
CONFIG_PATH = os.path.join(BASE_PATH, "config", "config.yaml")


# --------------------------------
# Load configuration
# --------------------------------

def load_config():

    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG = load_config()


# --------------------------------
# Configuration values
# --------------------------------

ARM_IP = CONFIG["robot"]["arm_ip"]

TCP_HOST = CONFIG["network"]["tcp_host"]
TCP_PORT = CONFIG["network"]["tcp_port"]
HTTP_PORT = CONFIG["network"]["http_port"]

CSHARP_EXE_PATH = CONFIG["csharp_app"]["exe_path"]
CSHARP_ARGS = CONFIG["csharp_app"]["args"]
AUTO_RESTART_CSHARP = CONFIG["csharp_app"]["auto_restart"]

SAFE_POS = CONFIG["robot_defaults"]["safe_position"]

MAX_LOG_LINES = CONFIG["logging"]["max_lines"]


# --------------------------------
# Debug logging
# --------------------------------

debug_log = []
log_lock = threading.Lock()


def log(message):

    with log_lock:

        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"

        debug_log.append(line)

        print(line, flush=True)

        if len(debug_log) > MAX_LOG_LINES:
            debug_log.pop(0)


log(f"Using config file: {CONFIG_PATH}")


# --------------------------------
# Robot initialization
# --------------------------------

print("Connecting to xArm...")

arm = XArmAPI(ARM_IP)

arm.connect()
arm.motion_enable(True)
arm.set_mode(0)
arm.set_state(0)

time.sleep(1)

print("xArm connected.")

arm.set_vacuum_gripper(False)

log("Vacuum gripper initialized (off)")


# --------------------------------
# Active client tracking
# --------------------------------

active_client_lock = threading.Lock()
active_client_addr = None


# --------------------------------
# C# application launcher
# --------------------------------

csharp_process = None
csharp_lock = threading.Lock()


def is_process_running(process_name):

    try:
        result = subprocess.run(
            ["tasklist"],
            capture_output=True,
            text=True
        )

        return process_name.lower() in result.stdout.lower()

    except Exception as e:
        log(f"Process check failed: {e}")
        return False


def launch_csharp_app():

    global csharp_process

    try:

        exe_path = CSHARP_EXE_PATH
        if not os.path.isabs(exe_path):
            exe_path = os.path.join(BASE_PATH, exe_path)

        if not os.path.exists(exe_path):
            log(f"C# exe not found: {exe_path}")
            return

        exe_name = os.path.basename(exe_path)

        # Check if already running
        try:
            result = subprocess.run(["tasklist"], capture_output=True, text=True)
            running = any(exe_name.lower() == line.split()[0].lower()
                          for line in result.stdout.splitlines())
        except Exception as e:
            log(f"Process check failed: {e}")
            running = False

        if running:
            log(f"C# app already running: {exe_name}")
            return

        # Prepare args
        args = CSHARP_ARGS or []
        if isinstance(args, str):
            args = args.split()
        cmd = [exe_path] + args

        log(f"Launching C# app: {' '.join(cmd)}")

        proc = subprocess.Popen(cmd, cwd=os.path.dirname(exe_path))

        with csharp_lock:
            csharp_process = proc

        log(f"C# app started (PID={proc.pid})")

        threading.Thread(target=monitor_csharp_process, args=(proc,), daemon=True).start()

    except Exception as e:
        log(f"ERROR launching C# app: {e}")

def monitor_csharp_process(proc):

    global csharp_process

    try:

        proc.wait()

        exit_code = proc.returncode

        log(f"C# app exited with code {exit_code}")

    except Exception as e:
        log(f"C# monitor error: {e}")

    finally:

        with csharp_lock:
            csharp_process = None

        if AUTO_RESTART_CSHARP:

            log("Restarting C# app in 15 seconds...")

            time.sleep(15)

            launch_csharp_app()


def stop_csharp_app():

    global csharp_process

    with csharp_lock:

        if csharp_process and csharp_process.poll() is None:

            log("Stopping C# application")

            try:
                csharp_process.terminate()
                csharp_process.wait(timeout=5)

            except subprocess.TimeoutExpired:

                log("Force killing C# application")

                csharp_process.kill()

        csharp_process = None


atexit.register(stop_csharp_app)


# --------------------------------
# Robot control
# --------------------------------

def reset_safe_position():

    try:

        log("Reset: moving to safe position")

        arm.clean_error()
        arm.clean_warn()

        arm.motion_enable(True)
        arm.set_mode(0)
        arm.set_state(0)

        code = arm.set_position(
            x=SAFE_POS["x"],
            y=SAFE_POS["y"],
            z=SAFE_POS["z"],
            roll=SAFE_POS["roll"],
            pitch=SAFE_POS["pitch"],
            yaw=SAFE_POS["yaw"],
            speed=SAFE_POS["speed"],
            wait=True
        )

        return {"status": "ok", "reached": True, "code": code}

    except Exception as e:

        log(f"Reset error: {e}")

        return {"status": "error", "reached": False, "message": str(e)}


def init_robot():

    arm.set_servo_angle(angle=[0, 0, 0, 0, 0, 0], speed=100, wait=True)
    arm.set_servo_angle(angle=[100, 0, 0, 0, 0, -90], speed=50, wait=True)
    arm.set_servo_angle(angle=[95, 15, 21, 0, 4, -5], speed=50, wait=True)

    arm.set_mode(0)
    arm.set_state(0)


def move_robot(cmd):

    try:

        x = float(cmd["x"])
        y = float(cmd["y"])
        z = float(cmd["z"])

        roll = float(cmd.get("roll", 180))
        pitch = float(cmd.get("pitch", 0))
        yaw = float(cmd.get("yaw", 90))
        speed = float(cmd.get("speed", 100))

        log(f"Moving to: x={x:.1f} y={y:.1f} z={z:.1f}")

        code = arm.set_position(
            x=x,
            y=y,
            z=z,
            roll=roll,
            pitch=pitch,
            yaw=yaw,
            speed=speed,
            wait=True
        )

        log(f"Reached: x={x:.1f} y={y:.1f} z={z:.1f}")

        return {
            "status": "ok",
            "reached": True,
            "x": x,
            "y": y,
            "z": z,
            "code": code
        }

    except Exception as e:

        log(f"Move error: {e}")

        return {"status": "error", "reached": False, "message": str(e)}


def vacuum_on():

    try:

        log("Vacuum: ON")

        code = arm.set_vacuum_gripper(True)

        return {"status": "ok", "vacuum": "on", "code": code}

    except Exception as e:

        log(f"Vacuum on error: {e}")

        return {"status": "error", "message": str(e)}


def vacuum_off():

    try:

        log("Vacuum: OFF")

        code = arm.set_vacuum_gripper(False)

        return {"status": "ok", "vacuum": "off", "code": code}

    except Exception as e:

        log(f"Vacuum off error: {e}")

        return {"status": "error", "message": str(e)}


def terminate_server():
    """
    Terminates the Python server process gracefully.
    """
    log("Received terminate command. Exiting Python server...")
    # Optionally stop C# app if running
    stop_csharp_app()
    reset_safe_position()

    # Give logs a moment to flush
    time.sleep(0.5)

    # Exit process
    os._exit(0)  # Force exit immediately
    # or: sys.exit(0)  # Graceful exit (might hang if threads block)

def get_status():

    try:

        _, state = arm.get_state()
        _, err = arm.get_err_warn_code()

        return {"state": state, "error": err}

    except Exception as e:

        return {"status": "error", "message": str(e)}


# --------------------------------
# Framing
# --------------------------------

def send_json(conn, payload):

    conn.sendall((json.dumps(payload) + "\n").encode())


def parse_frame(raw_line):

    text = raw_line.strip().decode("utf-8", errors="replace")

    try:
        return json.loads(text), None

    except json.JSONDecodeError as e:
        return None, str(e)


def iter_messages(conn):

    buf = b""

    while True:

        try:
            chunk = conn.recv(4096)

        except OSError:
            return

        if not chunk:
            return

        buf += chunk

        while b"\n" in buf:

            line, buf = buf.split(b"\n", 1)

            if line.strip():
                yield parse_frame(line)


# --------------------------------
# TCP CLIENT HANDLER
# --------------------------------

def client_handler(conn, addr):

    global active_client_addr

    conn.settimeout(60)

    with active_client_lock:

        if active_client_addr is not None:

            log(f"Rejected duplicate from {addr}")

            conn.close()

            return

        active_client_addr = addr

    log(f"Client connected: {addr}")

    try:

        send_json(conn, {
            "connected": True,
            "message": "xArm server online",
            "arm_ip": ARM_IP
        })

    except Exception as e:

        log(f"Welcome send failed: {e}")

        conn.close()

        with active_client_lock:
            active_client_addr = None

        return

    with conn:

        for msg, err in iter_messages(conn):

            if err:
                log(f"Bad frame from {addr}: {err}")
                continue

            if msg.get("gripper") == "grab":
                result = vacuum_on()

            elif msg.get("gripper") == "release":
                result = vacuum_off()

            elif msg.get("reset"):
                result = reset_safe_position()

            elif msg.get("status"):
                result = get_status()

            elif msg.get("terminate_server"):
                print("Received terminate command from client")
                result = {"status": "ok", "message": "Python server terminating"}
                send_json(conn, result)
                terminate_server()  # immediately terminates server
                return

            elif all(k in msg for k in ("x", "y", "z")):
                result = move_robot(msg)

            else:
                result = {"error": "unknown command"}

            send_json(conn, result)

    with active_client_lock:
        active_client_addr = None

    log(f"Client disconnected: {addr}")


# --------------------------------
# TCP SERVER
# --------------------------------

def start_tcp_server():

    server = None

    while True:

        try:

            if server is None:

                server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

                server.bind((TCP_HOST, TCP_PORT))
                server.listen(5)

                server.settimeout(None)

                log(f"TCP server listening on :{TCP_PORT}")

            conn, addr = server.accept()

            threading.Thread(
                target=client_handler,
                args=(conn, addr),
                daemon=True
            ).start()

        except TimeoutError:
            continue

        except OSError as e:

            log(f"TCP server error: {e}")

            try:
                server.close()
            except:
                pass

            server = None

            time.sleep(2)


# --------------------------------
# HTTP MONITORING API
# --------------------------------

app = FastAPI()


@app.get("/")
def root():
    return {"server": "xArm Robot Server"}


@app.get("/status")
def http_status():

    s = get_status()

    with active_client_lock:

        s["active_client"] = (
            f"{active_client_addr[0]}:{active_client_addr[1]}"
            if active_client_addr else None
        )

    return s


@app.get("/log")
def http_logs():
    return {"log": debug_log}


@app.post("/restart_client")
def restart_client():

    stop_csharp_app()
    launch_csharp_app()

    return {"status": "restarted"}


# --------------------------------
# MAIN
# --------------------------------

def main():

    print("Starting Robo Server")
    print("=" * 20)

    reset_safe_position()
    init_robot()

    launch_csharp_app()

    threading.Thread(target=start_tcp_server, daemon=True).start()

    log("HTTP monitoring server started")

    try:
        uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT, log_config=None)

    finally:

        stop_csharp_app()


if __name__ == "__main__":
    main()