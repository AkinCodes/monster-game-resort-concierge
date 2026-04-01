import subprocess
import time


def main():
    print("🌕 MONSTER RESORT - FINAL READINESS CHECK")
    print("-" * 40)

    # Step 1: Quality Audit (RAG)
    print("\n📝 STEP 1: Running Quality Audit...")
    subprocess.run(["python", "run_audit.py"])

    print("\n" + "-" * 40)
    time.sleep(2)

    # Step 2: Stress Test (Capacity)
    print("\n🚀 STEP 2: Running Capacity Stress Test...")
    # This triggers the interactive menu in stress_test.py
    subprocess.run(["python", "stress_test.py"])


if __name__ == "__main__":
    main()
