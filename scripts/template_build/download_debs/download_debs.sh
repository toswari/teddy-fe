#!/bin/bash
mkdir -p /deb_files
echo "Fixing requirements file..."
if command -v dos2unix > /dev/null 2>&1; then
    dos2unix /app/requirements.txt > /dev/null 2>&1
fi
sed -i '/^[[:space:]]*$/d' /app/requirements.txt
sed -i 's/^[[:space:]]*//;s/[[:space:]]*$//' /app/requirements.txt
echo "Updated requirements file:"
cat /app/requirements.txt
echo "Updating package cache..."
apt-get update > /dev/null 2>&1
while read -r package; do
    echo "Processing: $package"
    if [[ "$package" == *"*"* ]]; then
        echo "Wildcard detected: $package"
        package_list=$(apt-cache search "^${package//\*/.*}" | awk '{print $1}')
        if [[ -z "$package_list" ]]; then
            echo "No packages found for wildcard: $package"
            continue
        fi
    else
        package_list=$package
    fi
    for resolved_package in $package_list; do
        echo "Downloading: $resolved_package"
        if apt-get download "$resolved_package" > /tmp/apt_output.log 2>&1; then
            echo "Downloaded: $resolved_package"
            deb_file=$(ls ./*.deb 2>/dev/null | head -n 1)
            if [[ -f "$deb_file" ]]; then
                mv "$deb_file" /deb_files/
                echo "Moved: $deb_file to /deb_files/"
            else
                echo "Could not find the .deb file for $resolved_package"
            fi
        else
            echo "Failed to download: $resolved_package"
            echo "Error output:"
            cat /tmp/apt_output.log
        fi
    done
done < /app/requirements.txt
echo "All DEB files have been downloaded to /deb_files."
