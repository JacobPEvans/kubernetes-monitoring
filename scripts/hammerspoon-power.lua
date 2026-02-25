-- K8s Monitoring Power Management
-- Scales monitoring pods down on battery/low-power and back up on AC.
-- Usage: Add to ~/.hammerspoon/init.lua or require("hammerspoon-power")

local NOTIFY_TITLE = "K8s Monitoring"
local k8sDir = os.getenv("K8S_MONITORING_DIR") or (os.getenv("HOME") .. "/git/kubernetes-monitoring/main")
local stateFile = "/tmp/kubernetes-monitoring-power-state"

local function isLowPowerMode()
  local out = hs.execute("pmset -g 2>/dev/null | grep powermode | awk '{print $2}'")
  return out and out:gsub("%s+", "") == "1"
end

local function shouldSavePower()
  return isLowPowerMode() or hs.battery.powerSource() ~= "AC Power"
end

local function readState()
  local f = io.open(stateFile, "r")
  if not f then return "unknown" end
  local s = f:read("*a")
  f:close()
  if not s or s == "" then return "unknown" end
  return s:gsub("%s+", "")
end

local function writeState(state)
  local f, err = io.open(stateFile, "w")
  if not f then
    hs.notify.show(NOTIFY_TITLE, "Error writing state", tostring(err))
    return
  end
  f:write(state)
  f:close()
end

local function powerChanged()
  local desired = shouldSavePower() and "save" or "full"
  if readState() == desired then return end

  local target = desired == "full" and "full-power" or "power-save"
  local _, ok = hs.execute("make -C '" .. k8sDir .. "' " .. target, true)
  if not ok then
    hs.notify.show(NOTIFY_TITLE, "Error", "Failed to run make " .. target)
    return
  end

  writeState(desired)
  local message = desired == "full"
    and "Restored monitoring (AC power)"
    or "Scaled down monitoring (battery/low power)"
  hs.notify.show(NOTIFY_TITLE, "", message)
end

-- Instant trigger on power source change
local k8sBatteryWatcher = hs.battery.watcher.new(powerChanged)
k8sBatteryWatcher:start()

-- Poll for Low Power Mode changes (not covered by battery watcher).
-- Assigned to a local to prevent garbage collection.
local k8sPowerTimer = hs.timer.doEvery(60, powerChanged)

-- Sync state on load
powerChanged()
