import gradio as gr
import threading
import time
import json
import socket
from xarm.wrapper import XArmAPI

# ---- Arm setup ----
arm = XArmAPI("192.168.1.188")
arm.connect()
arm.motion_enable(True)
arm.set_mode(0)
arm.set_state(0)
time.sleep(1)


def init_robot():
    # Example: move each joint by angle (degrees)
    # joints = [J1, J2, J3, J4, J5, J6]
    arm.set_servo_angle(angle=[0, 0, 0, 0, 0, 0], speed=100, wait=True)
    # arm.set_servo_angle(angle=[100, 0, 0, 0, 0, 0], speed=50, wait=True)

    # Get current Cartesian position
    pos = arm.get_position(is_radian=False)  # returns [x, y, z, roll, pitch, yaw]

    x, y, z, roll, pitch, yaw = pos[1]  # pos[0] is error code, pos[1] is coords

    # Cartesian mode
    arm.set_mode(0)
    arm.set_state(0)


# ---- Improved error handling ----
def check_and_clear_errors():
    """Check for errors and clear them if present"""
    code, state = arm.get_state()
    code2, err_code = arm.get_err_warn_code()

    if state > 2:  # Error state (3 or 4)
        add_debug(f"[ERROR] Arm in error state: {state}, error code: {err_code}")

        # Clear errors following the documentation
        arm.clean_error()
        time.sleep(0.5)

        # Clear warn code if present
        arm.clean_warn()
        time.sleep(0.1)

        # Re-enable motion
        arm.motion_enable(True)
        time.sleep(0.2)

        # Reset mode to position control
        arm.set_mode(0)
        time.sleep(0.1)

        # Set state to ready
        arm.set_state(0)
        time.sleep(0.5)

        return True, f"Cleared error state {state}, error code {err_code}"

    return False, "No errors detected"


# ---- Arm functions ----
def reset_safe_position():
    """Reset arm to safe position with proper error handling"""
    try:
        # Check and clear any errors first
        had_error, error_msg = check_and_clear_errors()
        if had_error:
            add_debug(f"[RESET] {error_msg}")

        # Move to safe position
        code = arm.set_position(x=250, y=0, z=150, roll=180, pitch=0, yaw=0, speed=50, wait=True)

        if code != 0:
            return f"⚠️ Reset completed with warning code: {code}"

        return "✅ Arm reset successful"
    except Exception as e:
        add_debug(f"[RESET] Exception: {e}")
        return f"❌ Failed to reset arm: {e}"


def safe_set_position(x, y, z, roll=180, pitch=0, yaw=0, speed=100):
    """Move arm with error checking before and after"""
    try:
        # Check state before moving
        code, state = arm.get_state()
        if state > 2:  # In error state
            return f"❌ Arm in error state {state}. Please reset first."

        # Attempt movement
        ret_code = arm.set_position(
            x=float(x), y=float(y), z=float(z),
            roll=float(roll), pitch=float(pitch), yaw=float(yaw),
            speed=float(speed), wait=True
        )

        # Check if movement completed successfully
        if ret_code == 0:
            return f"✅ Moved to position: x={x}, y={y}, z={z}"
        else:
            # Check for errors after failed movement
            code2, err_code = arm.get_err_warn_code()
            add_debug(f"[MOVE] Failed with code {ret_code}, error: {err_code}")
            return f"⚠️ Motion completed with warning code: {ret_code}"

    except Exception as e:
        add_debug(f"[MOVE] Exception: {e}")
        # Check if we're now in error state
        code, state = arm.get_state()
        if state > 2:
            return f"❌ Motion failed - Arm in error state {state}. Use Reset button."
        return f"❌ Motion failed: {e}"


def get_arm_status():
    """Get detailed arm status for monitoring"""
    try:
        code, state = arm.get_state()
        code2, err_code = arm.get_err_warn_code()

        state_desc = {
            1: "Ready",
            2: "Paused",
            3: "Error (stopped)",
            4: "Error (collision)"
        }

        status = f"State: {state_desc.get(state, f'Unknown ({state})')}\n"
        if err_code and err_code[0] != 0:
            status += f"Error Code: {err_code[0]}\n"
        if err_code and err_code[1] != 0:
            status += f"Warning Code: {err_code[1]}\n"

        return status
    except Exception as e:
        return f"Failed to get status: {e}"


# ---- Shared debug log ----
debug_log = []
debug_lock = threading.Lock()


def add_debug(message):
    with debug_lock:
        timestamp = time.strftime("%H:%M:%S")
        debug_log.append(f"[{timestamp}] {message}")
        if len(debug_log) > 100:
            debug_log.pop(0)


def get_debug_log():
    with debug_lock:
        return "\n".join(debug_log)


# ---- TCP server ----
TCP_HOST = "0.0.0.0"
TCP_PORT = 5005


def tcp_client_handler(conn, addr):
    add_debug(f"[TCP] Connection from {addr}")
    with conn:
        while True:
            try:
                data = conn.recv(1024)
                if not data:
                    time.sleep(0.1)
                    continue
                try:
                    msg = json.loads(data.decode())
                except Exception:
                    add_debug(f"[TCP] Invalid JSON from {addr}: {data}")
                    conn.sendall(json.dumps({"error": "Invalid JSON"}).encode())
                    continue

                if msg.get("reset"):
                    add_debug(f"[TCP] Reset command from {addr}")
                    result = reset_safe_position()
                    conn.sendall(json.dumps({"status": result}).encode())

                elif all(k in msg for k in ("x", "y", "z")):
                    add_debug(f"[TCP] Move command from {addr}: {msg}")
                    result = safe_set_position(
                        x=msg["x"], y=msg["y"], z=msg["z"],
                        roll=msg.get("roll", 180),
                        pitch=msg.get("pitch", 0),
                        yaw=msg.get("yaw", 0),
                        speed=msg.get("speed", 100)
                    )
                    conn.sendall(json.dumps({"status": result}).encode())

                elif msg.get("status"):
                    status = get_arm_status()
                    conn.sendall(json.dumps({"status": status}).encode())

                else:
                    add_debug(f"[TCP] Unknown command from {addr}: {msg}")
                    conn.sendall(json.dumps({"error": "Unknown command"}).encode())

            except Exception as e:
                add_debug(f"[TCP] Exception in client {addr}: {e}")
                time.sleep(0.1)

    add_debug(f"[TCP] Connection from {addr} closed")

