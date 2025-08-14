import configparser
from pathlib import Path
import shutil
from datetime import datetime

def get_aws_config_path():
    """Get the path to AWS config file"""
    return Path.home() / '.aws' / 'config'

def create_backup(file_path):
    """Create a backup of the file with timestamp"""
    if file_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = file_path.parent / f"{file_path.name}.backup_{timestamp}"
        shutil.copy2(file_path, backup_path)
        print(f"Created backup: {backup_path}")
        return backup_path
    return None

def load_aws_config():
    """Load AWS config file"""
    config_path = get_aws_config_path()
    config = configparser.ConfigParser()
    
    if config_path.exists():
        config.read(config_path)
    
    return config

def check_and_add_profiles(required_profiles):
    """
    Check for required AWS profiles and add them if they don't exist
    
    Args:
        required_profiles (dict): Dictionary of profile names and their configurations
                                 Example: {'profile dev': {'region': 'us-east-1', 'output': 'json'}}
    """
    config = load_aws_config()
    config_path = get_aws_config_path()
    
    # Ensure .aws directory exists
    config_path.parent.mkdir(exist_ok=True)
    
    profiles_added = []
    
    for profile_name, profile_config in required_profiles.items():
        if profile_name not in config:
            config[profile_name] = profile_config
            profiles_added.append(profile_name)
            print(f"Added profile: {profile_name}")
        else:
            print(f"Profile already exists: {profile_name}")
            # Check if existing profile matches the proposed configuration
            needs_update = False
            for key, value in profile_config.items():
                if key not in config[profile_name] or config[profile_name][key] != value:
                    needs_update = True
                    break

            if needs_update:
                config[profile_name].update(profile_config)
                profiles_added.append(profile_name)
                print(f"Updated profile: {profile_name}")
    
    if profiles_added:
        # Create backup before modifying
        create_backup(config_path)
        
        with open(config_path, 'w') as config_file:
            config.write(config_file)
        print(f"Updated AWS config file at {config_path}")
    
    return profiles_added

# Example usage
if __name__ == "__main__":
    # Define required profiles
    required_profiles = {
        'profile pff-video': {
            'region': 'us-east-2',
            'role_arn': 'arn:aws:iam::822239714482:role/service/clarifai-read-only-s3',
            's3': '\nsignature_version = s3v4',
            'source_profile': 'default'
        },
        'profile pff-ls': {
            'region': 'us-east-2',
            'role_arn': 'arn:aws:iam::844585895626:role/service/clarifai-read-only-s3',
            's3': '\nsignature_version = s3v4',
            'source_profile': 'default'
        },
        'profile pff-tracking': {
            'region': 'us-east-1',
            'role_arn': 'arn:aws:iam::915236037149:role/service/clarifai-read-only-s3',
            'source_profile': 'default'
        }
    }
    
    # Check and add profiles
    added_profiles = check_and_add_profiles(required_profiles)
    
    if added_profiles:
        print(f"Successfully added {len(added_profiles)} new profiles")
    else:
        print("All required profiles already exist")