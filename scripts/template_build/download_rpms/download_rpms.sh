#!/bin/bash

mkdir -p /rpm_files

while read -r package; do
    echo "Downloading: $package"
    dnf download --resolve --destdir=/rpm_files "$package" || {
        echo "Failed to download: $package"
    }
done < /app/requirements.txt
