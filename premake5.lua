-- Shared build scripts from repo_build package
repo_build = require("omni/repo/build")

-- Repo root
root = repo_build.get_abs_path(".")

kit = require("_repo/deps/repo_kit_tools/kit-template/premake5-kit")
kit.setup_all()

-- Applications
define_app("omni.app.demo")
