#!/usr/bin/env python3
"""
Clarifai Application Management Script

This script allows users to list and delete applications from their Clarifai account
using username and Personal Access Token (PAT) authentication.

Usage:
    python clarifai_app_manager.py

Requirements:
    - clarifai>=11.7.5
"""

import sys
import os
from typing import List, Optional
from clarifai.client.user import User


class ClarifaiAppManager:
    """Manages Clarifai applications for a given user."""
    
    def __init__(self, username: str, pat: str):
        """Initialize the Clarifai app manager.
        
        Args:
            username (str): The Clarifai username
            pat (str): The Personal Access Token
        """
        self.username = username
        self.pat = pat
        self.client = None
        
    def authenticate(self) -> bool:
        """Authenticate with Clarifai using username and PAT.
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            self.client = User(user_id=self.username, pat=self.pat)
            # Test authentication by attempting to list apps
            list(self.client.list_apps(per_page=1))
            return True
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False
    
    def list_applications(self) -> List:
        """List all applications for the authenticated user.
        
        Returns:
            List: List of application objects
        """
        if not self.client:
            raise ValueError("Client not authenticated. Call authenticate() first.")
        
        try:
            apps = list(self.client.list_apps())
            return apps
        except Exception as e:
            print(f"Error listing applications: {e}")
            return []
    
    def delete_application(self, app_id: str) -> bool:
        """Delete a specific application.
        
        Args:
            app_id (str): The ID of the application to delete
            
        Returns:
            bool: True if deletion successful, False otherwise
        """
        if not self.client:
            raise ValueError("Client not authenticated. Call authenticate() first.")
        
        try:
            self.client.delete_app(app_id=app_id)
            return True
        except Exception as e:
            print(f"Error deleting application {app_id}: {e}")
            return False


def get_user_credentials() -> tuple:
    """Get username and PAT from user input.
    
    Returns:
        tuple: (username, pat)
    """
    print("Clarifai Application Manager")
    print("=" * 30)
    
    username = input("Enter your Clarifai username: ").strip()
    if not username:
        print("Error: Username cannot be empty")
        sys.exit(1)
    
    pat = input("Enter your Personal Access Token (PAT): ").strip()
    if not pat:
        print("Error: PAT cannot be empty")
        sys.exit(1)
    
    return username, pat


def main():
    """Main function to run the application manager."""
    try:
        # Get credentials
        username, pat = get_user_credentials()
        
        # Initialize manager
        manager = ClarifaiAppManager(username, pat)
        
        # Authenticate
        print("\nAuthenticating...")
        if not manager.authenticate():
            print("Authentication failed. Please check your credentials.")
            sys.exit(1)
        
        print("Authentication successful!")
        
        # Continue with application management
        manage_applications(manager)
        
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)


def display_applications(apps: List) -> None:
    """Display applications in a formatted table.
    
    Args:
        apps: List of application objects
    """
    if not apps:
        print("\nNo applications found in your account.")
        return
    
    print(f"\nFound {len(apps)} application(s):")
    print("-" * 80)
    print(f"{'#':<3} {'App ID':<25} {'Name':<25} {'Created':<25}")
    print("-" * 80)
    
    for i, app in enumerate(apps, 1):
        created_date = getattr(app, 'created_at', 'Unknown')
        if created_date and hasattr(created_date, 'strftime'):
            created_str = created_date.strftime('%Y-%m-%d %H:%M:%S')
        else:
            created_str = str(created_date)[:25] if created_date else 'Unknown'
        
        print(f"{i:<3} {app.id:<25} {getattr(app, 'name', 'N/A'):<25} {created_str:<25}")


def get_deletion_choice(apps: List) -> List[int]:
    """Get user's choice for which applications to delete.
    
    Args:
        apps: List of application objects
        
    Returns:
        List[int]: List of indices (0-based) of apps to delete
    """
    while True:
        print("\nDeletion Options:")
        print("1. Delete specific applications (enter numbers)")
        print("2. Delete all applications")
        print("3. Cancel and exit")
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == "1":
            return get_specific_apps_to_delete(apps)
        elif choice == "2":
            confirm = input(f"\nAre you sure you want to delete ALL {len(apps)} applications? This cannot be undone! (yes/no): ").strip().lower()
            if confirm in ['yes', 'y']:
                return list(range(len(apps)))
            else:
                print("Deletion cancelled.")
                continue
        elif choice == "3":
            return []
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")


def get_specific_apps_to_delete(apps: List) -> List[int]:
    """Get specific application numbers to delete.
    
    Args:
        apps: List of application objects
        
    Returns:
        List[int]: List of indices (0-based) of apps to delete
    """
    while True:
        print(f"\nEnter the application numbers to delete (1-{len(apps)}):")
        print("Examples: '1' for single app, '1,3,5' for multiple apps, '1-3' for range")
        
        selection = input("Enter your selection: ").strip()
        
        if not selection:
            print("No selection made.")
            return []
        
        try:
            indices = parse_selection(selection, len(apps))
            if indices:
                selected_apps = [apps[i] for i in indices]
                print(f"\nSelected applications for deletion:")
                for i, app in enumerate(selected_apps):
                    print(f"  {i+1}. {app.id} - {getattr(app, 'name', 'N/A')}")
                
                confirm = input(f"\nDelete these {len(indices)} application(s)? This cannot be undone! (yes/no): ").strip().lower()
                if confirm in ['yes', 'y']:
                    return indices
                else:
                    print("Deletion cancelled.")
                    return []
            else:
                print("No valid applications selected.")
                return []
        except ValueError as e:
            print(f"Invalid selection: {e}")


def parse_selection(selection: str, max_num: int) -> List[int]:
    """Parse user selection string into list of indices.
    
    Args:
        selection: User input string (e.g., "1,3,5" or "1-3")
        max_num: Maximum valid number
        
    Returns:
        List[int]: List of 0-based indices
    """
    indices = set()
    
    for part in selection.split(','):
        part = part.strip()
        if '-' in part:
            # Handle range (e.g., "1-3")
            start, end = part.split('-', 1)
            start, end = int(start.strip()), int(end.strip())
            if start < 1 or end > max_num or start > end:
                raise ValueError(f"Invalid range {start}-{end}. Must be between 1 and {max_num}")
            indices.update(range(start-1, end))
        else:
            # Handle single number
            num = int(part.strip())
            if num < 1 or num > max_num:
                raise ValueError(f"Invalid number {num}. Must be between 1 and {max_num}")
            indices.add(num-1)
    
    return sorted(list(indices))


def manage_applications(manager: ClarifaiAppManager):
    """Handle application listing and deletion options.
    
    Args:
        manager: Authenticated ClarifaiAppManager instance
    """
    # List applications
    print("\nFetching applications...")
    apps = manager.list_applications()
    
    if not apps:
        print("No applications found in your account.")
        return
    
    # Display applications
    display_applications(apps)
    
    # Get deletion choice
    indices_to_delete = get_deletion_choice(apps)
    
    if not indices_to_delete:
        print("No applications selected for deletion. Exiting.")
        return
    
    # Delete selected applications
    print(f"\nDeleting {len(indices_to_delete)} application(s)...")
    success_count = 0
    
    for i in indices_to_delete:
        app = apps[i]
        print(f"Deleting {app.id}...")
        if manager.delete_application(app.id):
            print(f"  ✓ Successfully deleted {app.id}")
            success_count += 1
        else:
            print(f"  ✗ Failed to delete {app.id}")
    
    print(f"\nDeletion complete. Successfully deleted {success_count}/{len(indices_to_delete)} application(s).")


if __name__ == "__main__":
    main()
