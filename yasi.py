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
MAX_IDLE_MINUTES_PER_CARD = None # New global variable

GAME_NAME_CACHE = {} # Cache for game names

# --- Config Loading Function ---
def load_configuration():
    global USER_STEAM_ID_64, STEAM_COMMUNITY_APPID, TRADING_CARD_CONTEXT_ID, DEFAULT_MONITORING_INTERVAL_SECONDS, MAX_IDLE_MINUTES_PER_CARD

    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    config_json_path = os.path.join(script_dir, "config.json")
    user_json_path = os.path.join(script_dir, "user.json")

    try:
        with open(config_json_path, 'r') as f:
            app_config = json.load(f)
        STEAM_COMMUNITY_APPID = app_config['steam_community_appid']
        TRADING_CARD_CONTEXT_ID = app_config['trading_card_context_id']
        DEFAULT_MONITORING_INTERVAL_SECONDS = int(app_config['default_monitoring_interval_seconds'])
        MAX_IDLE_MINUTES_PER_CARD = int(app_config.get('max_idle_minutes_per_card', 30)) # Load new config
        Colors.debug(f"Loaded application config from {config_json_path}")
    except FileNotFoundError:
        Colors.error(f"CRITICAL: Application configuration file 'config.json' not found in {script_dir}.")
        Colors.error("Please ensure 'config.json' exists and is correctly formatted.")
        sys.exit(1)
    except (KeyError, ValueError) as e:
        Colors.error(f"CRITICAL: Error parsing 'config.json': {e}. Check file structure and values.")
        sys.exit(1)

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

    USER_STEAM_ID_64 = USER_STEAM_ID_64.strip() # Store the stripped version

    if not USER_STEAM_ID_64: # Check after stripping
        Colors.error("CRITICAL: 'steam_id_64' in 'user.json' cannot be empty.")
        sys.exit(1)

