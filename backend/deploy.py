import os
import shutil
import zipfile
import subprocess
import sys


def main():
    print("Creating Lambda deployment package...")

    # Clean up old package (use subprocess for root-owned files from Docker)
    if os.path.exists("lambda-package"):
        try:
            shutil.rmtree("lambda-package")
        except PermissionError:
            print("Cleaning up Docker-created files...")
            subprocess.run(["sudo", "rm", "-rf", "lambda-package"], check=False)
    if os.path.exists("lambda-deployment.zip"):
        os.remove("lambda-deployment.zip")

    os.makedirs("lambda-package")

    print("Installing dependencies for Lambda runtime...")

    # Check if Docker is available (try both docker command and Windows WSL path)
    docker_cmd = None
    docker_available = False
    
    # First try standard docker command
    try:
        subprocess.run(["docker", "--version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        docker_cmd = "docker"
        docker_available = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # If not available, try Windows Docker Desktop via WSL
    if not docker_available:
        windows_docker_path = "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"
        if os.path.exists(windows_docker_path):
            try:
                # Check both that the exe exists AND that Docker daemon is accessible
                result = subprocess.run([windows_docker_path, "info"], 
                                      check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                docker_cmd = windows_docker_path
                docker_available = True
                print("Using Docker Desktop via WSL2 integration...")
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
    
    if docker_available:
        # Use Docker if available (preferred method)
        # Get current user ID to prevent root-owned files
        user_id = os.getuid() if hasattr(os, 'getuid') else 1000
        
        try:
            subprocess.run(
                [
                    docker_cmd,
                    "run",
                    "--rm",
                    "--user",
                    str(user_id),
                    "-v",
                    f"{os.getcwd()}:/var/task",
                    "--platform",
                    "linux/amd64",
                    "--entrypoint",
                    "",
                    "public.ecr.aws/lambda/python:3.12",
                    "/bin/sh",
                    "-c",
                    "pip install --target /var/task/lambda-package -r /var/task/requirements.txt --platform manylinux2014_x86_64 --only-binary=:all: --upgrade",
                ],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Docker connection failed: {e}")
            print("💡 Try one of these solutions:")
            print("   1. Restart Docker Desktop and wait for it to fully start")
            print("   2. Enable WSL2 integration in Docker Desktop Settings → General → Use the WSL 2 based engine")
            print("   3. Enable your WSL distribution in Docker Desktop Settings → Resources → WSL Integration")
            print("   4. Restart Cursor to refresh the WSL environment\n")
            # Fall through to pip fallback
            docker_available = False
    else:
        # Fallback: Use pip directly (may have compatibility issues)
        print("⚠️  Docker not available, using pip directly...")
        print("⚠️  Warning: This may not be fully compatible with Lambda runtime!")
        
        # Use pip with platform targeting if possible
        pip_cmd = [
            sys.executable, "-m", "pip", "install",
            "--target", "lambda-package",
            "-r", "requirements.txt",
            "--upgrade"
        ]
        
        # Try to target Linux platform if we can detect it
        import platform
        if platform.machine() == "x86_64":
            pip_cmd.extend(["--platform", "manylinux2014_x86_64", "--only-binary=:all:"])
        
        subprocess.run(pip_cmd, check=True)

    print("Copying application files...")
    for file in ["server.py", "lambda_handler.py", "context.py", "resources.py"]:
        if os.path.exists(file):
            shutil.copy2(file, "lambda-package/")
    
    if os.path.exists("data"):
        shutil.copytree("data", "lambda-package/data")

    print("Creating zip file...")
    with zipfile.ZipFile("lambda-deployment.zip", "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk("lambda-package"):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, "lambda-package")
                zipf.write(file_path, arcname)

    size_mb = os.path.getsize("lambda-deployment.zip") / (1024 * 1024)
    print(f"✓ Created lambda-deployment.zip ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()