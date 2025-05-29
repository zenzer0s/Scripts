#!/bin/bash

# Script to help add entries to /etc/fstab for auto-mounting drives

# --- Configuration ---
FSTAB_FILE="/etc/fstab"
DEFAULT_MOUNT_OPTIONS="defaults"
DEFAULT_DUMP_PASS="0 0" # <dump> <pass> 0 0 means no dump, no fsck ordering

# --- Functions ---
check_root() {
    if [[ "$EUID" -ne 0 ]]; then
        echo "🛑 This script needs to be run as root (e.g., using 'sudo $0')."
        exit 1
    fi
}

list_drives() {
    echo
    echo "🔍 Available block devices (partitions):"
    lsblk -o NAME,SIZE,FSTYPE,UUID,LABEL,MOUNTPOINT
    echo "---------------------------------------------------------------------"
    echo "Please identify the UUID of the partition you want to auto-mount."
    echo "If the UUID is not visible, the partition might not be formatted,"
    echo "or you might need to run 'sudo blkid' to see all UUIDs."
    echo "For NTFS drives (Windows), ensure 'ntfs-3g' package is installed."
    echo "For exFAT drives, ensure 'exfat-fuse' or 'exfatprogs' is installed."
    echo "---------------------------------------------------------------------"
}

get_user_input() {
    read -r -p "Enter the UUID of the partition: " drive_uuid
    if [[ -z "$drive_uuid" ]]; then
        echo "❌ UUID cannot be empty. Exiting."
        exit 1
    fi

    # Robust check if UUID already exists as the first field in an active fstab entry
    if grep -Eq "^\s*UUID=${drive_uuid}\s+" "$FSTAB_FILE"; then
        echo "⚠️ Warning: An entry starting with UUID=${drive_uuid} already exists in $FSTAB_FILE:"
        grep -E "^\s*UUID=${drive_uuid}\s+" "$FSTAB_FILE" | sed 's/^/  /'
        read -r -p "Do you want to continue and add another entry for this UUID? (yes/no): " confirm_continue
        if [[ "$confirm_continue" != "yes" ]]; then
            echo "Aborting."
            exit 1
        fi
    fi

    local suggested_mount_point="/mnt/$(blkid -U "$drive_uuid" -o export | grep -oP 'LABEL="\K[^"]+' || echo "drive-${drive_uuid:0:8}" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]_-')"
    read -r -p "Enter the desired mount point (e.g., /mnt/mydisk) [suggested: $suggested_mount_point]: " mount_point
    mount_point=${mount_point:-$suggested_mount_point}

    if [[ -z "$mount_point" ]]; then
        echo "❌ Mount point cannot be empty. Exiting."
        exit 1
    fi

    # Robust check if mount point already exists as the second field in an active fstab entry
    if grep -Eq "^\s*[^#]\S+\s+${mount_point}(\s+|$)" "$FSTAB_FILE"; then
         echo "⚠️ Warning: An entry with mount point '$mount_point' already exists in $FSTAB_FILE:"
         grep -E "^\s*[^#]\S+\s+${mount_point}(\s+|$)" "$FSTAB_FILE" | sed 's/^/  /'
         read -r -p "Do you want to continue and add another entry for this mount point? (yes/no): " confirm_continue_mp
         if [[ "$confirm_continue_mp" != "yes" ]]; then
             echo "Aborting."
             exit 1
         fi
    fi

    local detected_fstype
    detected_fstype=$(lsblk -no FSTYPE UUID="$drive_uuid")
    if [[ -n "$detected_fstype" ]]; then
        read -r -p "Enter the filesystem type (e.g., ntfs, ext4) [detected: $detected_fstype]: " fs_type
        fs_type=${fs_type:-$detected_fstype}
    else
        read -r -p "Enter the filesystem type (e.g., ntfs, ext4) [detection failed, please specify]: " fs_type
    fi

    if [[ -z "$fs_type" ]]; then
        echo "❌ Filesystem type cannot be empty. Exiting."
        exit 1
    fi

    read -r -p "Enter mount options [default: $DEFAULT_MOUNT_OPTIONS]: " mount_options
    mount_options=${mount_options:-$DEFAULT_MOUNT_OPTIONS}

    read -r -p "Enter dump and pass values (e.g., '0 0', '0 2') [default: '$DEFAULT_DUMP_PASS']: " dump_pass_input
    dump_pass="${dump_pass_input:-$DEFAULT_DUMP_PASS}" # Use quotes to preserve spaces if user enters them
}

create_mount_point_dir() {
    if [[ ! -d "$mount_point" ]]; then
        echo "ℹ️ Mount point directory '$mount_point' does not exist."
        read -r -p "Do you want to create it? (yes/no): " create_dir_choice
        if [[ "$create_dir_choice" == "yes" ]]; then
            echo "Creating directory '$mount_point'..."
            mkdir -p "$mount_point"
            if [[ $? -ne 0 ]]; then
                echo "❌ Failed to create directory '$mount_point'. Please check permissions or path."
                exit 1
            fi
            echo "✅ Directory '$mount_point' created."
        else
            echo "⚠️ Warning: Mount point directory not created. Mounting will fail if it doesn't exist."
            echo "   You can create it manually later with: sudo mkdir -p \"$mount_point\""
        fi
    else
        if [[ -n "$(ls -A "$mount_point")" ]]; then
            echo "⚠️ Warning: Mount point '$mount_point' exists and is not empty."
            echo "   Mounting here will hide its current contents."
            read -r -p "Are you sure you want to continue? (yes/no): " confirm_non_empty
            if [[ "$confirm_non_empty" != "yes" ]]; then
                echo "Aborting."
                exit 1
            fi
        fi
    fi
}

generate_fstab_entry() {
    # Ensure no leading/trailing whitespace from user inputs for critical parts
    drive_uuid=$(echo "$drive_uuid" | xargs)
    mount_point=$(echo "$mount_point" | xargs)
    fs_type=$(echo "$fs_type" | xargs)
    
    fstab_entry="UUID=$drive_uuid $mount_point $fs_type $mount_options $dump_pass"
    echo "---------------------------------------------------------------------"
    echo "The following line will be prepared for $FSTAB_FILE:"
    echo "$fstab_entry"
    echo "---------------------------------------------------------------------"
}

add_to_fstab() {
    read -r -p "Do you want to add this line to $FSTAB_FILE? (yes/no): " confirm_add
    if [[ "$confirm_add" == "yes" ]]; then
        local fstab_backup="${FSTAB_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
        echo "Backing up $FSTAB_FILE to $fstab_backup..."
        cp "$FSTAB_FILE" "$fstab_backup"
        if [[ $? -ne 0 ]]; then
            echo "❌ Failed to backup $FSTAB_FILE. Aborting."
            exit 1
        fi
        echo "✅ Backup created: $fstab_backup"

        echo "Adding entry to $FSTAB_FILE..."
        # Add a newline before the entry if fstab doesn't end with one
        if [[ "$(tail -c1 "$FSTAB_FILE")" != "" ]]; then
            echo >> "$FSTAB_FILE"
        fi
        echo "# Entry added by script on $(date)" >> "$FSTAB_FILE"
        echo "$fstab_entry" >> "$FSTAB_FILE"

        if [[ $? -ne 0 ]]; then
            echo "❌ Failed to add entry to $FSTAB_FILE. Check permissions or disk space."
            echo "   Your original fstab is backed up at $fstab_backup."
            exit 1
        fi
        echo "✅ Entry added to $FSTAB_FILE."
        echo
        echo "Next steps:"
        echo "1. Test mounting all entries: sudo mount -a"
        echo "   (If errors occur, check 'dmesg' or 'journalctl -xe' for details)"
        echo "2. Test this specific mount: sudo mount \"$mount_point\""
        echo "3. Verify: df -h \"$mount_point\""
        echo "If you encounter boot issues, you might need to boot into a live environment"
        echo "and restore from $fstab_backup (e.g., sudo cp \"$fstab_backup\" /mnt/system/$FSTAB_FILE)."
    else
        echo "No changes made to $FSTAB_FILE."
    fi
}

# --- Main Script ---
echo "===== fstab Auto-Mount Helper (Bash Script) ====="
check_root

list_drives
get_user_input # This will set global vars: drive_uuid, mount_point, fs_type, mount_options, dump_pass
create_mount_point_dir
generate_fstab_entry # This will set global var: fstab_entry
add_to_fstab

echo "===== Script Finished =====