settings_output_visibility = False

def start_tcp_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((TCP_HOST, TCP_PORT))
    server.listen()
    server.settimeout(1)
    add_debug(f"[TCP] Server listening on {TCP_HOST}:{TCP_PORT}")
    while True:
        try:
            conn, addr = server.accept()
            threading.Thread(target=tcp_client_handler, args=(conn, addr), daemon=True).start()
        except socket.timeout:
            continue


# ---- Settings functions ----
def save_settings(tcp_host, tcp_port, arm_ip, default_speed):
    result = f"Settings saved:\n"
    result += f"TCP Host: {tcp_host}\n"
    result += f"TCP Port: {tcp_port}\n"
    result += f"Arm IP: {arm_ip}\n"
    result += f"Default Speed: {default_speed}"
    add_debug(f"[Settings] Configuration updated")
    return result



# ---- Gradio UI ----
css = """
/* ----------  card look for Haply status  ---------- */
.haply-card {
    background-color: #444;   /* light grey */
    # border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,.12);
}
"""

with gr.Blocks(css=css, title="xArm Controller") as app:
    gr.Markdown("## 🤖 xArm Controller UI (TCP Server for Unity)")

    with gr.Row():
        # Collapsible Sidebar
        with gr.Sidebar(open=False):
            gr.Markdown("###  xARM Menu")

            with gr.Accordion("⚙️ Settings", open=False):
                with gr.Accordion("TCP Configuration", open=False):
                    settings_tcp_host = gr.Textbox(label="TCP Host", value=TCP_HOST)
                    settings_tcp_port = gr.Number(label="TCP Port", value=TCP_PORT)
                with gr.Accordion("Arm Configuration",open=False):
                    settings_arm_ip = gr.Textbox(label="Arm IP Address", value="192.168.1.188")
                    settings_default_speed = gr.Number(label="Default Speed", value=50)

                show_debug = gr.Checkbox(label="Show Debug Log", value=False)

                gr.Markdown("---")
                settings_output = gr.Textbox(label="Info", lines=2, visible=True)
                save_settings_btn = gr.Button("💾 Save", variant="primary")

        # Main content area
        with gr.Column():
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Position Control")

                    x = gr.Slider(label="X", minimum=50, maximum=400, step=1, value=200)
                    y = gr.Slider(label="Y", minimum=-300, maximum=300, step=1, value=0)
                    z = gr.Slider(label="Z", minimum=50, maximum=300, step=1, value=150)
                    roll = gr.Slider(label="Roll", minimum=0, maximum=360, step=1, value=180)
                    pitch = gr.Slider(label="Pitch", minimum=-90, maximum=90, step=1, value=0)
                    yaw = gr.Slider(label="Yaw", minimum=0, maximum=360, step=1, value=0)

                    speed = gr.Slider(label="Speed", minimum=1, maximum=100, step=1, value=50)

                    with gr.Row():
                        move_btn = gr.Button("▶️ Move Arm", variant="primary")
                        reset_btn = gr.Button("🔄 Reset Position", variant="stop")



                with gr.Column():
                        gr.Markdown("### Haply Status", elem_classes="haply-card")

                        gr.Markdown("### xArm Status")
                        output = gr.Textbox(label="Arm Status", lines=6, show_label=False)
                        status_btn = gr.Button("📊 Get Arm Status")

            # Debug log section (conditionally visible)
            debug_section = gr.Column(visible=False)
            with debug_section:
                gr.Markdown("### 🐛 Debug Log")
                debug_output = gr.Textbox(
                    label="Debug Output",
                    lines=12,
                    interactive=False,
                    show_label=False
                )
                refresh_debug_btn = gr.Button("🔄 Refresh Debug Log")


    # Event handlers
    def toggle_debug(show):
        return gr.update(visible=show)


    # Connect events
    show_debug.change(fn=toggle_debug, inputs=[show_debug], outputs=[debug_section])

    save_settings_btn.click(
        fn=save_settings,
        inputs=[settings_tcp_host, settings_tcp_port, settings_arm_ip, settings_default_speed],
        outputs=[settings_output]
    )

    move_btn.click(
        fn=safe_set_position,
        inputs=[x, y, z, roll, pitch, yaw, speed],
        outputs=output
    )

    reset_btn.click(
        fn=reset_safe_position,
        outputs=output
    )

    status_btn.click(
        fn=get_arm_status,
        outputs=output
    )

    refresh_debug_btn.click(
        fn=get_debug_log,
        inputs=None,
        outputs=debug_output
    )

    # Auto-refresh debug log on actions
    move_btn.click(fn=get_debug_log, inputs=None, outputs=debug_output)
    reset_btn.click(fn=get_debug_log, inputs=None, outputs=debug_output)

# ---- Start TCP server in background ----
threading.Thread(target=start_tcp_server, daemon=True).start()

if __name__ == "__main__":
    init_robot()
    app.launch(server_name="0.0.0.0", server_port=9080)