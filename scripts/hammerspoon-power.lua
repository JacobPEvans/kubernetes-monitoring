-- K8s Monitoring Power Management
-- Add to ~/.hammerspoon/init.lua or require("hammerspoon-power")
local k8sDir = os.getenv("HOME") .. "/git/kubernetes-monitoring/main"
local stateFile = "/tmp/kubernetes-monitoring-power-state"

local function isLowPowerMode()
  local out = hs.execute("pmset -g 2>/dev/null | grep powermode | awk '{print $2}'")
  return out and out:match("1") ~= nil
end

local function getPowerState()
  if isLowPowerMode() or hs.battery.powerSource() ~= "AC Power" then
    return "save"
  end
  return "full"
end

local function readState()
  local f = io.open(stateFile, "r")
  if f then local s = f:read("*a"); f:close(); return s:gsub("%s+", "") end
  return "unknown"
end

local function writeState(state)
  local f = io.open(stateFile, "w"); f:write(state); f:close()
end

local function powerChanged()
  local desired = getPowerState()
  if readState() == desired then return end
  local target = desired == "full" and "full-power" or "power-save"
  hs.execute("make -C " .. k8sDir .. " " .. target, true)
  writeState(desired)
  hs.notify.show("K8s Monitoring", "", desired == "full"
    and "Restored monitoring (AC power)" or "Scaled down monitoring (battery)")
end

-- Instant trigger on power source change
k8sBatteryWatcher = hs.battery.watcher.new(powerChanged)
k8sBatteryWatcher:start()

-- Fallback timer for Low Power Mode detection (60s poll)
k8sPowerTimer = hs.timer.doEvery(60, powerChanged)

-- Sync on load
powerChanged()
