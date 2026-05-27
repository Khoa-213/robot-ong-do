-- setup_jodell_gripper.lua
-- FAIRINO FR Lua test script for JODELL EPG40-050 / EPG Series gripper
-- Use after configuring the gripper in the teach pendant / web UI as Gripper index 1.
-- Safe first test: low speed, low force, non-blocking movement.

function jodell_init()
    -- Reset gripper
    ActGripper(1, 0)
    WaitMs(1000)

    -- Activate gripper
    ActGripper(1, 1)
    WaitMs(1000)
end

function jodell_open()
    -- MoveGripper(index, pos, vel, force, max_time, block)
    -- pos: 0-100%, vel: 0-100%, force: 0-100%, max_time: ms
    -- block: 0 = blocking, 1 = non-blocking
    MoveGripper(1, 100, 20, 20, 3000, 0)
end

function jodell_close_soft()
    -- Soft close for testing / holding a pen lightly
    MoveGripper(1, 20, 15, 15, 3000, 0)
end

function jodell_close_mid()
    -- Medium close; use carefully
    MoveGripper(1, 10, 20, 30, 3000, 0)
end

-- Run demo
jodell_init()
jodell_open()
WaitMs(1000)
jodell_close_soft()
WaitMs(1000)
jodell_open()
