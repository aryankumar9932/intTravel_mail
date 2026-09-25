@echo off
setlocal
cd /d "%~dp0data_process"
set PYTHONIOENCODING=utf-8

python data_processor.py --input-dir ".\raw_data" --user-action-file "user_action.csv" --user-profile-file "user_profile.csv" --poi-info-file "poi_info.csv" --poi-geographic-file "poi_info_groupby_geographic.csv"
if errorlevel 1 (
    echo.
    echo Data processing failed.
    pause
    exit /b 1
)

python post_process_features.py
if errorlevel 1 (
    echo.
    echo Feature post-processing failed.
    pause
    exit /b 1
)

cd /d "%~dp0"
echo.
echo Starting the complete Travel Guard FastAPI application...
echo Web app: http://127.0.0.1:8000/
echo API docs: http://127.0.0.1:8000/docs
python -m uvicorn fastapi_app:app --host 0.0.0.0 --port 8000
endlocal
