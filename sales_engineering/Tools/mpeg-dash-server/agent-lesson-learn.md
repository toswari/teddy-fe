# Agent Lessons Learned

- Always serve MPD and media segment URLs relative to the UI origin so HTTPS reverse proxies avoid mixed-content blocking.
- When dash.js emits a generic parsing failure, crank its log level to DEBUG and validate the MPD text with `DOMParser` before assuming ffmpeg packaging broke.
- Embed diagnostic logging in the Streamlit component early; capturing container URL, base URI, and browser crypto support helped confirm the iframe sandbox was not the culprit.
- Keep Python helper functions clean—leaked JavaScript during rapid edits triggered syntax errors that were caught quickly with `py_compile` in the CI loop.

## Nginx basic-auth not applying (UI protection)

**What happened**

- We added optional HTTP Basic Auth in the nginx config generator, but:
	- The first implementation injected `auth_basic` lines via a shell string with `\n`, which wrote a literal `\n` sequence into the config file.
	- Then `auth_basic` was scoped only inside the `location /` block.
- Symptoms:
	- `grep` on the nginx config showed `auth_basic "Restricted";\n        auth_basic_user_file ...` in a single line.
	- `curl -vk https://clarifai-lab.ddns.net:5443/` returned `200 OK` even without credentials (no `WWW-Authenticate`), while `curl -vk -u user:pass ...` also returned `200 OK`.
	- Browser access to `https://clarifai-lab.ddns.net:5443/` never prompted for login.

**Key findings**

- Having `auth_basic` in the file is not enough—the syntax must be correct and it must be inside the **active server block** that matches `server_name` + `listen`.
- Using `$'...\n...'` in Bash to build a snippet and then embedding that inside a here-doc can easily leak literal `\n` sequences into the generated config.
- Scoping `auth_basic` inside only the `location /` block can work, but moving it to the **server level** is simpler and more reliable when all paths (UI, `/api`, `/video`, `/dash`) should be protected.
- `curl -vk` is the fastest way to see whether nginx is really challenging for auth:
	- Without credentials you should see `HTTP/1.1 401 Unauthorized` plus `WWW-Authenticate: Basic realm="..."`.
	- With `-u user:pass` you should see `HTTP/1.1 200 OK`.
- `nginx -T` is critical to verify which server block is actually in effect and whether it contains the `auth_basic` directives we think we generated.

**Resolution plan**

1. **Generate clean auth directives in the template**
	 - Avoid prebuilt multi-line shell snippets with escaped `\n`.
	 - Instead, print `auth_basic` and `auth_basic_user_file` directly into the here-doc using a small inline `printf`, or hard-code them when `UI_BASIC_AUTH=1`.

2. **Apply auth at the server block level**
	 - Move:
		 - `auth_basic "Restricted";`
		 - `auth_basic_user_file /etc/nginx/.htpasswd-mpeg-dash;`
		 into the `server { ... }` block so they apply to all locations (`/`, `/api/`, `/video`, `/dash/`), not just `location /`.

3. **Regenerate nginx config with explicit env vars**
	 - From the project root:
		 - `export UI_BASIC_AUTH=1`
		 - `export UI_BASIC_AUTH_REALM="Restricted"`
		 - `export UI_BASIC_AUTH_FILE="/etc/nginx/.htpasswd-mpeg-dash"`
		 - Run `./setup-env.sh --setup-nginx --tls-domain clarifai-lab.ddns.net --tls-email <email>`.
	 - This overwrites the Homebrew nginx config under `$(brew --prefix nginx)/etc/nginx/conf.d/mpeg_dash.conf`.

4. **Verify the live nginx config**
	 - Run `sudo nginx -T | grep -n "auth_basic"` to confirm the **active** config includes the expected lines inside the correct `server` block (matching `clarifai-lab.ddns.net:5443`).
	 - If multiple server blocks exist, ensure only one matches that `server_name` + `listen` combination, and it has auth enabled.

5. **Reload nginx and test behavior**
	 - Reload: `./start-nginx.sh` (or `sudo nginx -t && sudo nginx -s reload`).
	 - Test from the terminal:
		 - `curl -vk https://clarifai-lab.ddns.net:5443/ | head` → expect `401 Unauthorized` and `WWW-Authenticate`.
		 - `curl -vk -u clarifai:***** https://clarifai-lab.ddns.net:5443/ | head` → expect `200 OK`.
	 - Test from a fresh browser session (private window) hitting `https://clarifai-lab.ddns.net:5443/` → expect a login prompt.

6. **Lock in the pattern**
	 - Keep all future security-related nginx changes inside the generator (`setup-env.sh`) and always validate with `nginx -T` plus `curl -vk` rather than relying solely on grepping config files.

**What actually fixed it**

- The real issue: On macOS with Homebrew nginx, the system was loading config from `/opt/homebrew/etc/nginx/servers/mpeg_dash.conf`, **not** from `/opt/homebrew/etc/nginx/conf.d/mpeg_dash.conf`.
- We had been editing/grepping the wrong file (`conf.d/`), so our `auth_basic` changes never took effect.
- Solution: Used `sudo nginx -T` (capital T) to see the **actual loaded config** and discovered it was reading from `servers/` directory.
- Once we copied the corrected config (with server-level `auth_basic` and `auth_basic_user_file`) to the correct location (`/opt/homebrew/etc/nginx/servers/mpeg_dash.conf`), reloaded nginx, and tested:
  - `curl -vk https://clarifai-lab.ddns.net:5443/` → `401 Unauthorized` ✓
  - `curl -vk -u clarifai:Clarifai2026! https://clarifai-lab.ddns.net:5443/` → `200 OK` ✓
  - Browser now prompts for login when visiting `https://clarifai-lab.ddns.net:5443/` ✓

**Key takeaway**: Always use `sudo nginx -T` (not just `nginx -t` or grepping files) to see which config files nginx is **actually loading**, especially on Homebrew installations where directories may differ from defaults.
