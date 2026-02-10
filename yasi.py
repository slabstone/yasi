import sys
import time
import requests
import os
import ctypes
import argparse
import json
from datetime import datetime

# --- Color Codes ---
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'

    @staticmethod
    def _print_color(color_code, message_type, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        print(f"{timestamp} {color_code}[{message_type}] {message}{Colors.ENDC}")

    @staticmethod
    def debug(message):
        Colors._print_color(Colors.BLUE, "DEBUG", message)

    @staticmethod
    def info(message):
        Colors._print_color(Colors.GREEN, "INFO", message)

    @staticmethod
    def warning(message):
        Colors._print_color(Colors.YELLOW, "WARNING", message)

    @staticmethod
    def error(message):
        Colors._print_color(Colors.RED, "ERROR", message)

# --- Global Configuration Variables ---
USER_STEAM_ID_64 = None
STEAM_COMMUNITY_APPID = None
TRADING_CARD_CONTEXT_ID = None
DEFAULT_MONITORING_INTERVAL_SECONDS = None
MAX_IDLE_MINUTES_PER_CARD = None
ENABLE_INVENTORY_CHECKING = None

GAME_NAME_CACHE = {} # Cache for game names

# --- Config Loading Function ---
def load_configuration():
    global USER_STEAM_ID_64, STEAM_COMMUNITY_APPID, TRADING_CARD_CONTEXT_ID, DEFAULT_MONITORING_INTERVAL_SECONDS, MAX_IDLE_MINUTES_PER_CARD, ENABLE_INVENTORY_CHECKING

    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    config_json_path = os.path.join(script_dir, "config.json")
    user_json_path = os.path.join(script_dir, "user.json")

    try:
        with open(config_json_path, 'r') as f:
            app_config = json.load(f)
        STEAM_COMMUNITY_APPID = app_config['steam_community_appid']
        TRADING_CARD_CONTEXT_ID = app_config['trading_card_context_id']
        DEFAULT_MONITORING_INTERVAL_SECONDS = int(app_config['default_monitoring_interval_seconds'])
        MAX_IDLE_MINUTES_PER_CARD = int(app_config.get('max_idle_minutes_per_card', 30))
        ENABLE_INVENTORY_CHECKING = bool(app_config.get('enable_inventory_checking', True))
        Colors.debug(f"Loaded application config from {config_json_path}")
    except FileNotFoundError:
        Colors.error(f"CRITICAL: Application configuration file 'config.json' not found in {script_dir}.")
        Colors.error("Please ensure 'config.json' exists and is correctly formatted.")
        sys.exit(1)
    except (KeyError, ValueError) as e:
        Colors.error(f"CRITICAL: Error parsing 'config.json': {e}. Check file structure and values.")
        sys.exit(1)

    # Only load user.json if inventory checking is enabled
    if ENABLE_INVENTORY_CHECKING:
        try:
            with open(user_json_path, 'r') as f:
                user_config = json.load(f)
            USER_STEAM_ID_64 = user_config['steam_id_64']
            Colors.debug(f"Loaded user config from {user_json_path}")
        except FileNotFoundError:
            Colors.error(f"CRITICAL: User configuration file 'user.json' not found in {script_dir}.")
            Colors.error(f"Please create it based on 'user.json.tmpl' or ensure it's in the correct location.")
            sys.exit(1)
        except (KeyError, ValueError) as e:
            Colors.error(f"CRITICAL: Error parsing 'user.json': {e}. Check file structure and values (expected 'steam_id_64').")
            sys.exit(1)

        if not isinstance(USER_STEAM_ID_64, str):
            Colors.error("CRITICAL: 'steam_id_64' in 'user.json' must be a string.")
            sys.exit(1)

        USER_STEAM_ID_64 = USER_STEAM_ID_64.strip()

        if not USER_STEAM_ID_64: # Check after stripping
            Colors.error("CRITICAL: 'steam_id_64' in 'user.json' cannot be empty.")
            sys.exit(1)
    else:
        Colors.debug("Inventory checking disabled - skipping user.json load")

# --- Steamworks Simulation ---
class SteamSimulator:
    """
    Manages the simulation of running a game via Steamworks
    by directly loading and calling steam_api64.dll using ctypes.
    Requires steam_api64.dll.
    """
    def __init__(self, app_id_str, game_name=None):
        self.app_id_str = str(app_id_str)
        self.game_name = game_name if game_name else str(app_id_str)
        self.script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.steam_appid_file_path = os.path.join(self.script_dir, "steam_appid.txt")
        self.steam_api_dll = None

    def _load_steam_api_dll(self):
        if self.steam_api_dll:
            Colors.debug("steam_api64.dll already loaded.")
            return True
        try:
            sdk_dir_path = os.path.join(self.script_dir, "sdk")
            if not os.path.isdir(sdk_dir_path):
                Colors.error(f"Steamworks SDK directory not found at {sdk_dir_path}")
                Colors.error("Please ensure the 'sdk' directory from the Steamworks SDK is present in the script's directory.")
                return False

            dll_path = os.path.join(sdk_dir_path, "redistributable_bin", "win64", "steam_api64.dll")

            if not os.path.exists(dll_path):
                Colors.error(f"steam_api64.dll not found at {dll_path}")
                Colors.error("Ensure 'steam_api64.dll' is in the 'sdk/redistributable_bin/win64/' directory.")
                return False

            Colors.debug(f"Attempting to load DLL: {dll_path}")
            self.steam_api_dll = ctypes.CDLL(dll_path)
            Colors.info("steam_api64.dll loaded successfully.")

            self.steam_api_dll.SteamAPI_InitSafe.restype = ctypes.c_bool
            self.steam_api_dll.SteamAPI_InitSafe.argtypes = []

            self.steam_api_dll.SteamAPI_RunCallbacks.restype = None
            self.steam_api_dll.SteamAPI_RunCallbacks.argtypes = []

            self.steam_api_dll.SteamAPI_Shutdown.restype = None
            self.steam_api_dll.SteamAPI_Shutdown.argtypes = []
            return True

        except OSError as e:
            Colors.error(f"Could not load or access steam_api64.dll: {e}")
            Colors.error("Ensure the DLL is not corrupted and is accessible.")
            self.steam_api_dll = None
            return False
        except AttributeError as e:
            Colors.error(f"A required Steam API function was not found in steam_api64.dll: {e}")
            Colors.error("This might indicate an incorrect, outdated, or corrupted steam_api64.dll.")
            self.steam_api_dll = None
            return False
        except Exception as e:
            Colors.error(f"An unexpected error occurred while loading steam_api64.dll: {e}")
            self.steam_api_dll = None
            return False

    def init_steam(self):
        """Initialize Steam API. Returns True on success, False on failure."""
        if not self.steam_api_dll:
            Colors.debug("Steam API DLL is not loaded. Attempting to load...")
            if not self._load_steam_api_dll():
                Colors.error("Failed to load Steam API DLL. Cannot initialize Steam simulation.")
                return False

        Colors.info(f"Initializing Steam for {self.game_name}...")

        self._cleanup_appid_file()

        try:
            with open(self.steam_appid_file_path, "w") as f:
                f.write(self.app_id_str)
            Colors.debug(f"Created {self.steam_appid_file_path} with AppID {self.app_id_str}.")
        except IOError as e:
            Colors.error(f"Could not create {self.steam_appid_file_path}: {e}")
            return False

        try:
            if not self.steam_api_dll.SteamAPI_InitSafe():
                 Colors.error("Failed to initialize Steam API (SteamAPI_InitSafe() returned False).")
                 Colors.error("Steam client is not running. Please start Steam and try again.")
                 self._cleanup_appid_file()
                 return False

            Colors.info("Steam API initialized successfully.")
            Colors.info(f"Steam should now show you as playing {self.game_name}.")
            return True
        except Exception as e:
            Colors.error(f"An unexpected error occurred during SteamAPI_InitSafe: {e}")
            self._cleanup_appid_file()
            return False

    def shutdown_steam(self):
        if self.steam_api_dll:
            Colors.info("Shutting down Steam API (direct DLL call)...")
            try:
                self.steam_api_dll.SteamAPI_Shutdown()
                Colors.info("Steam API shut down.")
            except Exception as e:
                Colors.error(f"An error occurred during SteamAPI_Shutdown: {e}")

            self.steam_api_dll = None

        self._cleanup_appid_file()

    def _cleanup_appid_file(self):
        if os.path.exists(self.steam_appid_file_path):
            try:
                os.remove(self.steam_appid_file_path)
                Colors.debug(f"Removed {self.steam_appid_file_path}.")
            except OSError as e:
                Colors.warning(f"Could not remove {self.steam_appid_file_path}: {e}")

    def run_callbacks(self):
        if self.steam_api_dll:
            try:
                self.steam_api_dll.SteamAPI_RunCallbacks()
            except Exception as e:
                Colors.error(f"An error occurred during SteamAPI_RunCallbacks: {e}")

# --- Steam Inventory Functions ---
def get_game_name(app_id):
    app_id_str = str(app_id)
    if app_id_str in GAME_NAME_CACHE:
        return GAME_NAME_CACHE[app_id_str]

    url = f"https://store.steampowered.com/api/appdetails?appids={app_id_str}"
    Colors.debug(f"Fetching game name for AppID {app_id_str} from Steam Store API")
    name_to_return = app_id_str  # Default to AppID string if fetching fails

    try:
        response = requests.get(url, timeout=10) # 10-second timeout for this API call
        response.raise_for_status() # Raises HTTPError for bad responses (4XX or 5XX)
        data = response.json()

        if data and app_id_str in data and data[app_id_str].get("success"):
            game_info = data[app_id_str].get("data")
            if game_info and "name" in game_info:
                name_to_return = game_info["name"]
                Colors.debug(f"Fetched game name for AppID {app_id_str}: {name_to_return}")
            else:
                Colors.warning(f"Could not find name in successful API response for AppID {app_id_str}.")
        else:
            # Game is likely delisted or removed from the store
            Colors.warning(f"Game AppID {app_id_str} not found in Steam Store (likely delisted). Using AppID as name.")

    except requests.exceptions.Timeout:
        Colors.warning(f"Timeout while fetching game name for AppID {app_id_str}.")
    except requests.exceptions.HTTPError as e:
        Colors.warning(f"HTTP error fetching game name for AppID {app_id_str}: {e}")
    except requests.exceptions.RequestException as e:
        Colors.warning(f"Network error fetching game name for AppID {app_id_str}: {e}")
    except ValueError: # Includes JSONDecodeError
        Colors.warning(f"Could not decode JSON for game name for AppID {app_id_str}.")

    GAME_NAME_CACHE[app_id_str] = name_to_return
    return name_to_return

def get_steam_inventory_card_count(steam_id_64, game_app_id_to_filter_for):
    """
    Fetch card count for a specific game from Steam inventory with pagination support.
    Steam now limits inventory requests to 2500 items per page.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    card_count = 0
    start_assetid = None
    page_num = 1
    total_items_processed = 0

    Colors.debug(f"Starting paginated inventory fetch for AppID {game_app_id_to_filter_for} (Steam ID: {steam_id_64})")

    while True:
        # Build URL for current page
        base_url = f"https://steamcommunity.com/inventory/{steam_id_64}/{STEAM_COMMUNITY_APPID}/{TRADING_CARD_CONTEXT_ID}?l=english&count=2500"
        if start_assetid:
            inventory_url = f"{base_url}&start_assetid={start_assetid}"
        else:
            inventory_url = base_url

        Colors.debug(f"Fetching inventory page {page_num}: {inventory_url}")

        try:
            response = requests.get(inventory_url, timeout=20, headers=headers)
            response.raise_for_status()
            data = response.json()

            if data is None or not isinstance(data, dict):
                Colors.error(f"Invalid JSON response or empty data from inventory page {page_num}.")
                if response:
                    Colors.debug(f"Response text (first 200 chars): {response.text[:200]}...")
                return -1

            if data.get("success") is False:
                error_message = data.get("Error", data.get("error", "Unknown error"))
                if "k_EResultNoMatch" in error_message or "42" in error_message:
                    Colors.info(f"Steam API Info: No matching items found (k_EResultNoMatch for AppID {STEAM_COMMUNITY_APPID}, ContextID {TRADING_CARD_CONTEXT_ID}). This can mean an empty inventory for this context. Assuming 0 cards for game {game_app_id_to_filter_for}.")
                    return 0
                Colors.error(f"Steam API Error on page {page_num}: {error_message}")
                if "private" in error_message.lower():
                    Colors.warning("Hint: The inventory might be private.")
                return -1

            # Process current page
            assets = data.get("assets", [])
            descriptions = data.get("descriptions", [])

            if not assets and not descriptions:
                if page_num == 1:
                    Colors.info(f"No 'assets' or 'descriptions' in inventory data for AppID {STEAM_COMMUNITY_APPID}, ContextID {TRADING_CARD_CONTEXT_ID} (or inventory is private/empty). Assuming 0 cards for game {game_app_id_to_filter_for}.")
                    return 0
                else:
                    # Empty page but not the first one - stop pagination
                    break

            # Build description map for this page
            description_map = {desc["classid"]: desc for desc in descriptions}
            page_cards = 0

            for asset in assets:
                desc = description_map.get(asset["classid"])
                if desc:
                    is_for_correct_game = False
                    if str(desc.get("market_fee_app")) == str(game_app_id_to_filter_for):
                        is_for_correct_game = True

                    if not is_for_correct_game and desc.get("tags"):
                        for tag in desc["tags"]:
                            if tag.get("category") == "Game" and tag.get("internal_name") == f"appid_{game_app_id_to_filter_for}":
                                is_for_correct_game = True
                                break

                    if not is_for_correct_game:
                        continue

                    is_card = False
                    if desc.get("tags"):
                        for tag in desc["tags"]:
                            if (tag.get("category") == "item_class" and
                                tag.get("internal_name") == "item_class_2" and
                                tag.get("localized_tag_name") == "Trading Card"):
                                is_card = True
                                break
                    if is_card:
                        card_amount = int(asset.get("amount", 1))
                        page_cards += card_amount
                        card_count += card_amount

            total_items_processed += len(assets)
            Colors.debug(f"Page {page_num}: Found {page_cards} card(s) for game {game_app_id_to_filter_for}, processed {len(assets)} items")

            # Check if there are more pages
            more_items = data.get("more_items", 0)
            if more_items != 1:
                # No more pages
                break

            # Get start_assetid for next page
            last_assetid = data.get("last_assetid")
            if not last_assetid:
                Colors.warning(f"No 'last_assetid' found in response but 'more_items' is 1. Stopping pagination.")
                break

            start_assetid = last_assetid
            page_num += 1

            # Add a small delay between requests to be nice to Steam's servers
            time.sleep(0.5)

        except requests.exceptions.Timeout:
            Colors.error(f"Timeout while fetching inventory page {page_num}.")
            return -1
        except requests.exceptions.HTTPError as e:
            Colors.error(f"HTTP error fetching inventory page {page_num}: {e}")
            if e.response is not None:
                if e.response.status_code == 403:
                     Colors.warning("Hint: Inventory might be private or inaccessible.")
                elif e.response.status_code == 429:
                     Colors.warning("Hint: Rate limited by Steam (HTTP 429). Try again later or increase monitoring interval.")
                Colors.debug(f"Response text (first 200 chars): {e.response.text[:200]}...")
            return -1
        except requests.exceptions.RequestException as e:
            Colors.error(f"General network error fetching inventory page {page_num}: {e}")
            return -1
        except ValueError:
            Colors.error(f"Could not decode inventory JSON for page {page_num}. Is the inventory public and format valid?")
            if 'response' in locals() and response:
                 Colors.debug(f"Response text (first 200 chars): {response.text[:200]}...")
            return -1

    Colors.debug(f"Completed paginated inventory fetch: {page_num} page(s), {total_items_processed} total items processed, {card_count} card(s) for Game AppID {game_app_id_to_filter_for}")
    return card_count

# --- State File Functions ---
def load_state_file(app_id):
    """Load saved state for the given app_id from state.txt"""
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    state_file_path = os.path.join(script_dir, "state.txt")

    if not os.path.exists(state_file_path):
        return None, None

    try:
        with open(state_file_path, 'r') as f:
            line = f.readline().strip()
            if not line:
                return None, None

            parts = line.split()
            if len(parts) != 3:
                Colors.warning(f"Invalid state file format. Expected 3 fields, got {len(parts)}.")
                return None, None

            saved_appid, saved_target, saved_seconds = parts

            if str(saved_appid) == str(app_id):
                Colors.info(f"Loaded saved state: {saved_target} with {saved_seconds}s progress toward next card")
                return saved_target, int(saved_seconds)
            else:
                return None, None

    except Exception as e:
        Colors.warning(f"Error reading state file: {e}")
        return None, None

def save_state_file(app_id, target_spec, seconds_idled):
    """Save current idling state to state.txt"""
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    state_file_path = os.path.join(script_dir, "state.txt")

    try:
        with open(state_file_path, 'w') as f:
            f.write(f"{app_id} {target_spec} {int(seconds_idled)}\n")
        Colors.info(f"Saved idling state: {target_spec} with {int(seconds_idled)}s progress")
    except Exception as e:
        Colors.error(f"Error saving state file: {e}")

def clear_state_file():
    """Clear the state.txt file"""
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    state_file_path = os.path.join(script_dir, "state.txt")

    if os.path.exists(state_file_path):
        try:
            os.remove(state_file_path)
            Colors.debug(f"Cleared state file: {state_file_path}")
        except Exception as e:
            Colors.warning(f"Error clearing state file: {e}")

# --- Helper Function for Card Target Parsing ---
def parse_card_target(target_str: str):
    if not target_str or len(target_str) < 2:
        return None, None, "Target string is too short (e.g., 't3', 'r1')."

    mode = target_str[0].lower()
    if mode not in ['t', 'r']:
        return None, None, f"Invalid mode '{target_str[0]}'. Must be 't' (total) or 'r' (remaining)."

    try:
        value = int(target_str[1:])
        if value <= 0:
            return None, None, f"Number of cards '{target_str[1:]}' must be a positive integer."
        return mode, value, None
    except ValueError:
        return None, None, f"Invalid number of cards '{target_str[1:]}'. Must be an integer."

# --- Helper Functions ---
def determine_target_card_count(initial_card_count, target_spec):
    mode, value, error_detail = parse_card_target(target_spec)
    if error_detail:
        Colors.error(f"Invalid target specification '{target_spec}': {error_detail}")
        return None, None

    if mode == 't':
        return value, False
    elif mode == 'r':
        return initial_card_count + value, True

def parse_arguments():
    # load_configuration() will have been called prior to this in main(),
    # so DEFAULT_MONITORING_INTERVAL_SECONDS is populated.
    parser = argparse.ArgumentParser(description="Yet Another Steam Idler (YASI) - Single Game Mode", formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("-a", "--app-id", type=int, required=True, help="The AppID of the game to idle.")

    parser.add_argument("-c", "--card-target", type=str, required=True,
                        help="The target card count, prefixed with mode: \n  'tX' for a total of X cards (e.g., t5).\n  'rX' for X more (remaining) cards (e.g., r2).")

    parser.add_argument("-i", "--interval", type=int,
                        default=DEFAULT_MONITORING_INTERVAL_SECONDS, # Use loaded config value as default
                        help=f"The interval in seconds to check for new card drops (default: {DEFAULT_MONITORING_INTERVAL_SECONDS}s from config.json).")

    parser.add_argument("-f", "--fast", action="store_true",
                        help="Fast check mode: run the game for 5 seconds and exit.")

    args = parser.parse_args()

    # No need to check if DEFAULT_MONITORING_INTERVAL_SECONDS is None here,
    # load_configuration() would have exited if it failed to load.
    # args.interval now directly holds the effective monitoring interval.

    if args.app_id <= 0:
        parser.error("AppID specified with -a/--app-id must be a positive integer.")

    if args.interval <= 0:
        parser.error("Monitoring interval specified with -i/--interval must be a positive integer.")

    return args

def main():
    load_configuration() # Load config first
    args = parse_arguments() # Then parse arguments, using loaded config for defaults

    app_id_to_idle = args.app_id
    target_spec = args.card_target
    monitoring_interval = args.interval

    Colors.info(f"--- YASI: Yet Another Steam Idler ---")
    Colors.info(f"Working with AppID: {app_id_to_idle}")

    # Validate target specification when inventory checking is disabled
    if not ENABLE_INVENTORY_CHECKING:
        mode, value, error_detail = parse_card_target(target_spec)
        if error_detail:
            Colors.error(f"Invalid target specification '{target_spec}': {error_detail}")
            sys.exit(1)
        if mode == 't':
            Colors.error(
                f"Cannot use 'total' card target mode ('{target_spec}') when "
                f"inventory checking is disabled in config.json. Use 'remaining' "
                f"mode instead (e.g., 'r3' for 3 additional cards)."
            )
            sys.exit(1)
        Colors.warning("Inventory checking is disabled - using timed idling mode only.")

    game_name = get_game_name(app_id_to_idle)
    Colors.info(f"Game name: {game_name}")

    # Parse and explain target
    mode, value, error_detail = parse_card_target(target_spec)
    if error_detail:
        Colors.error(f"Invalid target specification '{target_spec}': {error_detail}")
        sys.exit(1)

    target_explanation = f"{value} remaining card(s)" if mode == 'r' else f"total of {value} card(s)"
    Colors.info(f"Target: {target_explanation} ('{target_spec}')")

    if ENABLE_INVENTORY_CHECKING:
        Colors.info(f"Monitoring interval: {monitoring_interval} seconds.")

    # --- Initial Card Count Check (Before Steam Init) ---
    initial_card_count = 0  # Default for when inventory checking is disabled
    target_card_count = None
    check_for_any_new_card = False

    if ENABLE_INVENTORY_CHECKING:
        Colors.info(
            f"Performing initial card count check for {game_name}..."
        )
        initial_card_count = get_steam_inventory_card_count(
            USER_STEAM_ID_64, app_id_to_idle
        )

        if initial_card_count == -1:
            Colors.error(
                f"Failed to get initial card count for {game_name}. Cannot proceed reliably."
            )
            sys.exit(1)

        Colors.info(
            f"Initial card count for {game_name}: {initial_card_count}"
        )

        target_card_count, check_for_any_new_card = determine_target_card_count(
            initial_card_count, target_spec
        )
        if target_card_count is None:
            sys.exit(1) # Error message already printed by determine_target_card_count

        if not check_for_any_new_card and initial_card_count >= target_card_count:
            Colors.info(
                f"Target of {target_card_count} card(s) for {game_name} already met or exceeded "
                f"(current: {initial_card_count}). No idling needed."
            )
            sys.exit(0)
    else:
        # When inventory checking is disabled, we can only use 'remaining' mode
        # The target validation was already done earlier in main()
        mode, value, _ = parse_card_target(target_spec)  # We know this is valid and 'r' mode
        target_card_count = value  # For 'r' mode without inventory checking, this is just the number of cards to wait for
        check_for_any_new_card = True  # Always true in timed mode
        Colors.info(
            f"Inventory checking disabled - will idle for {value} card drop(s) "
            f"using timed mode."
        )

    Colors.info(
        f"Initializing Steam simulation for {game_name}..."
    )

    # Calculate max idle time for this session
    max_idle_time_seconds = 0
    num_cards_to_wait_for_this_session = target_card_count - initial_card_count

    if num_cards_to_wait_for_this_session > 0:
        max_idle_minutes = (
            num_cards_to_wait_for_this_session * MAX_IDLE_MINUTES_PER_CARD
        )
        max_idle_time_seconds = max_idle_minutes * 60
        Colors.info(
            f"Max idle time for this session set to: "
            f"{max_idle_minutes:.0f} minutes."
        )
        Colors.debug(
            f"  (Calc: {num_cards_to_wait_for_this_session} card(s) "
            f"to drop * {MAX_IDLE_MINUTES_PER_CARD} min/card)"        )
    # --- End of Initial Card Count Check ---

    simulator = SteamSimulator(app_id_to_idle, game_name)
    if not simulator.init_steam():
        sys.exit(2)  # Exit code 2: Stop batch processing without marking as FAIL

    # Fast check mode: run for 5 seconds and exit
    if args.fast:
        Colors.info(f"Fast check mode enabled. Running {game_name} for 5 seconds...")
        try:
            for i in range(5):
                simulator.run_callbacks()
                time.sleep(1)
            Colors.info("Fast check complete. Shutting down...")
        finally:
            simulator.shutdown_steam()
            Colors.info(f"--- Finished fast check for {game_name} ---")
        sys.exit(0)

    # Load saved state for timed mode (saved state takes priority)
    saved_seconds_for_next_card = 0
    if not ENABLE_INVENTORY_CHECKING:
        saved_target, saved_seconds = load_state_file(app_id_to_idle)
        if saved_target and saved_seconds is not None:
            # Saved state takes priority - use saved target instead of command-line
            if saved_target != target_spec:
                Colors.warning(f"Saved state found with different target!")
                Colors.warning(f"  Command-line target: '{target_spec}'")
                Colors.warning(f"  Saved target: '{saved_target}' (will be used)")
                Colors.warning(f"  Delete state.txt to start fresh")
                target_spec = saved_target
                # Recalculate target_card_count with saved target
                mode, value, _ = parse_card_target(target_spec)
                target_card_count = value
            saved_seconds_for_next_card = saved_seconds
            Colors.info(f"Resuming from saved state: {saved_seconds_for_next_card}s progress toward next card")

    try:
        current_card_count = initial_card_count
        cards_dropped_this_session = 0  # Track cards dropped during this idling session

        if ENABLE_INVENTORY_CHECKING:
            Colors.info(
                f"Monitoring for card drops for {game_name}. "
                f"Target: {target_card_count} card(s). Checking every {monitoring_interval}s."
            )
        else:
            Colors.info(
                f"Timed idling for {game_name}. "
                f"Target: {target_card_count} card drop(s). Max time: "
                f"{(max_idle_time_seconds / 60):.0f} minutes."
            )

        last_check_time = time.time()
        start_idle_time = time.time() # Record when idling starts

        while True:
            simulator.run_callbacks()

            # Check for card drops (do this first so messages appear before any exit conditions)
            current_time = time.time()
            if ENABLE_INVENTORY_CHECKING and current_time - last_check_time >= monitoring_interval:
                Colors.info(f"Checking inventory for {game_name}...")
                fresh_inventory_count = get_steam_inventory_card_count(USER_STEAM_ID_64, app_id_to_idle)
                last_check_time = current_time

                if fresh_inventory_count == -1:
                    Colors.warning(f"Failed to fetch inventory count during monitoring for {game_name}. Will retry.")
                elif fresh_inventory_count > current_card_count:
                    cards_gained = fresh_inventory_count - current_card_count
                    Colors.info(f"New card drop detected for {game_name}! Count increased from {current_card_count} to {fresh_inventory_count}.")
                    current_card_count = fresh_inventory_count
                elif fresh_inventory_count < current_card_count:
                    Colors.warning(f"Card count for {game_name} decreased from {current_card_count} to {fresh_inventory_count}. This is unusual. Continuing.")
                    current_card_count = fresh_inventory_count
                else:
                    Colors.info(f"No new cards detected for {game_name}. Current count: {current_card_count}.")
            elif not ENABLE_INVENTORY_CHECKING and current_time - last_check_time >= monitoring_interval:
                # In timed mode, simulate card drops based on time elapsed plus saved progress
                total_elapsed_seconds = (current_time - start_idle_time) + saved_seconds_for_next_card
                elapsed_minutes = total_elapsed_seconds / 60
                expected_cards = int(elapsed_minutes / MAX_IDLE_MINUTES_PER_CARD)
                if expected_cards > cards_dropped_this_session:
                    cards_dropped_this_session = expected_cards
                    # Calculate session time for this drop (actual drop time minus saved progress)
                    session_drop_minutes = cards_dropped_this_session * MAX_IDLE_MINUTES_PER_CARD - (saved_seconds_for_next_card / 60)
                    Colors.info(f"Assumed card drop for {game_name} after {session_drop_minutes:.1f} minutes. Estimated drops: {cards_dropped_this_session}.")
                last_check_time = current_time

            # Check if target is met
            if ENABLE_INVENTORY_CHECKING:
                # In inventory checking mode, check against current card count
                if current_card_count >= target_card_count:
                    Colors.info(
                        f"Target of {target_card_count} cards met for {game_name}. "
                        f"Current: {current_card_count}."
                    )
                    clear_state_file()  # Clear state on successful completion
                    break
            else:
                # In timed mode, check against cards dropped this session
                if cards_dropped_this_session >= target_card_count:
                    Colors.info(
                        f"Target of {target_card_count} card drop(s) assumed to be "
                        f"met for {game_name} after "
                        f"{(time.time() - start_idle_time) / 60:.1f} minutes of idling."
                    )
                    clear_state_file()  # Clear state on successful completion
                    break

            # Check for max idle time limit
            if max_idle_time_seconds > 0: # Only if a limit was set
                elapsed_idle_time = time.time() - start_idle_time
                if elapsed_idle_time >= max_idle_time_seconds:
                    # Do a final card drop check in timed mode before exiting
                    if not ENABLE_INVENTORY_CHECKING:
                        total_elapsed_seconds = elapsed_idle_time + saved_seconds_for_next_card
                        elapsed_minutes = total_elapsed_seconds / 60
                        expected_cards = int(elapsed_minutes / MAX_IDLE_MINUTES_PER_CARD)
                        if expected_cards > cards_dropped_this_session:
                            cards_dropped_this_session = expected_cards
                            # Calculate session time for this drop (actual drop time minus saved progress)
                            session_drop_minutes = cards_dropped_this_session * MAX_IDLE_MINUTES_PER_CARD - (saved_seconds_for_next_card / 60)
                            Colors.info(f"Assumed card drop for {game_name} after {session_drop_minutes:.1f} minutes. Estimated drops: {cards_dropped_this_session}.")

                    max_minutes_reached = max_idle_time_seconds / 60
                    Colors.warning(
                        f"Max idle time (~{max_minutes_reached:.0f} min) reached for {game_name}."
                    )
                    Colors.info("Waiting 5 seconds for Steam to sync state before stopping...")
                    time.sleep(5)

                    # Save state on max time reached (timed mode only)
                    if not ENABLE_INVENTORY_CHECKING:
                        total_elapsed_seconds = (time.time() - start_idle_time) + saved_seconds_for_next_card
                        seconds_into_current_card = int(total_elapsed_seconds % (MAX_IDLE_MINUTES_PER_CARD * 60))
                        remaining_target = target_card_count - cards_dropped_this_session
                        if remaining_target > 0:
                            save_state_file(app_id_to_idle, f"r{remaining_target}", seconds_into_current_card)

                    break # Exit the idling loop

            time.sleep(1)
    except KeyboardInterrupt:
        Colors.info(f"\nMonitoring for {game_name} interrupted by user (Ctrl+C).")

        # Save state on CTRL-C (timed mode only)
        if not ENABLE_INVENTORY_CHECKING:
            total_elapsed_seconds = (time.time() - start_idle_time) + saved_seconds_for_next_card
            seconds_into_current_card = int(total_elapsed_seconds % (MAX_IDLE_MINUTES_PER_CARD * 60))
            remaining_target = target_card_count - cards_dropped_this_session
            if remaining_target > 0:
                save_state_file(app_id_to_idle, f"r{remaining_target}", seconds_into_current_card)
            else:
                Colors.info("Target already met, no need to save state.")
                clear_state_file()
    finally:
        Colors.info(f"Stopping game simulation for {game_name}...")
        simulator.shutdown_steam()
        Colors.info(f"--- Finished processing {game_name} (AppID: {app_id_to_idle}) ---")

if __name__ == "__main__":
    main()
