# robot-ong-do
AI-powered Vietnamese calligraphy robot demo using Fairino FR3 Cobot

# AI Calligraphy Robot FR3

This project is a recruitment/open-day demo using a Fairino FR5 cobot to write Vietnamese calligraphy based on user selection.

## Concept

Users select a Vietnamese calligraphy word from a web interface. The system loads a pre-designed SVG file, converts the SVG path into robot trajectory points, maps the points into the robot workspace, performs safety checks, and sends commands to the robot.

## Demo Words

- TÃ¢m
- Tri thá»©c
- SÃ¡ng táº¡o
- TÆ°Æ¡ng lai
- CÃ´ng nghá»‡
- KhÃ¡t vá»ng

## System Pipeline

User selection  
â†’ Load SVG  
â†’ Parse SVG path  
â†’ Sample Bezier curves  
â†’ Scale to paper size  
â†’ Map to robot coordinates  
â†’ Safety check  
â†’ Send trajectory to Fairino FR5  

## Tech Stack

- Python
- svgpathtools
- NumPy
- OpenCV
- Streamlit
- Fairino SDK/API

## Project Structure

```text
assets/             SVG files and preview images
config/             Robot and paper configuration
src/                Main source code
outputs/            Generated trajectories and logs
tests/              Unit tests
docs/               Project documentation
```

## Fairino FR3 safe air-line demo

Run from project root:

```powershell
cd D:\robot-ong-do
.venv\Scripts\activate

python tests\test_import_fairino.py
python tests\test_robot_connection.py
python tests\test_robot_xmlrpc_status.py
python tests\test_robot_raw_xmlrpc_status.py
python tests\test_draw_line_air.py
python tests\test_draw_line_measured_paper_air.py
python tests\test_draw_line_measured_paper_raw_xmlrpc.py
python tests\test_gripper_connection.py
python tests\test_gripper_ping.py
python tests\test_gripper_485_diagnostics.py
python tests\test_gripper_setup_tool_end.py
python tests\test_gripper_open_close.py
python tests\test_tool_do0_gripper.py
```

Safety rules:

- `config/robot_config.json` keeps `"enable_robot_move": false` by default.
- With movement disabled, `test_draw_line_air.py` only validates and prints the planned trajectory.
- Only set `"enable_robot_move": true` after Emergency Stop is released, alarms are cleared, robot is enabled, WebApp jog has been tested, and SDK connection/ports are OK.
- Do not run unknown poses.
- Do not lower Z before paper/table calibration.
- The first demo only draws one straight line in the air. It does not touch paper and does not use a gripper or pen.
- For FR3 controllers that expose `20003` and `20004` but not `20005`, keep `allow_xmlrpc_motion_when_cnde_unavailable` false until XML-RPC status reads are verified and the robot is physically ready.
- Raw XML-RPC motion is a compatibility path for this FR3 V6 controller. It requires both `"enable_robot_move": true` and `"allow_raw_xmlrpc_motion": true`.
- The JODELL EPG40-050 gripper has its own safety lock. `test_gripper_open_close.py` only previews until `gripper.enable_gripper_motion` is true.
- Before enabling gripper motion, keep fingers and the pen clear of the jaws, confirm 24V tool-end power, and confirm the configured Fairino gripper vendor/device matches the actual gripper.
- If the gripper is wired as a simple valve/relay on tool DO0, use `python tests\test_tool_do0_gripper.py`. This sends `SetToolDO(id=0, status=1)` to close and `SetToolDO(id=0, status=0)` to open only after `tool_do_gripper.enable_tool_do_gripper=true` and `--apply`.

Gripper notes:

- The mounted gripper label reads `JODELL EPG40-050`, `24V`, max current about `0.85A`.
- The first connection test uses Fairino's built-in gripper XML-RPC methods: `GetGripperConfig`, `SetGripperConfig`, `ActGripper`, and `MoveGripper`.
- `config/robot_config.json` currently uses `company=4`, `device=0` because a Fairino SDK gripper example uses that pair. If activation still returns an error, run `python tests\test_gripper_menu.py --action scan_config --apply` to compare the built-in Fairino gripper drivers, or use the vendor tool-end Lua protocol file.
- If WebApp shows `Gripper 485 timeout`, run `python tests\test_gripper_485_diagnostics.py` and keep `gripper.enable_gripper_motion=false`. This usually means the controller cannot talk to the gripper over tool-end RS485: power, A/B wiring, baud rate, address, vendor/device, or end Lua/protocol setup is wrong.
- To configure tool-end RS485/Lua gripper path without moving the gripper, first preview with `python tests\test_gripper_setup_tool_end.py`, then apply with `python tests\test_gripper_setup_tool_end.py --apply`.

Paper calibration notes:

- Step 1: jog robot to the upper-left paper corner, then save `origin_x`, `origin_y`, and `paper_z`.
- Step 2: measure the real paper `width_mm` and `height_mm`.
- Step 3: set a safe `margin_mm`.
- Step 4: run the air-line test first.
- Step 5: only after the air test is safe, test write Z offsets.
