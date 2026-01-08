#!/usr/bin/env python3
"""
Re-anonymize historical events.json data that may contain non-anonymized folder names.

Usage:
    python scripts/reanonymize_history.py <input_events.json> <output_events.json>

This reads the input events.json, replaces any watch_folder names with their
anonymized equivalents (using the same salt as the agent), and writes the
anonymized version to output.
"""
import json
import sys
from pathlib import Path

# Add parent directory to path to import prolific_agent modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from prolific_agent.privacy import get_or_create_local_salt, project_id_for_watch_path


def reanonymize_events(events: list[dict], salt: str) -> list[dict]:
    """Replace watch_folders with anonymized project IDs."""
    anonymized = []
    
    for event in events:
        event_copy = event.copy()
        watch_folders = event.get("watch_folders", [])
        
        if watch_folders:
            # Anonymize each watch folder name
            anonymized_folders = []
            for folder_name in watch_folders:
                # For each folder name, generate an anonymized ID
                # We need to treat it as if it were a Path, but we only have the name
                # The best we can do is hash the name itself consistently
                try:
                    # Try to parse as a path
                    folder_path = Path(folder_name)
                    project_id = project_id_for_watch_path(folder_path, salt=salt)
                except Exception:
                    # If that fails, just hash the string directly
                    import hmac
                    digest = hmac.new(
                        salt.encode("utf-8"),
                        folder_name.encode("utf-8"),
                        "sha256"
                    ).hexdigest()
                    project_id = f"Project-{digest[:10]}"
                
                anonymized_folders.append(project_id)
            
            event_copy["watch_folders"] = anonymized_folders
        
        anonymized.append(event_copy)
    
    return anonymized


def main():
    if len(sys.argv) != 3:
        print("Usage: python scripts/reanonymize_history.py <input.json> <output.json>")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)
    
    print(f"Reading events from: {input_file}")
    events = json.loads(input_file.read_text(encoding="utf-8-sig"))
    
    if not isinstance(events, list):
        print("Error: Input file does not contain a JSON array")
        sys.exit(1)
    
    print(f"Found {len(events)} events")
    
    # Get the same salt the agent uses
    salt = get_or_create_local_salt()
    print(f"Using local salt for consistent anonymization")
    
    # Re-anonymize
    anonymized = reanonymize_events(events, salt)
    
    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(anonymized, indent=2), encoding="utf-8")
    
    print(f"Wrote {len(anonymized)} anonymized events to: {output_file}")
    print("\nDone! You can now:")
    print(f"  1. Review the output: {output_file}")
    print(f"  2. Copy it to your repo: copy {output_file} <repo>/docs/events.json")
    print(f"  3. Regenerate viz: prolific-agent run")


if __name__ == "__main__":
    main()
