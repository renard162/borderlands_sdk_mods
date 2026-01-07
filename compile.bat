@echo off
setlocal

for /f "usebackq tokens=1,* delims==" %%A in ("compile.cfg") do (
    if not "%%A"=="" set %%A=%%B
)

%ZIP% a "%MOD_NAME%.zip" "%MOD_NAME%\*"
ren "%MOD_NAME%.zip" "%MOD_NAME%.sdkmod"

del "%BL_SDK_DIR%\%MOD_NAME%.sdkmod"
move "%MOD_NAME%.sdkmod" "%BL_SDK_DIR%\%MOD_NAME%.sdkmod"
