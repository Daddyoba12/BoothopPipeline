@echo off
schtasks /Create /TN "BootHop-WeeklyAnalysis" /TR "C:\Python314\python.exe C:\Users\babso\Desktop\BootHopPipeline\analysis\weekly_analysis.py" /SC WEEKLY /D MON /ST 08:00 /F /RL LIMITED
echo.
echo Task registered: BootHop-WeeklyAnalysis - Mondays at 08:00
echo To run now: schtasks /Run /TN "BootHop-WeeklyAnalysis"
echo To remove:  schtasks /Delete /TN "BootHop-WeeklyAnalysis" /F
pause
