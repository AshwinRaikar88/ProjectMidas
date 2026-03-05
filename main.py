import socket
import json
import threading
import time
import sys

from xarm.wrapper import XArmAPI
from fastapi import FastAPI
import uvicorn


# --------------------------------
# Configuration
# --------------------------------

ARM_IP = "192.168.1.188"

TCP_HOST = "0.0.0.0"
TCP_PORT = 5005

HTTP_PORT = 8000


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
        print(line)

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
            x=250,
            y=0,
            z=150,
            roll=180,
            pitch=0,
            yaw=0,
            speed=50,
            wait=True
        )

        return {"status": "ok", "code": code}

    except Exception as e:

        log(f"Reset error: {e}")
        return {"status": "error", "message": str(e)}


def move_robot(cmd):

    try:

        x = float(cmd["x"])
        y = float(cmd["y"])
        z = float(cmd["z"])

        roll = float(cmd.get("roll", 180))
        pitch = float(cmd.get("pitch", 0))
        yaw = float(cmd.get("yaw", 0))
        speed = float(cmd.get("speed", 100))

        log(f"Move command: {x} {y} {z}")

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

        return {"status": "ok", "code": code}

    except Exception as e:

        log(f"Move error: {e}")
        return {"status": "error", "message": str(e)}


def get_status():

    try:

        _, state = arm.get_state()
        _, err = arm.get_err_warn_code()

        return {
            "state": state,
            "error": err
        }

    except Exception as e:

        return {"status": "error", "message": str(e)}


# --------------------------------
# TCP CLIENT HANDLER
# --------------------------------

def client_handler(conn, addr):

    log(f"Client connected: {addr}")

    with conn:

        while True:

            try:

                data = conn.recv(1024)

                if not data:
                    break

                msg = json.loads(data.decode())

                if msg.get("reset"):

                    result = reset_safe_position()

                elif msg.get("status"):

                    result = get_status()

                elif all(k in msg for k in ("x", "y", "z")):

                    result = move_robot(msg)

                else:

                    result = {"error": "unknown command"}

                conn.sendall(json.dumps(result).encode())

            except Exception as e:

                log(f"Client error {addr}: {e}")
                break

    log(f"Client disconnected: {addr}")


# --------------------------------
# TCP SERVER
# --------------------------------

def start_tcp_server():

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    server.bind((TCP_HOST, TCP_PORT))
    server.listen()

    log(f"TCP server running on port {TCP_PORT}")

    while True:

        try:

            conn, addr = server.accept()

            threading.Thread(
                target=client_handler,
                args=(conn, addr),
                daemon=True
            ).start()

        except Exception as e:
            log(f"TCP server error: {e}")
            wait_time = 15
            log(f"Retrying in {wait_time} seconds...")

            for elapsed in range(1, wait_time + 1):
                bar = '=' * elapsed + '-' * (wait_time - elapsed)
                remaining = wait_time - elapsed
                sys.stdout.write(f"\r[{bar}] {remaining} sec{'s' if remaining != 1 else ''} remaining")
                sys.stdout.flush()
                time.sleep(1)
            print()

# --------------------------------
# HTTP MONITORING API
# --------------------------------

app = FastAPI()


@app.get("/")
def root():
    return {"server": "xArm Robot Server"}


@app.get("/status")
def status():
    return get_status()


@app.get("/log")
def logs():
    return {"log": debug_log}

# --------------------------------
# MAIN
# --------------------------------

def main():
    reset_safe_position()
    # start TCP server
    threading.Thread(
        target=start_tcp_server,
        daemon=True
    ).start()

    log("HTTP monitoring server started")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=HTTP_PORT,
        log_config=None
    )

if __name__ == "__main__":
    main()