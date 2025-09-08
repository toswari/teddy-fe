# Clarifai App Manager

Interactive command‑line utility to list and (optionally) delete applications in a Clarifai user account using a Personal Access Token (PAT).

> WARNING: Deletions are irreversible. Double‑check before confirming.

## Features

- Authenticate with Clarifai via username + PAT
- List all applications in a tabular view
- Select apps to delete via:
  - Single numbers (e.g. `1`)
  - Comma list (e.g. `1,3,7`)
  - Ranges (e.g. `2-5`)
  - Delete all (explicit confirmation required)
- Graceful cancellation at any prompt (Ctrl+C or choosing cancel options)

## Requirements

- Python 3.8+
- clarifai >= 11.7.5

## Installation

```powershell
python -m venv .venv
./.venv/Scripts/Activate.ps1
pip install --upgrade clarifai
```

## Usage

```powershell
python clarifai_app_manager.py
```

You will be prompted for:

1. Clarifai username
2. Personal Access Token (PAT)

After successful authentication the script lists your applications and offers deletion options.

### Deletion Input Syntax

| Input Type | Example | Meaning |
|------------|---------|---------|
| Single     | `3`     | Delete the 3rd listed app |
| Multiple   | `1,4,9` | Delete apps 1, 4, and 9 |
| Range      | `2-5`   | Delete apps 2,3,4,5 |
| Mixed      | `1,3,7-9` | Delete 1,3,7,8,9 |

Selecting option 2 in the menu ("Delete all applications") requires an explicit `yes` / `y` confirmation.

## Example Session

```
Clarifai Application Manager
==============================
Enter your Clarifai username: johndoe
Enter your Personal Access Token (PAT): ****************

Authenticating...
Authentication successful!

Fetching applications...
Found 3 application(s):
#   App ID                    Name                      Created
----------------------------------------------------------------
1   product-detector         Product Detector          2025-08-01 14:22:11
2   demo-segmentation        Demo Segmentation         2025-07-15 09:05:44
3   test-exp-1               Test Exp 1                2025-06-30 18:10:02

Deletion Options:
1. Delete specific applications (enter numbers)
2. Delete all applications
3. Cancel and exit
Enter your choice (1-3): 1

Enter the application numbers to delete (1-3):
Examples: '1' for single app, '1,3,5' for multiple apps, '1-3' for range
Enter your selection: 2-3
Selected applications for deletion:
  1. demo-segmentation - Demo Segmentation
  2. test-exp-1 - Test Exp 1

Delete these 2 application(s)? This cannot be undone! (yes/no): yes

Deleting 2 application(s)...
Deleting demo-segmentation...
  ✓ Successfully deleted demo-segmentation
Deleting test-exp-1...
  ✓ Successfully deleted test-exp-1

Deletion complete. Successfully deleted 2/2 application(s).
```

## Environment Variables (Optional Enhancement)

Currently the script always prompts. If desired you can modify `get_user_credentials()` to first read:

| Variable | Purpose |
|----------|---------|
| `CLARIFAI_USERNAME` | Username |
| `CLARIFAI_PAT`      | Personal Access Token |

Example patch inside the function (not implemented by default):

```python
username = os.getenv("CLARIFAI_USERNAME") or input("Enter your Clarifai username: ").strip()
pat = os.getenv("CLARIFAI_PAT") or input("Enter your Personal Access Token (PAT): ").strip()
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| Authentication failed | Wrong PAT / username | Regenerate PAT in Clarifai portal |
| No applications found | Account empty / permissions | Create an app in Clarifai UI to verify |
| Range parse error | Input outside valid bounds | Use numbers within listed range |
| Unicode / console issues | Windows code page | Run: `chcp 65001` before executing |

## Safety Notes

- Deletion is permanent; there is no undo.
- Consider exporting or backing up app configurations before bulk deletion.

## Contributing

For small enhancements (env var support, dry‑run flag, export feature) open an issue or submit a PR.

## License

Add your chosen license (e.g. MIT) here.

---
Made with Python and the Clarifai SDK.
