# Tools Directory

This directory contains utility scripts for managing Steam badge data and generating card idling lists for YASI.

## Overview

The scripts work together in a pipeline to help you efficiently collect Steam trading cards:

1. **parse-badges** - Parse Steam badges HTML into structured CSV data
2. **generate-apps** - Generate an idling list from the CSV data
3. **apps-stats** - Calculate statistics and time estimates for idling

## Scripts

### parse-badges

Parses a Steam badges HTML page and extracts game badge information into a CSV file.

**Usage:**
```bash
./parse-badges [html_file]
```

**Arguments:**
- `html_file` - Input HTML file (default: `badges.html`)

**Output:**
- Creates `badges.csv` with the following columns:
  - `game_name` - Name of the game
  - `hours_on_record` - Total playtime hours
  - `card_drops_earned` - Number of cards earned
  - `card_drops_received` - Number of cards received
  - `card_drops_remaining` - Number of card drops remaining
  - `game_card_page_url` - URL to the game's card page

**How to get the badges HTML:**
1. Log into Steam in your web browser
2. Navigate to your badges page: `https://steamcommunity.com/id/YOUR_STEAM_ID/badges/`
3. Scroll to the bottom to load all badges (Steam loads badges progressively)
4. View page source (Ctrl+U or Cmd+Option+U) and copy the HTML
5. Save it as `badges.html` in the YASI directory

**Example:**
```bash
./parse-badges badges.html
```

**Output:** Displays statistics to stderr about drops remaining and apps to idle, writes CSV to `badges.csv`.

---

### generate-apps

Generates an `apps.txt` file containing games with remaining card drops from the parsed CSV data.

**Usage:**
```bash
./generate-apps [-o output_file] [csv_file]
```

**Arguments:**
- `-o output_file` - Specify output file (default: `apps.txt`)
- `csv_file` - Input CSV file (default: `badges.csv`)

**Output:**
- Creates `apps.txt` with lines in the format: `URL rN`
  - `URL` - Steam game card page URL
  - `rN` - Remaining card drops (e.g., `r5` means 5 cards remaining)

**Example:**
```bash
./generate-apps
./generate-apps -o custom-apps.txt badges.csv
```

**Note:** Only games with `card_drops_remaining > 0` are included in the output.

---

### apps-stats

Analyzes an `apps.txt` file and provides statistics about total cards to collect and time estimates for idling.

**Usage:**
```bash
./apps-stats [apps_file]
```

**Arguments:**
- `apps_file` - Input apps list file (default: `apps.txt`)

**Environment Variables:**
- `CONFIG_FILE` - Path to config.json (default: `../config.json`)

**Output:**
Displays:
- Total apps to idle
- Total cards to collect
- Maximum estimated idling time in various formats (minutes, hours, days, weeks)
- Time estimates for 8-hour daily idling sessions

**Example:**
```bash
./apps-stats
./apps-stats custom-apps.txt
```

**Notes:**
- Reads `max_idle_minutes_per_card` from `config.json`
- Estimates are maximum values; actual card drop times may vary
- Time calculations assume worst-case scenario (maximum idle time per card)

---

## Complete Workflow

Here's a typical workflow for using these tools:

```bash
# 1. Save your Steam badges page as badges.html
# (See parse-badges section above)

# 2. Parse the badges HTML into CSV format
./parse-badges badges.html

# 3. Generate the apps list from the CSV
./generate-apps

# 4. View statistics about the idling queue
./apps-stats

# 5. Use the generated apps.txt with YASI
cd ..
./yasim.bat
```

## Requirements

- **Bash**: These scripts use bash shell scripting
- **gawk**: GNU awk is required for CSV/HTML parsing
  - On Windows: Install via Git Bash, WSL, or Cygwin
  - On Linux: Usually pre-installed or `sudo apt install gawk`
  - On macOS: `brew install gawk`

## Platform Notes

### Windows

These are bash scripts, so you'll need a Unix-like environment:

- **Git Bash**: Recommended for Windows users (includes gawk)
- **WSL**: Windows Subsystem for Linux
- **Cygwin**: Another Unix-like environment option

Example using Git Bash:
```bash
"C:\Program Files\Git\bin\bash.exe" ./parse-badges badges.html
```

### Linux/macOS

Scripts should run natively:
```bash
chmod +x parse-badges generate-apps apps-stats
./parse-badges badges.html
```

## Troubleshooting

**Error: gawk not found**
- Install GNU awk for your platform (see Requirements section)

**Error: Config file not found**
- Ensure `config.json` exists in the parent directory
- Or set the `CONFIG_FILE` environment variable

**No output from parse-badges**
- Ensure the HTML file contains badge data
- Verify you scrolled to load all badges before saving
- Check that you're logged into Steam when saving the page

**generate-apps produces empty file**
- Verify that `badges.csv` has games with `card_drops_remaining > 0`
- Check that the CSV was parsed correctly by examining its contents

## See Also

- [Main YASI README](../README.md) - Main project documentation
- `config.json` - Configuration file for idling settings
- `apps.txt` - Generated list of games to idle (created by generate-apps)
- `badges.csv` - Parsed badge data (created by parse-badges)
