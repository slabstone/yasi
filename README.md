# YASI - Yet Another Steam Idler

YASI is a Python-based tool for simulating Steam game idling to trigger trading card drops. It uses the Steamworks SDK to make Steam believe a game is running and monitors your inventory for new cards. A PowerShell script (`yasim.ps1`) wrapped by a batch file (`yasim.bat`) is provided to manage idling multiple games sequentially.

## Features

*   Simulates running a game on Steam using the official Steamworks SDK.
*   **Does NOT require you to provide your Steam login credentials.**
*   Monitors your public Steam inventory for new trading cards for a specified game. **Your Steam inventory must be set to public for this to work.**
*   **Inventory checking toggle**: Can be disabled to use timed idling mode instead of inventory monitoring.
*   Stops idling for a game once a target number of cards is reached or a specified number of new cards have dropped.
*   Supports batch processing of multiple games from a list.
*   Fetches and displays game names in logs for better readability.
*   Configurable monitoring interval and pause between games.
*   Maximum idle time limits to prevent excessive idling per game.

## Prerequisites

1.  **Windows Operating System**: The current iteration relies on `steam_api64.dll` and uses PowerShell/Batch scripts for management.
2.  **Python 3.x**: Download and install from [python.org](https://www.python.org/). Ensure Python is added to your PATH.
3.  **Requests Library**: Install using pip:
    ```bash
    pip install requests
    ```
4.  **Steam Client**: Must be running and you must be logged into your Steam account.
5.  **Steamworks SDK**:
    *   Download the latest Steamworks SDK from the [Steamworks partner site](https://partner.steamgames.com/) (requires partner access).
    *   Extract the SDK.
    *   Create a subdirectory named `sdk` in the same directory as `yasi.py`.
    *   Copy the `redistributable_bin\win64\steam_api64.dll` file from the SDK into `yasi\sdk\redistributable_bin\win64\`. The final path should be `yasi\sdk\redistributable_bin\win64\steam_api64.dll` relative to `yasi.py`.

## Configuration

Configuration is split into three main JSON files and one text file for game lists:

1.  **`config.json`**: General application settings.
    *   `steam_community_appid`: The AppID for Steam Community items (usually `753`).
    *   `trading_card_context_id`: The context ID for trading cards in the inventory (usually `6`).
    *   `default_monitoring_interval_seconds`: How often (in seconds) to check your inventory for new cards (e.g., `300` for 5 minutes).
    *   `pause_between_games_seconds`: How long (in seconds) `yasim.ps1` should pause before starting the next game in a batch (e.g., `10`).
    *   `max_idle_minutes_per_card`: Maximum time to idle per expected card drop (e.g., `30` minutes).
    *   `enable_inventory_checking`: Set to `true` to monitor your Steam inventory for card drops, or `false` to use timed idling mode instead.

    Example `config.json`:
    ```json
    {
      "steam_community_appid": 753,
      "trading_card_context_id": 6,
      "default_monitoring_interval_seconds": 300,
      "pause_between_games_seconds": 10,
      "max_idle_minutes_per_card": 35,
      "enable_inventory_checking": true
    }
    ```

2.  **`user.json`**: User-specific settings.
    *   `steam_id_64`: Your 17-digit SteamID64. You can find this using sites like [SteamID.io](https://steamid.io/).
    *   A `user.json.tmpl` is provided as a template. Rename or copy it to `user.json` and fill in your details.

    Example `user.json`:
    ```json
    {
        "steam_id_64": "YOUR_STEAM_ID_64_HERE"
    }
    ```

3.  **`apps.txt`** (or any filename you choose): List of games to process in batch mode.
    *   Each line should contain a game AppID (or a full Steam game/card URL) followed by a target specification.
    *   Lines starting with `#` or `//` are treated as comments and skipped.
    *   Empty lines are also skipped.
    *   **Target Specification**:
        *   `tX`: Target a **total** of X cards for that game. If you have X or more, it skips.
        *   `rX`: Target X **remaining** (new) cards. It will idle until X more cards drop than what you had when starting for that game.

    Example `apps.txt`:
    ```plaintext
    # Idle for 2 new cards for Half-Life 2
    220 r2

    # Idle until a total of 5 cards for Portal 2
    https://steamcommunity.com/id/yourprofile/gamecards/620/ t5

    # Another game by AppID
    400 r1
    ```

## Usage

### Inventory Checking Modes

YASI supports two operational modes controlled by the `enable_inventory_checking` setting in `config.json`:

*   **Inventory Monitoring Mode** (`enable_inventory_checking: true`):
    *   **Default mode**. Monitors your public Steam inventory for card drops.
    *   Supports both 'total' (`tX`) and 'remaining' (`rX`) target formats.
    *   Requires your Steam inventory to be public.
    *   Provides real-time feedback on card drops.

*   **Timed Idling Mode** (`enable_inventory_checking: false`):
    *   Uses time-based estimation instead of inventory monitoring.
    *   **Only supports 'remaining' (`rX`) target format** - 'total' format will be rejected.
    *   Does not require public inventory access.
    *   Estimates card drops based on idle time (using `max_idle_minutes_per_card` setting).
    *   Useful when inventory privacy is preferred or inventory monitoring is unreliable.

### 1. Single Game Idling (`yasi.py`)

You can run `yasi.py` directly to idle a single game.

**Command:**
```bash
python yasi.py -a <AppID> -c <TargetSpec> [-i <IntervalSeconds>]
```

**Arguments:**
*   `-a <AppID>` or `--app-id <AppID>`: (Required) The AppID of the game to idle.
*   `-c <TargetSpec>` or `--card-target <TargetSpec>`: (Required) The card target specification (e.g., `t5` for a total of 5, `r2` for 2 more).
*   `-i <IntervalSeconds>` or `--interval <IntervalSeconds>`: (Optional) Override the `default_monitoring_interval_seconds` from `config.json`.

**Example:**
To idle game AppID `440` until you have a total of 3 cards, checking every 60 seconds:
```bash
python yasi.py -a 440 -c t3 -i 60
```

### 2. Batch Game Idling (`yasim.bat`)

The `yasim.bat` script is a convenient wrapper for `yasim.ps1` (PowerShell script) to process multiple games listed in a file (e.g., `apps.txt`).

**Command:**
```bash
yasim.bat <path_to_game_list_file>
```

**Example:**
If your game list is in `apps.txt` in the same directory:
```bash
yasim.bat apps.txt
```
This will:
1.  Read `apps.txt`.
2.  For each valid game entry, call `yasi.py` with the appropriate AppID and target.
3.  Pause for the duration specified by `pause_between_games_seconds` in `config.json` between games.
4.  Stream the output from `yasi.py` directly to the console, including timestamps.

The `yasim.ps1` script itself supports a `-PauseBetweenGamesSeconds` command-line parameter that can override the value from `config.json`. However, the current `yasim.bat` is simplified to only pass the game list file path. To use this override, you would need to call `yasim.ps1` directly or modify `yasim.bat` to pass all arguments (`%*`).

## Logging

Both `yasi.py` and `yasim.ps1` produce timestamped console output:
*   **[INFO]**: General progress and status messages.
*   **[DEBUG]**: More detailed information (e.g., API URLs, config loading).
*   **[WARNING]**: Non-critical issues (e.g., failed to fetch game name, inventory temporarily inaccessible).
*   **[ERROR]**: Critical issues that may halt processing (e.g., missing config files, Steamworks DLL not found).

Game names are fetched and included in logs alongside AppIDs for easier identification.

## How It Works

1.  **Configuration Loading**: `yasi.py` loads settings from `config.json` and `user.json`.
2.  **Initial Card Check**:
    *   **Inventory Monitoring Mode**: Before starting Steam simulation, `yasi.py` checks your current card count for the target game. If the target is already met, it exits for that game.
    *   **Timed Idling Mode**: Skips inventory checking and proceeds directly to Steam simulation.
3.  **Steam Simulation**:
    *   `yasi.py` creates a `steam_appid.txt` file with the game's AppID.
    *   It loads `steam_api64.dll` using `ctypes`.
    *   It calls `SteamAPI_InitSafe()` to initialize the Steamworks API, making Steam believe the game is running.
4.  **Monitoring Loop**:
    *   `yasi.py` periodically calls `SteamAPI_RunCallbacks()` to keep the Steam connection alive.
    *   **Inventory Monitoring Mode**: At intervals defined by `monitoring_interval`, it fetches your public Steam inventory using the Steam Community web API, counts trading cards, and stops when the target is met.
    *   **Timed Idling Mode**: Estimates card drops based on elapsed time using the `max_idle_minutes_per_card` setting, stopping when the target number of estimated drops is reached or maximum idle time is exceeded.
5.  **Shutdown**:
    *   `yasi.py` calls `SteamAPI_Shutdown()`.
    *   It cleans up the `steam_appid.txt` file.
6.  **Batch Processing (`yasim.ps1` / `yasim.bat`)**:
    *   The script reads the specified game list file.
    *   For each game, it invokes `yasi.py` as a separate process and waits for it to complete.
    *   It pauses between games if configured.

## Disclaimer

This tool interacts with the Steam client and its APIs. Use it at your own risk. When using inventory monitoring mode, ensure your inventory is set to public for the card counting to work. When using timed idling mode, inventory privacy settings do not matter. The effectiveness of idling for card drops can vary and is subject to Steam's policies and drop system.
