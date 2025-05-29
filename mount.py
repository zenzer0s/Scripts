#!/usr/bin/env python3

import os
import subprocess
import shutil
from datetime import datetime
import sys

FSTAB_FILE = "/etc/fstab"
DEFAULT_MOUNT_OPTIONS = "defaults"
DEFAULT_DUMP_PASS = "0 0"  # <dump> <pass>

def check_root():
    """Check if the script is run as root."""
    if os.geteuid() != 0:
        print("🛑 This script needs to be run as root (e.g., using 'sudo python3 script_name.py').")
        sys.exit(1)

def list_drives():
    """Lists available block devices using lsblk."""
    print("\n🔍 Available block devices (partitions):")
    try:
        result = subprocess.run(
            ["lsblk", "-o", "NAME,SIZE,FSTYPE,UUID,LABEL,MOUNTPOINT"],
            capture_output=True, text=True, check=False # Check=False to handle if lsblk has issues
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"⚠️ lsblk command finished with error code {result.returncode}:")
            print(result.stderr)
            print("Attempting 'sudo blkid' as an alternative to find UUIDs:")
            alt_result = subprocess.run(["sudo", "blkid"], capture_output=True, text=True, check=False)
            print(alt_result.stdout or alt_result.stderr)

    except FileNotFoundError:
        print("❌ 'lsblk' command not found. Please install it (usually part of 'util-linux' package).")
        print("You can try 'sudo blkid' manually to find UUIDs.")
    except Exception as e:
        print(f"An unexpected error occurred while listing drives: {e}")

    print("---------------------------------------------------------------------")
    print("Please identify the UUID of the partition you want to auto-mount.")
    print("If the UUID is not visible, the partition might not be formatted,")
    print("or you might need to run 'sudo blkid' manually.")
    print("For NTFS drives (Windows), ensure 'ntfs-3g' package is installed.")
    print("For exFAT drives, ensure 'exfat-fuse' or 'exfatprogs' is installed.")
    print("---------------------------------------------------------------------")


