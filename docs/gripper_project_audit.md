# Gripper Project Audit: Fairino FR3 + JODELL EPG40-050

Date: 2026-05-23

## Scope

This audit covers the existing Fairino FR3 robot project and the requested integration path:

Fairino FR3 -> RS485 / Modbus RTU -> JODELL EPG40-050 C7 gripper.

No existing project file was deleted during this audit. Old test files are candidates for archive, not deletion.

## Manual Findings

Source manual reviewed: `C:\Users\anhkh\Downloads\1776654784787_译文_202605111248.pdf`.

Confirmed from the PDF:

- Physical interface: RS485.
- Protocol: Modbus RTU.
- Default serial setting: 115200 baud, 8 data bits, 1 stop bit, no parity, no flow control.
- Control register first address: `0x03E8`.
- Status register first address: `0x07D0`.
- Supported function codes: `0x03`, `0x04`, `0x06`, `0x10`.
- Device address range: `1..247`; examples use slave/station address `0x09`.
- Modbus RTU frame order: slave address, function code, data bytes, CRC16 low byte then high byte.

### Control Register Map

- `0x03E8` low byte: main control register.
  - bit 0 `rACT`: `0` reset/disable, `1` enable.
  - bit 1 `rMODE`: `0` parameter mode, `1` parameter-free mode.
  - bit 2 `rSTOP`: emergency stop.
  - bit 3 `rGTO`: move to target.
  - Parameter mode motion uses `0x0009` (`rACT + rGTO`).
- `0x03E8` high byte: parameter-free instruction code when `rMODE=1`.
- `0x03E9` high byte: dynamic target position.
  - `0x00` fully open.
  - `0xFF` fully closed.
  - `0x03E9` low byte is kept/reserved as `0x00`.
- `0x03EA` low byte: dynamic speed.
  - `0x00` minimum stable speed.
  - `0xFF` maximum speed.
- `0x03EA` high byte: dynamic force/current limit.
  - `0x00` minimum stable force.
  - `0xFF` maximum force.

### Status Register Map

Read status via function code `0x04`.

- `0x07D0` low byte: gripper status.
  - bit 0 `gACT`: enabled.
  - bit 1 `gDropSta`: workpiece dropped.
  - bit 2 `gMODE`: parameter or parameter-free mode.
  - bit 3 `gGTO`: moving to target.
  - bits 4-5 `gSTA`: `0` reset/inspection, `1` activating, `3` activation completed.
  - bits 6-7 `gOBJ`: object/motion result.
- `0x07D1` low byte: fault byte.
- `0x07D1` high byte: current position.
- `0x07D2` low byte: current speed.
- `0x07D2` high byte: force/current status.
- `0x07D3` low byte: bus voltage.
- `0x07D3` high byte: ambient temperature.

### Confirmed Example Commands

- Reset/clear `rACT`: write `0x03E8 = 0x0000`.
- Enable: write `0x03E8 = 0x0001`.
- Close full speed/full force: write 3 registers from `0x03E8`:
  - `0x03E8 = 0x0009`
  - `0x03E9 = 0xFF00`
  - `0x03EA = 0xFFFF`
- Open full speed/full force: write 3 registers from `0x03E8`:
  - `0x03E8 = 0x0009`
  - `0x03E9 = 0x0000`
  - `0x03EA = 0xFFFF`

Project defaults should not use full force. Safe first tests should use:

- Open: position `0x00`, speed `0x20`, force `0x20`.
- Close: position `0x80` or `0xA0`, speed `0x20`, force `0x20`.

## Project Inventory

### Robot Core / Fairino SDK

Keep:

- `fairino-python-sdk/windows/fairino/Robot.py`: vendor SDK wrapper.
- `fairino-python-sdk/windows/libfairino/Robot.cp310-win_amd64.pyd`: Windows SDK binary.
- `modules/sdk_path.py`: useful SDK path/DLL setup helper.
- `modules/fairino_controller.py`: existing safe Fairino motion wrapper.
- `modules/fairino_raw_controller.py`: raw XML-RPC compatibility wrapper; dangerous if motion flags are enabled.
- `src/calibration/fairino_client.py`: currently empty; good target for a cleaned wrapper.

### Existing Gripper Files

Can reuse:

- `modules/jodell_epg_modbus.py`: useful CRC/frame builder. It is frame-only and does not manage a serial port.
- `modules/fairino_gripper.py`: useful for diagnosing Fairino built-in gripper XML-RPC and tool-end Lua settings.
- `modules/tool_do_gripper.py`: useful only if the gripper is wired as simple IO, not the preferred RS485 Modbus path.
- `config/robot_config.json`: contains current robot IP and gripper metadata.

Needs replacement or refactor:

- `tests/test_gripper_menu.py`: too broad; mixes Fairino built-in gripper API, Lua setup, Modbus passthrough, and sensor bridge experiments.
- `tests/test_gripper_open_close.py`: sends Fairino `ActGripper`/`MoveGripper` when flags are enabled; not the preferred direct Modbus path.
- `tests/test_gripper_enable_funcs.py`: writes tool-end Lua/function settings.
- `tests/test_gripper_setup_tool_end.py`: writes Fairino tool-end Lua settings with `--apply`; keep only as legacy diagnostic.
- `tests/test_gripper_upload_lua.py`: can upload Lua to robot; should be archived until a proven vendor Lua file is available.
- `config/lua/AXLE_LUA_End_DaHuan.lua`: demo Lua calls `ActGripper`/`MoveGripper`; not a JODELL register-level Lua protocol file.

