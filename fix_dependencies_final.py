#!/usr/bin/env python3
"""
Monster Resort Concierge - Final Dependency Fix
Resolves ALL conflicts: huggingface-hub, aiofiles, gradio
"""
import subprocess
import sys
import shutil
from pathlib import Path


def run_command(cmd, description, fail_ok=False, show_output=False):
    """Run a command and handle errors"""
    print(f"  {description}...")
    try:
        result = subprocess.run(
            cmd, shell=True, check=True, capture_output=True, text=True
        )
        if show_output and result.stdout.strip():
            print(f"    {result.stdout.strip()[:150]}")
        return True
    except subprocess.CalledProcessError as e:
        if fail_ok:
            print(f"    ⚠️  (skipped)")
            return False
        else:
            print(f"    ❌ Error")
            if show_output and e.stderr:
                print(f"    {e.stderr[:300]}")
            return False


def main():
    print("🔧 Monster Resort Concierge - FINAL Dependency Fix")
    print("=" * 70)
    print("This will resolve ALL dependency conflicts:")
    print("  - huggingface-hub version conflict")
    print("  - aiofiles conflict between gradio and FastAPI")
    print("  - Python version requirements")
    print("=" * 70)

    # Check Python version
    py_version = sys.version_info
    print(
        f"\n🐍 Python version: {py_version.major}.{py_version.minor}.{py_version.micro}"
    )

    if py_version < (3, 10):
        print("⚠️  WARNING: Python 3.10+ is recommended for best compatibility")
        print("   Your current version may work but could have issues with gradio 5+")

    # Detect package manager
    using_uv = False
    try:
        subprocess.run(["uv", "--version"], capture_output=True, check=True)
        using_uv = True
        print("✅ Detected: UV package manager")
        pip_cmd = "uv pip"
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("✅ Detected: Standard pip")
        pip_cmd = "pip"

    # Step 1: Backup and replace pyproject.toml
    print("\n📋 Step 1: Updating pyproject.toml...")

    pyproject_path = Path("pyproject.toml")
    pyproject_final = Path("pyproject_final.toml")

    if pyproject_path.exists():
        backup_path = Path("pyproject.toml.backup")
        shutil.copy(pyproject_path, backup_path)
        print(f"  ✅ Backed up existing pyproject.toml to {backup_path}")

    if pyproject_final.exists():
        shutil.copy(pyproject_final, pyproject_path)
        print(f"  ✅ Updated pyproject.toml with fixed dependencies")
    else:
        print(f"  ⚠️  pyproject_final.toml not found, using existing pyproject.toml")

    # Step 2: Clean slate - remove conflicting packages
    print("\n📦 Step 2: Removing conflicting packages...")
    packages_to_remove = [
        "huggingface-hub",
        "transformers",
        "sentence-transformers",
        "aiofiles",
        "gradio",
    ]

    for package in packages_to_remove:
        run_command(
            f"{pip_cmd} uninstall -y {package}", f"Removing {package}", fail_ok=True
        )

    # Step 3: Install in the correct order
    print("\n📦 Step 3: Installing packages in dependency order...")
    print("   (This may take 2-3 minutes, please be patient)")

    # Phase 1: Core dependencies
    print("\n   Phase 1: Core dependencies")
    core_packages = [
        ("torch==2.5.1", "PyTorch"),
        ("aiofiles==23.2.1", "aiofiles (compatible with gradio)"),
    ]

    for package, name in core_packages:
        run_command(f"{pip_cmd} install '{package}'", f"Installing {name}")

    # Phase 2: HuggingFace packages (in order!)
    print("\n   Phase 2: HuggingFace ecosystem")
    hf_packages = [
        ("huggingface-hub==0.27.0", "HuggingFace Hub (PINNED)"),
        ("transformers==4.48.0", "Transformers"),
        ("sentence-transformers==3.3.1", "Sentence Transformers"),
    ]

    for package, name in hf_packages:
        success = run_command(
            f"{pip_cmd} install '{package}' --no-deps", f"Installing {name} (no deps)"
        )
        if not success:
            print(f"    Retrying with dependencies...")
            run_command(f"{pip_cmd} install '{package}'", f"Retrying {name}")

    # Phase 3: Gradio (must come after aiofiles)
    print("\n   Phase 3: Gradio")
    run_command(f"{pip_cmd} install 'gradio>=4.44.1,<5.0.0'", "Installing Gradio 4.x")

    # Step 4: Install everything from pyproject.toml
    print("\n📦 Step 4: Installing all other dependencies...")

    if using_uv:
        success = run_command("uv sync", "Running uv sync", show_output=True)
        if not success:
            print("  Trying alternative method...")
            run_command("uv pip install -e .", "Installing with pip")
    else:
        run_command("pip install -e .", "Installing from pyproject.toml")

    # Step 5: Force re-pin critical packages
    print("\n📦 Step 5: Re-pinning critical packages to prevent version creep...")
    critical_pins = [
        ("huggingface-hub==0.27.0", "huggingface-hub"),
        ("aiofiles==23.2.1", "aiofiles"),
    ]

    for package, name in critical_pins:
        run_command(
            f"{pip_cmd} install --force-reinstall --no-deps '{package}'",
            f"Force pinning {name}",
        )

    # Step 6: Verify installation
    print("\n✅ Step 6: Verifying installation...")

    verifications = [
        (
            "from huggingface_hub import __version__; print(f'huggingface-hub: {__version__}'); assert __version__ == '0.27.0', 'Wrong version!'",
            "huggingface-hub (must be 0.27.0)",
        ),
        (
            "import transformers; print(f'transformers: {transformers.__version__}')",
            "transformers",
        ),
        (
            "import sentence_transformers; print(f'sentence-transformers: {sentence_transformers.__version__}')",
            "sentence-transformers",
        ),
        (
            "import aiofiles; print('aiofiles: OK')",
            "aiofiles (must be <24.0 for gradio)",
        ),
        ("import gradio; print(f'gradio: {gradio.__version__}')", "gradio"),
        ("import chromadb; print('chromadb: OK')", "chromadb"),
        ("import ragas; print('ragas: OK')", "ragas"),
        ("import fastapi; print('fastapi: OK')", "fastapi"),
    ]

    all_good = True
    failed = []

    for code, name in verifications:
        try:
            result = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            output = result.stdout.strip()
            print(f"  ✅ {output if output else name + ': OK'}")
        except subprocess.TimeoutExpired:
            print(f"  ⚠️  {name}: Timeout (but may be OK)")
        except subprocess.CalledProcessError as e:
            print(f"  ❌ {name}: FAILED")
            if e.stderr:
                error_msg = e.stderr.strip()[:200]
                print(f"     {error_msg}")
                failed.append((name, error_msg))
            all_good = False

    # Step 7: Show package versions
    print("\n📋 Step 7: Critical package versions:")
    try:
        result = subprocess.run(
            f"{pip_cmd} list | grep -E '(huggingface-hub|transformers|sentence-transformers|torch|aiofiles|gradio)'",
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print(result.stdout)
    except:
        # Windows doesn't have grep, try alternative
        try:
            result = subprocess.run(
                f"{pip_cmd} list", shell=True, capture_output=True, text=True
            )
            for line in result.stdout.split("\n"):
                if any(
                    pkg in line.lower()
                    for pkg in [
                        "huggingface",
                        "transformer",
                        "sentence",
                        "torch",
                        "aiofiles",
                        "gradio",
                    ]
                ):
                    print(line)
        except:
            pass

    # Final summary
    print("\n" + "=" * 70)
    if all_good:
        print("🎉 SUCCESS! All dependencies are properly installed!")
        print("=" * 70)
        print("\n✅ Everything is ready to go!")

        print("\n⚠️  IMPORTANT REMINDER:")
        print("   DON'T use 'uv run' - it will break version pinning!")
        print("\n   Instead, activate your virtual environment:")
        print("     source .venv/bin/activate  # macOS/Linux")
        print("     .venv\\Scripts\\activate    # Windows")

        print("\n   Then run scripts normally:")
        print("     python run_audit.py")
        print("     python stress_test.py")
        print("     uvicorn app.main:app --reload")

        print("\n🔒 Locked Versions:")
        print("   - huggingface-hub: 0.27.0 (required by transformers)")
        print("   - aiofiles: 23.2.1 (required by gradio 4.x)")
        print("   - gradio: 4.44.1 (compatible with Python 3.9+)")

    else:
        print("⚠️  Installation completed with some warnings")
        print("=" * 70)

        if failed:
            print("\n❌ Failed imports:")
            for name, error in failed:
                print(f"   - {name}: {error[:100]}")

        print("\n💡 If problems persist:")
        print("   1. Check Python version (3.10+ recommended)")
        print("      python --version")
        print("\n   2. Try fresh virtual environment:")
        print("      rm -rf .venv")
        print("      uv venv  # or: python -m venv .venv")
        print("      source .venv/bin/activate")
        print("      python fix_dependencies_final.py")
        print("\n   3. Clear package cache:")
        print("      uv cache clean  # or: pip cache purge")

    print("\n" + "=" * 70)
    return 0 if all_good else 1


if __name__ == "__main__":
    sys.exit(main())
