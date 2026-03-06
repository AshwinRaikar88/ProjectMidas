import socket
import json
import re
import threading
import time
import sys

from xarm.wrapper import XArmAPI
from fastapi import FastAPI
import uvicorn


# --------------------------------
# Configuration
# --------------------------------

ARM_IP    = "192.168.1.188"
TCP_HOST  = "0.0.0.0"
TCP_PORT  = 5005
HTTP_PORT = 8000


# --------------------------------
# Debug logging
# --------------------------------

debug_log = []
log_lock  = threading.Lock()


def log(message):
    with log_lock:
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        debug_log.append(line)
        print(line, flush=True)
        if len(debug_log) > 200:
            debug_log.pop(0)


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

# Make sure vacuum is off at startup
arm.set_vacuum_gripper(False)
log("Vacuum gripper initialized (off)")


# --------------------------------
# Active client tracking
# --------------------------------

active_client_lock = threading.Lock()
active_client_addr = None


# --------------------------------
# Robot control functions
# --------------------------------

def reset_safe_position():
    try:
        log("Reset command received")
        arm.clean_error()
        arm.clean_warn()
        arm.motion_enable(True)
        arm.set_mode(0)
        arm.set_state(0)
        code = arm.set_position(
            x=250, y=0, z=150,
            roll=180, pitch=0, yaw=0,
            speed=50, wait=True
        )
        return {"status": "ok", "code": code}
    except Exception as e:
        log(f"Reset error: {e}")
        return {"status": "error", "message": str(e)}


def init_robot():
    arm.set_servo_angle(angle=[0, 0, 0, 0, 0, 0], speed=100, wait=True)
    arm.set_servo_angle(angle=[100, 0, 0, 0, 0, 0], speed=50, wait=True)
    arm.set_mode(0)
    arm.set_state(0)


def move_robot(cmd):
    try:
        x     = float(cmd["x"])
        y     = float(cmd["y"])
        z     = float(cmd["z"])
        roll  = float(cmd.get("roll",  180))
        pitch = float(cmd.get("pitch",   0))
        yaw   = float(cmd.get("yaw",     0))
        speed = float(cmd.get("speed", 100))
        log(f"Move command: {x:.1f} {y:.1f} {z:.1f}")
        code = arm.set_position(
            x=x, y=y, z=z,
            roll=roll, pitch=pitch, yaw=yaw,
            speed=speed, wait=True
        )
        return {"status": "ok", "code": code}
    except Exception as e:
        log(f"Move error: {e}")
        return {"status": "error", "message": str(e)}


def vacuum_on():
    """Activate vacuum — suck / grab."""
    try:
        log("Vacuum: ON (grab)")
        code = arm.set_vacuum_gripper(True)
        return {"status": "ok", "vacuum": "on", "code": code}
    except Exception as e:
        log(f"Vacuum on error: {e}")
        return {"status": "error", "message": str(e)}


def vacuum_off():
    """Deactivate vacuum — release."""
    try:
        log("Vacuum: OFF (release)")
        code = arm.set_vacuum_gripper(False)
        return {"status": "ok", "vacuum": "off", "code": code}
    except Exception as e:
        log(f"Vacuum off error: {e}")
        return {"status": "error", "message": str(e)}


def get_status():
    try:
        _, state = arm.get_state()
        _, err   = arm.get_err_warn_code()
        return {"state": state, "error": err}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# --------------------------------
# Framing  (newline-delimited JSON)
# --------------------------------

def send_json(conn, payload: dict):
    conn.sendall((json.dumps(payload) + "\n").encode())


def parse_frame(raw_line: bytes):
    """Returns (dict, None) on success or (None, error_string) on failure."""
    text = raw_line.strip().decode("utf-8", errors="replace")
    if not text:
        return None, "empty frame"

    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        pass

    # Handle NaN / Infinity from C# without disconnecting
    sanitized = re.sub(r'\bNaN\b|\bInfinity\b|\b-Infinity\b', '"__BAD__"', text)
    try:
        obj = json.loads(sanitized)
        bad_keys = [k for k, v in obj.items() if v == "__BAD__"]
        if bad_keys:
            return None, f"NaN/Infinity in fields: {bad_keys} (frame skipped)"
        return obj, None
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}  raw={text[:80]}"


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

    conn.settimeout(30)

    # ── Duplicate guard ────────────────────────────────────────────────────
    with active_client_lock:
        if active_client_addr is not None:
            log(f"Rejected duplicate from {addr}  (active: {active_client_addr})")
            try:
                send_json(conn, {
                    "connected": False,
                    "reason":  "duplicate",
                    "message": f"Already connected: {active_client_addr[0]}:{active_client_addr[1]}"
                })
            except Exception:
                pass
            conn.close()
            return
        active_client_addr = addr

    # ── Welcome ────────────────────────────────────────────────────────────
    log(f"Client connected: {addr}")
    try:
        send_json(conn, {
            "connected": True,
            "message":  f"xArm server online. Welcome {addr[0]}:{addr[1]}",
            "arm_ip":    ARM_IP
        })
    except Exception as e:
        log(f"Welcome failed for {addr}: {e}")
        with active_client_lock:
            active_client_addr = None
        conn.close()
        return

    # ── Command loop ───────────────────────────────────────────────────────
    with conn:
        for msg, err in iter_messages(conn):

            if err:
                log(f"Skipped bad frame from {addr}: {err}")
                continue

            # Vacuum gripper commands
            if msg.get("gripper") == "grab":
                result = vacuum_on()

            elif msg.get("gripper") == "release":
                result = vacuum_off()

            # Motion commands
            elif msg.get("reset"):
                result = reset_safe_position()

            elif msg.get("status"):
                result = get_status()

            elif all(k in msg for k in ("x", "y", "z")):
                result = move_robot(msg)

            else:
                result = {"error": "unknown command"}

            try:
                send_json(conn, result)
            except Exception as e:
                log(f"Send error to {addr}: {e}")
                break

    with active_client_lock:
        active_client_addr = None
    log(f"Client disconnected: {addr}")


# --------------------------------
# TCP SERVER
# --------------------------------

def start_tcp_server():
    server = None
    while True:
        if server is None:
            try:
                server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.settimeout(None)   # override any XArmAPI global timeout
                server.bind((TCP_HOST, TCP_PORT))
                server.listen(5)
                log(f"TCP server listening on :{TCP_PORT}")
            except Exception as e:
                log(f"TCP bind/listen failed: {e} — retrying in 5s")
                if server:
                    try: server.close()
                    except Exception: pass
                    server = None
                time.sleep(5)
                continue

        try:
            conn, addr = server.accept()
            threading.Thread(
                target=client_handler,
                args=(conn, addr),
                daemon=True
            ).start()
        except OSError as e:
            log(f"accept() error: {e} — recreating server socket")
            try: server.close()
            except Exception: pass
            server = None
            time.sleep(1)


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


# --------------------------------
# MAIN
# --------------------------------

def main():
    reset_safe_position()
    init_robot()
    threading.Thread(target=start_tcp_server, daemon=True).start()
    log("HTTP monitoring server started")
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT, log_config=None)


if __name__ == "__main__":
    main()