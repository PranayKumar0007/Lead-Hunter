@echo off
:: followup_runner.bat — Windows Task Scheduler entry point
:: Runs the Lead Hunter follow-up pass daily at 9:00 AM.
::
:: This script:
::   1. Activates the project's virtual environment
::   2. Runs followup_runner.py in LIVE mode (--send flag)
::   3. Appends a timestamped log to output\followup_runner.log

cd /d "d:\projects\Active\Leadgen_automation\lead-hunter"

:: Activate venv
call "..\\.venv\\Scripts\\activate.bat"

:: Run the follow-up pass (live send)
echo ============================================ >> output\followup_runner.log
echo Run started: %date% %time% >> output\followup_runner.log
echo ============================================ >> output\followup_runner.log

python followup_runner.py --send >> output\followup_runner.log 2>&1

echo Run finished: %date% %time% >> output\followup_runner.log
echo. >> output\followup_runner.log
