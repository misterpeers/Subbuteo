@echo off
:: Prompt for local Git user name
set /p USERNAME="Enter your Git user name: "
git config user.name "%USERNAME%"

:: Prompt for local Git email address
set /p USEREMAIL="Enter your Git email address: "
git config user.email "%USEREMAIL%"

:: Prompt for commit message
set /p MSG="Enter your commit message: "
git commit -m "%MSG%"
echo.
echo Changes committed successfully with message: "%MSG%"
pause
