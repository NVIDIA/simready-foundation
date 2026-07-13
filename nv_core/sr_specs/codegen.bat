@echo off
pushd "%~dp0"
call repo usd_profiles_codegen %*
popd
