# fstab Auto-Mount Helper

This Bash script (`mount.sh`) helps you safely add new entries to `/etc/fstab` for auto-mounting drives on Linux.

## Features

- Lists available block devices and their UUIDs.
- Guides you through entering the correct UUID, mount point, and filesystem type.
- Checks for duplicate UUIDs or mount points in `/etc/fstab`.
- Optionally creates the mount point directory.
- Backs up your existing `/etc/fstab` before making changes.
- Adds a new entry to `/etc/fstab` with your chosen options.

## Usage

1. **Run as root:**
   ```bash
   sudo ./mount.sh
   ```
2. **Follow the prompts** to select the drive, mount point, filesystem type, and options.
3. **Test your changes:**
   ```bash
   sudo mount -a
   ```

## Notes

- For NTFS drives, install `ntfs-3g`.
- For exFAT drives, install `exfat-fuse` or `exfatprogs`.
- Always verify your `/etc/fstab` after editing to avoid boot issues.

## Disclaimer

Use at your own risk. Always keep a backup of your `/etc/fstab`.