### Old Tests To Archive

Recommended move to `archive/old_tests/`:

- `tests/test_gripper_485_diagnostics.py`
- `tests/test_gripper_connection.py`
- `tests/test_gripper_enable_funcs.py`
- `tests/test_gripper_menu.py`
- `tests/test_gripper_open_close.py`
- `tests/test_gripper_ping.py`
- `tests/test_gripper_setup_tool_end.py`
- `tests/test_gripper_upload_lua.py`
- `tests/test_tool_do0_gripper.py`

Keep robot/safety/SVG tests where they are:

- `tests/test_import_fairino.py`
- `tests/test_robot_connection.py`
- `tests/test_robot_raw_xmlrpc_status.py`
- `tests/test_robot_xmlrpc_status.py`
- `tests/test_safety_check.py`
- `tests/test_svg_loader.py`
- `tests/test_trajectory_builder.py`

### Dangerous Or Easy-To-Misuse Files

- `tests/testmove.py`: robot motion test; must remain guarded.
- `tests/test_draw_*raw_xmlrpc.py`: can move the robot if config flags allow.
- `modules/fairino_raw_controller.py`: raw `MoveJ`/`MoveL` path; safe only with explicit flags and verified workspace.
- `tests/test_gripper_open_close.py`: can close gripper through Fairino gripper API.
- `tests/test_gripper_menu.py`: can send several kinds of gripper writes with `--apply`.
- `tests/test_gripper_enable_funcs.py`: writes tool-end Lua/function configuration.
- `tests/test_gripper_upload_lua.py`: uploads/configures Lua on the controller.
- `config/robot_config.json`: currently has `enable_robot_move=true`, `allow_raw_xmlrpc_motion=true`, `gripper.enable_gripper_motion=true`, and `allow_raw_xmlrpc_gripper=true`; this is unsafe for casual testing.

## Proposed Architecture

Create a direct Modbus RTU gripper stack independent of Fairino built-in gripper drivers:

```text
src/
  robot/
    fairino_client.py
  gripper/
    jodell_epg40_modbus.py
    jodell_registers.py
    serial_config.py
  demos/
    gripper_menu.py
    robot_gripper_demo.py
  utils/
    logger.py
config/
  gripper_config.yaml
docs/
  gripper_project_audit.md
  jodell_epg40_modbus_notes.md
archive/
  old_tests/
```

Primary control path:

1. Open PC/USB-RS485 serial port.
2. Reset gripper with `0x03E8 = 0x0000`.
3. Enable gripper with `0x03E8 = 0x0001`.
4. Poll `0x07D0` until enabled/activation complete.
5. Move with function `0x10` writing 3 registers:
   - `0x03E8 = 0x0009`
   - `0x03E9 = position << 8`
   - `0x03EA = force << 8 | speed`
6. Poll `0x07D0..0x07D2` to observe status, fault, position, speed, and current/force.

Lua is not required for this direct PC-to-gripper RS485 path. If later the gripper must be controlled through the Fairino tool-end RS485 port and WebApp gripper abstraction, write a separate `AXLE_LUA_End_Jodell_EPG40_050.lua` only after confirming Fairino's Lua raw Modbus API names from official controller docs or a vendor example.

## Safe Test Plan

1. Bench test with the gripper mounted securely, jaws clear, 24V current-limited if possible.
2. Confirm wiring:
   - Brown: +24V.
   - Blue: 0V/GND.
   - White: 485A.
   - Black: 485B.
   - Gray: 485GND optional/reference, not PE.
3. Run read-only connection/status first.
4. Reset and enable only after status read is stable.
5. Open safe: position `0x00`, speed `0x20`, force `0x20`.
6. Close safe only on a test object: position `0x80`, speed `0x20`, force `0x20`.
7. Never start with `0xFF` force.
8. If LED shows blue slow blink, check RS485 polling, A/B wiring, slave ID, and baud rate.
9. If LED shows blue 1 Hz blink, stop and inspect command frame/register values.

## Files To Create

- `src/gripper/jodell_registers.py`
- `src/gripper/serial_config.py`
- `src/gripper/jodell_epg40_modbus.py`
- `src/demos/gripper_menu.py`
- `src/demos/robot_gripper_demo.py`
- `src/robot/fairino_client.py`
- `src/utils/logger.py`
- `config/gripper_config.yaml`
- `docs/jodell_epg40_modbus_notes.md`

## Files To Move Into Archive

Move after this report exists:

- `tests/test_gripper_*.py`
- `tests/test_tool_do0_gripper.py`

## Files Proposed For Later Deletion

Do not delete now. After the new menu has been hardware-tested, consider deleting or keeping only as reference:

- `config/lua/AXLE_LUA_End_DaHuan.lua` if no longer used.
- Archived old gripper tests after the new direct Modbus flow is verified.

## Residual Unknowns

- Hardware was not connected during audit, so serial communication and exact slave ID cannot be verified.
- The PDF confirms device ID is configurable and examples use `09`, but the actual gripper may have been changed.
- Fairino tool-end Lua raw Modbus function names were not confirmed from the provided PDF; therefore Lua should remain optional and manual-only.
