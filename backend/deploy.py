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

    # Get current user ID to prevent root-owned files
    user_id = os.getuid() if hasattr(os, 'getuid') else 1000
    
    subprocess.run(
        [
            "docker",
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