# schedule_weekly.ps1
# Register BootHop-WeeklyAnalysis — runs every Monday at 08:00
# Run this script once as Administrator to set up the task.

$python  = "C:\Python314\python.exe"
$script  = "C:\Users\babso\Desktop\BootHopPipeline\analysis\weekly_analysis.py"
$workdir = "C:\Users\babso\Desktop\BootHopPipeline"
$logfile = "C:\Users\babso\Desktop\BootHopPipeline\analysis\reports\weekly_run.log"

$action   = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "`"$script`" >> `"$logfile`" 2>&1" `
    -WorkingDirectory $workdir

$trigger  = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "08:00AM"

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

Register-ScheduledTask `
    -TaskName "BootHop-WeeklyAnalysis" `
    -Action   $action `
    -Trigger  $trigger `
    -Settings $settings `
    -RunLevel Limited `
    -Force

Write-Output "Task registered: BootHop-WeeklyAnalysis (Mondays 08:00)"
Write-Output "Log output: $logfile"
Write-Output ""
Write-Output "To run manually: python analysis\weekly_analysis.py"
Write-Output "To remove task:  Unregister-ScheduledTask -TaskName BootHop-WeeklyAnalysis -Confirm:`$false"
