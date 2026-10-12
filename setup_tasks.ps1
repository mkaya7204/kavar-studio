# Creates (or updates) KAVAR's daily Task Scheduler tasks from schedule.json.
#   powershell -ExecutionPolicy Bypass -File setup_tasks.ps1          # create / update
#   powershell -ExecutionPolicy Bypass -File setup_tasks.ps1 -Remove  # delete them all
#   powershell -ExecutionPolicy Bypass -File setup_tasks.ps1 -ProduceOnly  # only the 06:30 produce task
#     (no Instagram token yet: posts are scheduled by hand in Meta Business Suite)
# Tasks run as the signed-in user (the PC must be on and not asleep at those times).
param([switch]$Remove, [switch]$ProduceOnly)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$cmd = Join-Path $root "run_daily.cmd"
$cfg = Get-Content (Join-Path $root "schedule.json") -Raw -Encoding UTF8 | ConvertFrom-Json

$names = @("KAVAR Produce") + (1..$cfg.slots.Count | ForEach-Object { "KAVAR Publish $_" })
foreach ($n in $names) { schtasks /Delete /TN $n /F 2>$null | Out-Null }
if ($Remove) { "Removed: $($names -join ', ')"; exit 0 }

schtasks /Create /F /SC DAILY /ST $cfg.produce_at /TN "KAVAR Produce" /TR "`"$cmd`" produce" | Out-Null
"KAVAR Produce   at $($cfg.produce_at)"
if ($ProduceOnly) { exit 0 }
$i = 1
foreach ($s in $cfg.slots) {
    schtasks /Create /F /SC DAILY /ST $s.time /TN "KAVAR Publish $i" /TR "`"$cmd`" publish $i" | Out-Null
    "KAVAR Publish $i at $($s.time) ($($s.kind))"
    $i++
}
