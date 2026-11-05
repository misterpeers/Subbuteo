@echo off
echo Listing files in current directory:
echo -------------------------------
dir /b
echo -------------------------------

echo.
echo Remember to include file extensions (e.g. .txt, .js, .html)
set /p FILES="Enter the filename(s) to stage: "
echo.
git add %FILES%
echo.
echo The following file(s) have been staged: %FILES%
pause