def get_fs_type_for_uuid(uuid_to_find):
    """Tries to find the filesystem type for a given UUID using lsblk."""
    if not uuid_to_find: return None
    try:
        result = subprocess.run(
            ["lsblk", "-no", "FSTYPE", f"UUID={uuid_to_find}"],
            capture_output=True, text=True, check=False # Allow failure
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass # Silently fail, user will be prompted
    return None
    
def get_label_for_uuid(uuid_to_find):
    """Tries to find the LABEL for a given UUID using blkid."""
    if not uuid_to_find: return None
    try:
        result = subprocess.run(
            ["blkid", "-U", uuid_to_find, "-o", "export"],
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.startswith("LABEL="):
                    return line.split("=", 1)[1].strip('"')
    except (FileNotFoundError):
        pass
    return None


def get_user_input():
    """Gets drive details and mount information from the user."""
    drive_uuid = input("Enter the UUID of the partition: ").strip()
    if not drive_uuid:
        print("❌ UUID cannot be empty. Exiting.")
        sys.exit(1)

    # Check if UUID already exists in fstab
    try:
        with open(FSTAB_FILE, "r") as f:
            for line_num, line_content in enumerate(f, 1):
                line_content = line_content.strip()
                if not line_content or line_content.startswith("#"):
                    continue
                parts = line_content.split()
                if len(parts) > 0 and parts[0] == f"UUID={drive_uuid}":
                    print(f"⚠️ Warning: An entry with UUID={drive_uuid} already exists in {FSTAB_FILE} (line {line_num}):")
                    print(f"  {line_content}")
                    confirm_continue = input("Do you want to continue and add another entry for this UUID? (yes/no): ").lower()
                    if confirm_continue != "yes":
                        print("Aborting.")
                        sys.exit(1)
                    break # Only warn once per UUID
    except FileNotFoundError:
        print(f"❌ Error: {FSTAB_FILE} not found. This script expects a standard Linux environment.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred while reading {FSTAB_FILE}: {e}")
        sys.exit(1)
    
    label = get_label_for_uuid(drive_uuid)
    default_mount_name = label.replace(" ", "_").lower() if label else f"drive-{drive_uuid[:8]}"
    suggested_mount_point = f"/mnt/{default_mount_name}"
    
    mount_point = input(f"Enter the desired mount point (e.g., /mnt/mydisk) [suggested: {suggested_mount_point}]: ").strip()
    mount_point = mount_point or suggested_mount_point

    if not mount_point:
        print("❌ Mount point cannot be empty. Exiting.")
        sys.exit(1)

    # Check if mount_point already exists in fstab
    try:
        with open(FSTAB_FILE, "r") as f:
            for line_num, line_content in enumerate(f, 1):
                line_content = line_content.strip()
                if not line_content or line_content.startswith("#"):
                    continue
                parts = line_content.split()
                if len(parts) > 1 and parts[1] == mount_point:
                    print(f"⚠️ Warning: Mount point '{mount_point}' is already used in an active entry in {FSTAB_FILE} (line {line_num}):")
                    print(f"  {line_content}")
                    confirm_continue_mp = input("Do you want to continue and add another entry for this mount point? (yes/no): ").lower()
                    if confirm_continue_mp != "yes":
                        print("Aborting.")
                        sys.exit(1)
                    break # Only warn once per mount point
    except FileNotFoundError: # Should not happen if previous check passed
        pass 
    except Exception as e:
        print(f"An error occurred while reading {FSTAB_FILE}: {e}")
        sys.exit(1)


    detected_fstype = get_fs_type_for_uuid(drive_uuid)
    fs_type_prompt = "Enter the filesystem type (e.g., ntfs, ext4, vfat)"
    if detected_fstype:
        fs_type_prompt += f" [detected: {detected_fstype}]: "
        fs_type = input(fs_type_prompt).strip()
        fs_type = fs_type or detected_fstype
    else:
        fs_type_prompt += " [detection failed, please specify]: "
        fs_type = input(fs_type_prompt).strip()

    if not fs_type:
        print("❌ Filesystem type cannot be empty. Exiting.")
        sys.exit(1)

    mount_options = input(f"Enter mount options [default: {DEFAULT_MOUNT_OPTIONS}]: ").strip()
    mount_options = mount_options or DEFAULT_MOUNT_OPTIONS

    dump_pass_input = input(f"Enter dump and pass values (e.g., '0 0', '0 2') [default: '{DEFAULT_DUMP_PASS}']: ").strip()
    dump_pass = dump_pass_input or DEFAULT_DUMP_PASS

    return drive_uuid, mount_point, fs_type, mount_options, dump_pass

def create_mount_point_dir(mount_point):
    """Creates the mount point directory if it doesn't exist."""
    if not os.path.isdir(mount_point):
        print(f"ℹ️ Mount point directory '{mount_point}' does not exist.")
        create_dir_choice = input("Do you want to create it? (yes/no): ").lower()
        if create_dir_choice == "yes":
            try:
                print(f"Creating directory '{mount_point}'...")
                os.makedirs(mount_point, exist_ok=True)
                print(f"✅ Directory '{mount_point}' created.")
            except OSError as e:
                print(f"❌ Failed to create directory '{mount_point}': {e}")
                print("   Please check permissions or path.")
                sys.exit(1)
        else:
            print(f"⚠️ Warning: Mount point directory '{mount_point}' not created. Mounting will fail if it doesn't exist.")
            print(f"   You can create it manually later with: sudo mkdir -p \"{mount_point}\"")
    else:
        try:
            if os.listdir(mount_point):
                print(f"⚠️ Warning: Mount point '{mount_point}' exists and is not empty.")
                print("   Mounting here will hide its current contents.")
                confirm_non_empty = input("Are you sure you want to continue? (yes/no): ").lower()
                if confirm_non_empty != "yes":
                    print("Aborting.")
                    sys.exit(1)
        except PermissionError:
            print(f"⚠️ Warning: Cannot check contents of '{mount_point}' due to permissions, but it exists.")
        except Exception as e:
            print(f"An error occurred checking directory contents: {e}")


def add_to_fstab(drive_uuid, mount_point, fs_type, mount_options, dump_pass):
    """Generates the fstab entry and appends it to the fstab file after confirmation."""
    fstab_entry = f"UUID={drive_uuid} {mount_point} {fs_type} {mount_options} {dump_pass}"

    print("---------------------------------------------------------------------")
    print(f"The following line will be prepared for {FSTAB_FILE}:")
    print(fstab_entry)
    print("---------------------------------------------------------------------")

    confirm_add = input(f"Do you want to add this line to {FSTAB_FILE}? (yes/no): ").lower()
    if confirm_add == "yes":
        fstab_backup = f"{FSTAB_FILE}.bak.{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        try:
            print(f"Backing up {FSTAB_FILE} to {fstab_backup}...")
            shutil.copy2(FSTAB_FILE, fstab_backup) # copy2 preserves metadata
            print(f"✅ Backup created: {fstab_backup}")
        except Exception as e:
            print(f"❌ Failed to backup {FSTAB_FILE}: {e}. Aborting.")
            sys.exit(1)

        try:
            print(f"Adding entry to {FSTAB_FILE}...")
            with open(FSTAB_FILE, "r+") as f: # Read and write, start at beginning
                content = f.read()
                if content and not content.endswith("\n"):
                    f.write("\n") # Ensure newline if file doesn't end with one
                f.write(f"# Entry added by script on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(fstab_entry + "\n")
            print(f"✅ Entry added to {FSTAB_FILE}.")
            print("\nNext steps:")
            print("1. Test mounting all entries: sudo mount -a")
            print("   (If errors occur, check 'dmesg' or 'journalctl -xe' for details)")
            print(f"2. Test this specific mount: sudo mount \"{mount_point}\"")
            print(f"3. Verify: df -h \"{mount_point}\"")
            print(f"If you encounter boot issues, you might need to boot into a live environment")
            print(f"and restore from {fstab_backup} (e.g., sudo cp \"{fstab_backup}\" /mnt/system{FSTAB_FILE}).") # Corrected path
        except IOError as e:
            print(f"❌ Failed to add entry to {FSTAB_FILE}: {e}")
            print(f"   Your original fstab should be intact, but please verify. Backup is at {fstab_backup}.")
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred while writing to fstab: {e}")
            print(f"   Your original fstab should be intact, but please verify. Backup is at {fstab_backup}.")
            sys.exit(1)
    else:
        print(f"No changes made to {FSTAB_FILE}.")

def main():
    """Main function to run the script."""
    print("===== Python fstab Auto-Mount Helper =====")
    check_root()
    list_drives()
    try:
        drive_uuid, mount_point, fs_type, mount_options, dump_pass = get_user_input()
        create_mount_point_dir(mount_point)
        add_to_fstab(drive_uuid, mount_point, fs_type, mount_options, dump_pass)
    except KeyboardInterrupt:
        print("\n🛑 Script interrupted by user. Exiting.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ An unexpected error occurred: {e}")
        sys.exit(1)
    print("===== Script Finished =====")

if __name__ == "__main__":
    main()