# --- Steamworks Simulation ---
class SteamSimulator:
    """
    Manages the simulation of running a game via Steamworks
    by directly loading and calling steam_api64.dll using ctypes.
    Requires steam_api64.dll.
    """
    def __init__(self, app_id_str):
        self.app_id_str = str(app_id_str)
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
            Colors.error(f"A required SteamAPI function was not found in steam_api64.dll: {e}")
            Colors.error("This might indicate an incorrect, outdated, or corrupted steam_api64.dll.")
            self.steam_api_dll = None
            return False
        except Exception as e:
            Colors.error(f"An unexpected error occurred while loading steam_api64.dll: {e}")
            self.steam_api_dll = None
            return False

    def init_steam(self):
        if not self.steam_api_dll:
            Colors.debug("Steam API DLL is not loaded. Attempting to load...")
            if not self._load_steam_api_dll():
                Colors.error("Failed to load Steam API DLL. Cannot initialize Steam simulation.")
                return False

        Colors.info(f"Initializing Steam for AppID: {self.app_id_str} (via direct DLL call)...")

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
                 Colors.error("Failed to initialize Steamworks (SteamAPI_InitSafe() returned False).")
                 Colors.error("Ensure Steam client is running. The game might also need to be in your library.")
                 self._cleanup_appid_file()
                 return False

            Colors.info("Steamworks initialized successfully via direct DLL call.")
            Colors.info(f"Steam should now show you as playing game with AppID {self.app_id_str}.")
            return True
        except Exception as e:
            Colors.error(f"An unexpected error occurred during SteamAPI_InitSafe: {e}")
            self._cleanup_appid_file()
            return False

    def shutdown_steam(self):
        if self.steam_api_dll:
            Colors.info("Shutting down Steamworks (direct DLL call)...")
            try:
                self.steam_api_dll.SteamAPI_Shutdown()
                Colors.info("Steamworks shut down.")
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
    Colors.debug(f"Fetching game name for AppID {app_id_str} from {url}")
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
            api_error_detail = data.get(app_id_str, 'Not found in response') if data else 'No data returned'
            Colors.warning(f"API request for game name for AppID {app_id_str} not successful or data malformed. Detail: {api_error_detail}")

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
    inventory_url = f"https://steamcommunity.com/inventory/{steam_id_64}/{STEAM_COMMUNITY_APPID}/{TRADING_CARD_CONTEXT_ID}?l=english&count=5000"
    Colors.debug(f"Fetching inventory from: {inventory_url} (AppID: {STEAM_COMMUNITY_APPID}, ContextID: {TRADING_CARD_CONTEXT_ID}, filtering for game {game_app_id_to_filter_for})")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(inventory_url, timeout=20, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data is None or not isinstance(data, dict):
            Colors.error("Invalid JSON response or empty data from inventory.")
            if response:
                Colors.debug(f"Response text (first 200 chars): {response.text[:200]}...")
            return -1

        if data.get("success") is False:
            error_message = data.get("Error", data.get("error", "Unknown error"))
            if "k_EResultNoMatch" in error_message or "42" in error_message:
                Colors.info(f"Steam API Info: No matching items found (k_EResultNoMatch for AppID {STEAM_COMMUNITY_APPID}, ContextID {TRADING_CARD_CONTEXT_ID}). This can mean an empty inventory for this context. Assuming 0 cards for game {game_app_id_to_filter_for}.")
                return 0
            Colors.error(f"Steam API Error: {error_message}")
            if "private" in error_message.lower():
                Colors.warning("Hint: The inventory might be private.")
            return -1

        if "assets" not in data or "descriptions" not in data:
            Colors.info(f"No 'assets' or 'descriptions' in inventory data for AppID {STEAM_COMMUNITY_APPID}, ContextID {TRADING_CARD_CONTEXT_ID} (or inventory is private/empty). Assuming 0 cards for game {game_app_id_to_filter_for}.")
            return 0

        card_count = 0
        description_map = {desc["classid"]: desc for desc in data.get("descriptions", [])}

        for asset in data.get("assets", []):
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
                    card_count += int(asset.get("amount", 1))

        Colors.debug(f"Found {card_count} card(s) for Game AppID {game_app_id_to_filter_for} within Steam Community Inventory.")
        return card_count

    except requests.exceptions.Timeout:
        Colors.error("Timeout while fetching inventory.")
        return -1
    except requests.exceptions.HTTPError as e:
        Colors.error(f"HTTP error fetching inventory: {e}")
        if e.response is not None:
            if e.response.status_code == 403:
                 Colors.warning("Hint: Inventory might be private or inaccessible.")
            elif e.response.status_code == 429:
                 Colors.warning("Hint: Rate limited by Steam (HTTP 429). Try again later or increase monitoring interval.")
            Colors.debug(f"Response text (first 200 chars): {e.response.text[:200]}...")
        return -1
    except requests.exceptions.RequestException as e:
        Colors.error(f"General network error fetching inventory: {e}")
        return -1
    except ValueError:
        Colors.error("Could not decode inventory JSON. Is the inventory public and format valid?")
        if 'response' in locals() and response:
             Colors.debug(f"Response text (first 200 chars): {response.text[:200]}...")
        return -1

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

# --- Main Application Logic ---
def process_single_game(app_id_to_idle, target_mode, target_value, monitoring_interval, steam_id_64):
    Colors.info(f"--- Processing Game AppID: {app_id_to_idle} ---")
    if target_mode == 't':
        Colors.info(f"Mode: Total. Aiming for {target_value} card(s) for this game.")
    elif target_mode == 'r':
        Colors.info(f"Mode: Remaining. Aiming for {target_value} additional card(s) for this game.")
    Colors.info(f"Inventory check interval: {monitoring_interval} seconds.")

    steam_simulator = SteamSimulator(app_id_to_idle)
    if not steam_simulator.init_steam():
        Colors.error(f"Failed to initialize Steam simulation for AppID {app_id_to_idle}. Skipping this game.")
        return False

    Colors.info(f"Fetching initial card count for AppID {app_id_to_idle} (SteamID64: {steam_id_64})...")
    initial_cards = get_steam_inventory_card_count(steam_id_64, app_id_to_idle)

    if initial_cards == -1:
        Colors.error(f"Could not get initial card count for AppID {app_id_to_idle}. Ensure inventory is public and accessible. Skipping this game.")
        steam_simulator.shutdown_steam()
        return False

    Colors.info(f"Initial card count for AppID {app_id_to_idle}: {initial_cards}.")

    actual_target_total_cards = 0
    if target_mode == 't':
        actual_target_total_cards = target_value
    elif target_mode == 'r':
        actual_target_total_cards = initial_cards + target_value
        Colors.info(f"Current cards: {initial_cards}. Aiming for {target_value} more, so targeting a new total of {actual_target_total_cards} card(s).")

    if target_mode == 't':
        if initial_cards >= actual_target_total_cards:
            Colors.info(f"Already have {initial_cards} card(s), which meets or exceeds the target total of {actual_target_total_cards}. Skipping AppID {app_id_to_idle}.")
            steam_simulator.shutdown_steam()
            return True

    Colors.info(f"Monitoring AppID {app_id_to_idle} until inventory total reaches {actual_target_total_cards} card(s)... Press Ctrl+C to stop early for this game.")

    current_total_cards_in_inventory = initial_cards
    try:
        while current_total_cards_in_inventory < actual_target_total_cards:
            steam_simulator.run_callbacks()

            Colors.debug(f"Waiting for {monitoring_interval} seconds before next inventory check for AppID {app_id_to_idle}...")
            time.sleep(monitoring_interval)

            fetched_cards = get_steam_inventory_card_count(steam_id_64, app_id_to_idle)
            if fetched_cards == -1:
                Colors.warning(f"Failed to check inventory for AppID {app_id_to_idle} on this cycle. Will retry.")
                continue

            if fetched_cards > current_total_cards_in_inventory:
                Colors.info(f"[AppID {app_id_to_idle}] Card drop(s) detected! Inventory now has {fetched_cards} card(s) (was {current_total_cards_in_inventory}).")
            elif fetched_cards < current_total_cards_in_inventory:
                Colors.warning(f"[AppID {app_id_to_idle}] Card count decreased from {current_total_cards_in_inventory} to {fetched_cards}.")

            current_total_cards_in_inventory = fetched_cards

            if current_total_cards_in_inventory >= actual_target_total_cards:
                Colors.info(f"[AppID {app_id_to_idle}] Target total of {actual_target_total_cards} card(s) reached! Current total: {current_total_cards_in_inventory}.")
                break
            else:
                remaining_needed_for_target_total = actual_target_total_cards - current_total_cards_in_inventory
                Colors.info(f"[AppID {app_id_to_idle}] Current: {current_total_cards_in_inventory}/{actual_target_total_cards}. Need {remaining_needed_for_target_total} more card(s) to reach target total.")

    except KeyboardInterrupt:
        Colors.info(f"\nMonitoring for AppID {app_id_to_idle} interrupted by user (Ctrl+C).")
    finally:
        Colors.info(f"Stopping game simulation for AppID {app_id_to_idle}...")
        steam_simulator.shutdown_steam()
        Colors.info(f"--- Finished processing Game AppID: {app_id_to_idle} ---")
    return True

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
    monitoring_interval = args.interval # This is the effective interval to use

    game_name = get_game_name(app_id_to_idle) # Fetch game name

    Colors.info(f"--- YASI: Yet Another Steam Idler ---")
    Colors.info(
        f"Targeting AppID: {app_id_to_idle} ({game_name}) "
        f"with card target: '{target_spec}'"
    )
    Colors.info(f"Monitoring interval: {monitoring_interval} seconds.")

    # USER_STEAM_ID_64 is now used directly. Checks are done in load_configuration().

    # --- Initial Card Count Check (Before Steam Init) ---
    Colors.info(
        f"Performing initial card count check for AppID {app_id_to_idle} "
        f"({game_name})..."
    )
    initial_card_count = get_steam_inventory_card_count(
        USER_STEAM_ID_64, app_id_to_idle
    )

    if initial_card_count == -1:
        Colors.error(
            f"Failed to get initial card count for AppID {app_id_to_idle} "
            f"({game_name}). Cannot proceed reliably."
        )
        sys.exit(1)

    Colors.info(
        f"Initial card count for AppID {app_id_to_idle} ({game_name}): "
        f"{initial_card_count}"
    )

    target_card_count, check_for_any_new_card = determine_target_card_count(
        initial_card_count, target_spec
    )
    if target_card_count is None:
        sys.exit(1) # Error message already printed by determine_target_card_count

    if not check_for_any_new_card and initial_card_count >= target_card_count:
        Colors.info(
            f"Target of {target_card_count} card(s) for AppID "
            f"{app_id_to_idle} ({game_name}) already met or exceeded "
            f"(current: {initial_card_count}). No idling needed."
        )
        sys.exit(0)

    Colors.info(
        f"Proceeding to initialize Steam simulation for "
        f"AppID {app_id_to_idle} ({game_name})."
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
            f"to drop * {MAX_IDLE_MINUTES_PER_CARD} min/card)"
        )
    # --- End of Initial Card Count Check ---

    simulator = SteamSimulator(app_id_to_idle)
    if not simulator.init_steam():
        Colors.error(f"Failed to initialize Steam simulation for AppID {app_id_to_idle} ({game_name}). Exiting.")
        sys.exit(1)

    try:
        current_card_count = initial_card_count
        Colors.info(
            f"Monitoring for card drops for AppID {app_id_to_idle} "
            f"({game_name}). Target: {target_card_count} card(s). "
            f"Checking every {monitoring_interval}s."
        )
        last_check_time = time.time()
        start_idle_time = time.time() # Record when idling starts

        while True:
            simulator.run_callbacks()

            # Check for max idle time limit
            if max_idle_time_seconds > 0: # Only if a limit was set
                elapsed_idle_time = time.time() - start_idle_time
                if elapsed_idle_time >= max_idle_time_seconds:
                    max_minutes_reached = max_idle_time_seconds / 60
                    Colors.warning(
                        f"Max idle time (~{max_minutes_reached:.0f} min) "
                        f"reached for AppID {app_id_to_idle} ({game_name})."
                    )
                    break # Exit the idling loop

            if current_card_count >= target_card_count:
                Colors.info(
                    f"Target of {target_card_count} cards met for AppID "
                    f"{app_id_to_idle} ({game_name}). Current: {current_card_count}."
                )
                break

            current_time = time.time()
            if current_time - last_check_time >= monitoring_interval:
                Colors.info(f"Checking inventory for AppID {app_id_to_idle} ({game_name})...")
                fresh_inventory_count = get_steam_inventory_card_count(USER_STEAM_ID_64, app_id_to_idle)
                last_check_time = current_time

                if fresh_inventory_count == -1:
                    Colors.warning(f"Failed to fetch inventory count during monitoring for AppID {app_id_to_idle} ({game_name}). Will retry.")
                elif fresh_inventory_count > current_card_count:
                    Colors.info(f"New card drop detected for AppID {app_id_to_idle} ({game_name})! Count increased from {current_card_count} to {fresh_inventory_count}.")
                    current_card_count = fresh_inventory_count
                elif fresh_inventory_count < current_card_count:
                    Colors.warning(f"Card count for AppID {app_id_to_idle} ({game_name}) decreased from {current_card_count} to {fresh_inventory_count}. This is unusual. Continuing.")
                    current_card_count = fresh_inventory_count
                else:
                    Colors.info(f"No new cards detected for AppID {app_id_to_idle} ({game_name}). Current count: {current_card_count}.")

            time.sleep(1)
    except KeyboardInterrupt:
        Colors.info(f"\nMonitoring for AppID {app_id_to_idle} ({game_name}) interrupted by user (Ctrl+C).")
    finally:
        Colors.info(f"Stopping game simulation for AppID {app_id_to_idle} ({game_name})...")
        simulator.shutdown_steam()
        Colors.info(f"--- Finished processing Game AppID: {app_id_to_idle} ({game_name}) ---")

if __name__ == "__main__":
    main()
