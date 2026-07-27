@echo off
rem 用 pythonw 启动，不会残留黑色命令行窗口
cd /d "%~dp0"
start "" pythonw pet.py
