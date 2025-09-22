import logging
import os
import platform
import shutil
import subprocess
import sys

from setuptools import Extension, find_packages, setup
from setuptools.command.build_ext import build_ext

base_path = os.path.abspath(os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SUPPORTED_NODE_VERSIONS = ["18", "20"]
RECOMMENDED_NODE_VERSION = "18.20.4"


def check_node_version():
    try:
        result = subprocess.check_output(
            ["node", "-v"], text=True, stderr=subprocess.DEVNULL, timeout=10
        ).strip()
        return result
    except (
        OSError,
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return None


def is_node_version_compatible(version):
    try:
        major_version = version.lstrip("v").split(".")[0]
        return major_version in SUPPORTED_NODE_VERSIONS
    except (ValueError, IndexError):
        return False


def install_nodejs():
    system = platform.system().lower()

    if system == "windows":
        logger.error("Please install Node.js manually from https://nodejs.org")
        logger.error(f"Recommended version: Node.js {RECOMMENDED_NODE_VERSION} LTS")
        sys.exit(1)

    elif system == "linux":
        try:
            if os.path.exists("/etc/debian_version"):
                logger.info(
                    f"Installing Node.js {RECOMMENDED_NODE_VERSION} on Debian/Ubuntu..."
                )
                subprocess.check_call(
                    [
                        "bash",
                        "-c",
                        "curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash - && "
                        "sudo apt-get install -y nodejs",
                    ],
                    timeout=300,
                )

            elif os.path.exists("/etc/redhat-release") or os.path.exists(
                "/etc/centos-release"
            ):
                logger.info(
                    f"Installing Node.js {RECOMMENDED_NODE_VERSION} on RHEL/CentOS..."
                )
                subprocess.check_call(
                    [
                        "bash",
                        "-c",
                        "curl -fsSL https://rpm.nodesource.com/setup_18.x | sudo bash - && "
                        "sudo yum install -y nodejs",
                    ],
                    timeout=300,
                )

            elif os.path.exists("/etc/arch-release") or shutil.which("pacman"):
                logger.info(
                    f"Installing Node.js {RECOMMENDED_NODE_VERSION} on Arch Linux..."
                )
                # Check if nodejs is already available in official repos
                try:
                    # Try to install nodejs and npm from official repos first
                    subprocess.check_call(
                        ["sudo", "pacman", "-S", "--noconfirm", "nodejs", "npm"],
                        timeout=300,
                    )
                    logger.info("Node.js installed from official Arch repositories")
                except subprocess.CalledProcessError:
                    logger.info("Fallback: Installing Node.js LTS from AUR...")
                    # Fallback to AUR if available (requires yay or paru)
                    aur_helper = None
                    for helper in ["yay", "paru"]:
                        if shutil.which(helper):
                            aur_helper = helper
                            break

                    if aur_helper:
                        subprocess.check_call(
                            [aur_helper, "-S", "--noconfirm", "nodejs-lts-hydrogen"],
                            timeout=300,
                        )
                        logger.info(f"Node.js LTS installed via {aur_helper}")
                    else:
                        logger.warning("No AUR helper found (yay/paru)")
                        logger.info("Installing nodejs and npm from official repos...")
                        subprocess.check_call(
                            ["sudo", "pacman", "-S", "--noconfirm", "nodejs", "npm"],
                            timeout=300,
                        )

            else:
                raise RuntimeError("Unsupported Linux distribution")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install Node.js: {e}")
            logger.error("Please install Node.js manually")
            sys.exit(1)

    elif system == "darwin":
        try:
            if shutil.which("brew"):
                logger.info("Installing Node.js using Homebrew...")
                subprocess.check_call(["brew", "install", "node@18"], timeout=300)
            else:
                logger.error(
                    "Homebrew not found. Please install Node.js manually from https://nodejs.org"
                )
                sys.exit(1)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install Node.js via Homebrew: {e}")
            sys.exit(1)

    else:
        logger.error(f"Automated installation not supported on {system}")
        logger.error("Please install Node.js manually from https://nodejs.org")
        sys.exit(1)


def ensure_nodejs():
    version = check_node_version()

    if version:
        if is_node_version_compatible(version):
            logger.info(f"Compatible Node.js found: {version}")
            return
        else:
            logger.warning(
                f"Node.js {version} found, but requires version 18.x or 20.x"
            )
            logger.warning("Attempting to install compatible version...")
    else:
        logger.info("Node.js not found. Installing...")
    install_nodejs()
    version = check_node_version()
    if version and is_node_version_compatible(version):
        logger.info(f"Node.js successfully installed: {version}")
    else:
        logger.error("Node.js installation failed or version still incompatible")
        sys.exit(1)


def check_npm():
    try:
        subprocess.check_output(
            ["npm", "--version"], text=True, stderr=subprocess.DEVNULL, timeout=10
        )
        return True
    except (
        OSError,
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


class NodeJsExtension(Extension):
    def __init__(self, name, source_dir=""):
        super().__init__(name, sources=[])
        self.source_dir = os.path.abspath(source_dir)


class SetupHelper:
    def __init__(
        self,
        source_dir: str,
        ext_dir: str,
        tmp_dir: str,
    ):
        folder_package = ""
        for item in sys.path:
            if "dist-packages" in item or "site-packages" in item:
                folder_package = item
                break
        self._source_dir = source_dir
        self._ext_dir = ext_dir
        self._tmp_dir = tmp_dir
        self._folder_package = folder_package

    def clean_old_installation(self):
        if os.path.isdir(os.path.join(self._source_dir, "src")):
            paths_to_clean = [
                os.path.join(self._folder_package, "pytgcalls", "node_modules"),
                os.path.join(self._folder_package, "pytgcalls", "dist"),
                self._tmp_dir,
            ]

            for path in paths_to_clean:
                try:
                    if os.path.exists(path):
                        shutil.rmtree(path)
                        logger.info(f"Cleaned: {path}")
                except OSError as e:
                    logger.warning(f"Failed to clean {path}: {e}")

    def _copy_source_files(self):
        required_files = [
            ("src", True),
            ("package.json", False),
            ("tsconfig.json", False),
            (".npmignore", False),
        ]

        for filename, is_dir in required_files:
            src_path = os.path.join(self._source_dir, filename)
            dst_path = os.path.join(self._tmp_dir, filename)

            try:
                if is_dir:
                    if os.path.exists(src_path):
                        shutil.copytree(src_path, dst_path)
                        logger.info(f"Copied directory: {filename}")
                    else:
                        raise FileNotFoundError(
                            f"Required directory not found: {src_path}"
                        )
                else:
                    if os.path.exists(src_path):
                        shutil.copyfile(src_path, dst_path)
                        logger.info(f"Copied file: {filename}")
                    else:
                        logger.warning(f"Optional file not found: {filename}")
            except (OSError, shutil.Error) as e:
                logger.error(f"Failed to copy {filename}: {e}")
                raise

    def _run_npm_install(self):
        try:
            logger.info("Running npm install...")
            if os.path.exists(os.path.join(self._tmp_dir, "package-lock.json")):
                logger.info("Found package-lock.json, using npm ci...")
                subprocess.check_call(["npm", "ci"], cwd=self._tmp_dir, timeout=600)
            else:
                subprocess.check_call(
                    ["npm", "install", "."], cwd=self._tmp_dir, timeout=600
                )

            logger.info("npm install completed successfully")

        except subprocess.CalledProcessError as e:
            logger.error(f"npm install failed with return code {e.returncode}")
            raise
        except subprocess.TimeoutExpired:
            logger.error("npm install timed out")
            raise
        except Exception as e:
            logger.error(f"npm install failed: {e}")
            raise

    def _copy_build_artifacts(self):
        artifacts = [("node_modules", "node_modules"), ("dist", "dist")]

        for src_name, dst_name in artifacts:
            src_path = os.path.join(self._tmp_dir, src_name)
            dst_path = os.path.join(self._ext_dir, "pytgcalls", dst_name)

            if os.path.exists(src_path):
                try:
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    shutil.copytree(src_path, dst_path)
                    logger.info(f"Copied {src_name} to extension directory")
                except (OSError, shutil.Error) as e:
                    logger.error(f"Failed to copy {src_name}: {e}")
                    raise
            else:
                logger.warning(f"Build artifact not found: {src_path}")

    def run_installation(self):
        if not os.path.isdir(os.path.join(self._source_dir, "src")):
            logger.info("No src directory found, skipping Node.js build")
            return
        try:
            os.makedirs(self._tmp_dir, exist_ok=True)
            self._copy_source_files()
            self._run_npm_install()
            self._copy_build_artifacts()
            logger.info("Installation completed successfully")

        except Exception as e:
            logger.error(f"Installation failed: {e}")
            raise


class NodeJsBuilder(build_ext):
    def run(self):
        ensure_nodejs()
        if not check_npm():
            logger.error("npm not found. Please ensure npm is installed with Node.js")
            sys.exit(1)
        super().run()

    def build_extension(self, ext):
        logger.info(f"Building extension: {ext.name}")
        ext_dir = os.path.abspath(
            os.path.dirname(self.get_ext_fullpath(ext.name)),
        )

        if not os.path.exists(self.build_temp):
            os.makedirs(self.build_temp)

        sh = SetupHelper(
            ext.source_dir,
            ext_dir,
            self.build_temp,
        )
        sh.clean_old_installation()
        sh.run_installation()


def read_readme():
    try:
        with open(os.path.join(base_path, "README.md"), encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("README.md not found")
        return "Python library for Telegram voice calls"


if __name__ == "__main__":
    setup(
        name="py-tgcalls",
        version="0.9.8",
        description="Python library for Telegram voice calls",
        long_description=read_readme(),
        long_description_content_type="text/markdown",
        url="https://github.com/pytgcalls/pytgcalls",
        author="Laky-64",
        author_email="iraci.matteo@gmail.com",
        license="LGPL-3.0",
        license_files=["LICENSE"],
        project_urls={
            "Bug Tracker": "https://github.com/pytgcalls/pytgcalls/issues",
            "Documentation": "https://pytgcalls.readthedocs.io/",
            "Source Code": "https://github.com/pytgcalls/pytgcalls",
        },
        classifiers=[
            "Development Status :: 4 - Beta",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
            "Operating System :: OS Independent",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3 :: Only",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: 3.12",
            "Programming Language :: Python :: 3.13",
            "Programming Language :: Python :: Implementation :: CPython",
            "Programming Language :: Python :: Implementation :: PyPy",
            "Topic :: Communications :: Chat",
            "Topic :: Internet :: WWW/HTTP",
            "Topic :: Multimedia :: Sound/Audio",
            "Topic :: Software Development :: Libraries :: Python Modules",
        ],
        keywords="telegram voice calls voip webrtc pytgcalls",
        ext_modules=[NodeJsExtension("pytgcalls")],
        packages=find_packages(exclude=["tests*", "docs*", "examples*"]),
        install_requires=[
            "aiohttp>=3.8.0",
            "psutil>=5.9.0",
            "screeninfo>=0.8.1",
        ],
        extras_require={
            "dev": [
                "pytest>=7.0.0",
                "pytest-asyncio>=0.21.0",
                "black>=22.0.0",
                "isort>=5.10.0",
                "flake8>=4.0.0",
            ],
        },
        python_requires=">=3.9",
        include_package_data=True,
        cmdclass={
            "build_ext": NodeJsBuilder,
        },
        zip_safe=False,
    )
