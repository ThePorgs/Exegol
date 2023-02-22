import subprocess
from rich.prompt import Prompt

from exegol.utils.ExeLog import logger


def createVolume(container_path: str, container_size: int, encryption_key: str):
    logger.debug(f"Encrypted container path: {container_path}")

    # Create an empty container with a defined size (in GB)
    _container_size_gb = container_size * 1024 * 1024 * 1024
    logger.debug(f"Creating an empty container of {_container_size_gb}GB")
    with open(container_path, "wb") as f:
        f.truncate(_container_size_gb)

    # Encrypt the container with LUKS
    logger.debug("Encrypting the container")
    p = subprocess.run(
        ["cryptsetup", "luksFormat", f"{container_path}", "--cipher", "aes-xts-plain64",
         "--key-size", "512", "--hash", "sha512", "--iter-time", "5000", "--use-random", "--batch-mode", "--key-file", "-"],
        input=encryption_key.encode(),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if p.returncode != 0:
        logger.debug(f"luksFormat output: {p.stderr.decode()}")

def unlockVolume(container_path: str, container_name: str, encryption_key:str):
    # Open the encrypted container as a mapped device
    logger.debug("Decrypting the container into a volume")
    p = subprocess.run(
        ["cryptsetup", "luksOpen", container_path, container_name, "--key-file", "-"],
        input=encryption_key.encode(),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if p.returncode != 0:
        logger.debug(f"cryptsetup luksOpen: {p.stderr.decode()}")


def mountVolume(container_name: str, target_host_path: str):
    # Mount the decrypted volume to a host directory
    logger.debug("Mounting the volume")
    p = subprocess.run(
        ["mount", "-o", "rw", f"/dev/mapper/{container_name}", target_host_path],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if p.returncode != 0:
        logger.debug(f"mount output: {p.stderr.decode()}")


def umountVolume(target_host_path: str):
    # Unmount the decrypted volume to a host directory
    logger.debug("Unmounting the volume")
    p = subprocess.run(
        ["umount", target_host_path],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if p.returncode != 0:
        logger.debug(f"umount output: {p.stderr.decode()}")


def formatVolume(container_name: str):
    # Create an ext4 file system on the encrypted container
    logger.debug("Create an ext4 file system on the encrypted container")
    p = subprocess.run(
        ["mkfs.ext4", f"/dev/mapper/{container_name}"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if p.returncode != 0:
        logger.debug(f"mkfs.ext4 output: {p.stderr.decode()}")


def lockVolume(container_name: str):
    # Close the container
    logger.debug("Closing the container")
    p = subprocess.run(
        ["cryptsetup", "luksClose", container_name],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if p.returncode != 0:
        logger.debug(f"cryptsetup luksClose: {p.stderr.decode()}")