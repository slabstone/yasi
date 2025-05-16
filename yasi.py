import sys
import time
import requests
import os
import ctypes # Added for direct DLL interaction
import argparse # Added for argument parsing

# --- Color Codes ---
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m' # Resets the color

    @staticmethod
    def _print_color(color_code, message_type, message):
        print(f"{color_code}[{message_type}] {message}{Colors.ENDC}")

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

# --- Constants ---
USER_STEAM_VANITY_NAME = "queendom" # As per your request
DEFAULT_MONITORING_INTERVAL_SECONDS = 300 # Check inventory every 5 minutes (300 seconds)

# --- Steamworks Simulation ---
class SteamSimulator:
    """
    Manages the simulation of running a game via Steamworks
    by directly loading and calling steam_api64.dll using ctypes.
    Requires steam_api64.dll.
    """
    def __init__(self, app_id_str):
        self.app_id_str = str(app_id_str) # Ensure app_id is a string for the file
        self.steam_appid_file = "steam_appid.txt"
        self.steam_api_dll = None
        self._load_steam_api_dll()

    def _load_steam_api_dll(self):
        """Loads steam_api64.dll and defines necessary function prototypes."""
        try:
            # Construct the path to steam_api64.dll, assuming it's in the same directory as the script.
            dll_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "steam_api64.dll")
            
            if not os.path.exists(dll_path):
                Colors.error(f"steam_api64.dll not found at {dll_path}")
                Colors.error("Ensure 'steam_api64.dll' from your SDK's 'redistributable_bin/win64/'")
                Colors.error("is copied to the same directory as this yasi.py script.")
                return

            Colors.debug(f"Attempting to load DLL: {dll_path}")
            self.steam_api_dll = ctypes.CDLL(dll_path)
            Colors.info("steam_api64.dll loaded successfully.")

            # Define function prototypes for the Steam API functions we need.
            # bool SteamAPI_InitSafe(); (Replaced SteamAPI_Init)
            self.steam_api_dll.SteamAPI_InitSafe.restype = ctypes.c_bool
            self.steam_api_dll.SteamAPI_InitSafe.argtypes = []

            # void SteamAPI_RunCallbacks();
            self.steam_api_dll.SteamAPI_RunCallbacks.restype = None
            self.steam_api_dll.SteamAPI_RunCallbacks.argtypes = []

            # void SteamAPI_Shutdown();
            self.steam_api_dll.SteamAPI_Shutdown.restype = None
            self.steam_api_dll.SteamAPI_Shutdown.argtypes = []

        except OSError as e:
            Colors.error(f"Could not load or access steam_api64.dll: {e}")
            Colors.error("Ensure the DLL is not corrupted and is accessible.")
            self.steam_api_dll = None
        except AttributeError as e:
            Colors.error(f"A required SteamAPI function (e.g., SteamAPI_InitSafe, SteamAPI_RunCallbacks, SteamAPI_Shutdown) was not found in steam_api64.dll: {e}")
            Colors.error("This might indicate an incorrect, outdated, or corrupted steam_api64.dll.")
            self.steam_api_dll = None
        except Exception as e:
            Colors.error(f"An unexpected error occurred while loading steam_api64.dll: {e}")
            self.steam_api_dll = None

    def init_steam(self):
        if not self.steam_api_dll:
            Colors.error("Steam API DLL not loaded. Cannot initialize Steam simulation.")
            return False

        Colors.info(f"Initializing Steam for AppID: {self.app_id_str} (via direct DLL call)...")
        
        # Create steam_appid.txt: This file tells the Steam client which game to simulate.
        try:
            with open(self.steam_appid_file, "w") as f:
                f.write(self.app_id_str)
            Colors.debug(f"Created {self.steam_appid_file} with AppID {self.app_id_str}.")
        except IOError as e:
            Colors.error(f"Could not create {self.steam_appid_file}: {e}")
            return False

        # Initialize Steamworks. This requires:
        # 1. Steam client running.
        # 2. steam_api64.dll accessible (handled by _load_steam_api_dll).
        # 3. steam_appid.txt present in the current working directory.
        try:
            if not self.steam_api_dll.SteamAPI_InitSafe(): # Changed from SteamAPI_Init
                 Colors.error("Failed to initialize Steamworks (SteamAPI_InitSafe() returned False).") # Changed message
                 Colors.error("Ensure Steam client is running. The game might also need to be in your library.")
                 self._cleanup_appid_file()
                 return False
            
            Colors.info("Steamworks initialized successfully via direct DLL call.")
            Colors.info(f"Steam should now show you as playing game with AppID {self.app_id_str}.")
            return True
        except Exception as e: 
            Colors.error(f"An unexpected error occurred during SteamAPI_InitSafe: {e}") # Changed message
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
        self._cleanup_appid_file()

    def _cleanup_appid_file(self):
        if os.path.exists(self.steam_appid_file):
            try:
                os.remove(self.steam_appid_file)
                Colors.debug(f"Removed {self.steam_appid_file}.")
            except OSError as e:
                Colors.warning(f"Could not remove {self.steam_appid_file}: {e}")
    
    def run_callbacks(self):
        """Call this periodically to keep Steamworks connection alive."""
        if self.steam_api_dll:
            try:
                self.steam_api_dll.SteamAPI_RunCallbacks()
            except Exception as e:
                Colors.error(f"An error occurred during SteamAPI_RunCallbacks: {e}")

# --- Steam Inventory Functions ---
def resolve_vanity_to_steamid64(vanity_name, app_id_for_test=None):
    """
    Resolves a vanity URL to SteamID64.
    Currently hardcoded for 'queendom', provides guidance for others.
    """
    if vanity_name.lower() == "queendom":
        # Pre-resolved SteamID64 for "queendom"
        return "76561198029858508" # Updated SteamID
    
    # Check if the provided name is already a SteamID64
    if len(vanity_name) == 17 and vanity_name.startswith("7656") and vanity_name.isdigit():
        Colors.info(f"'{vanity_name}' appears to be a SteamID64. Using it directly.")
        return vanity_name

    Colors.info(f"Automatic vanity URL resolution for '{vanity_name}' is not implemented.")
    Colors.info("      Please use your 64-bit SteamID (a 17-digit number starting with 7656).")
    Colors.info("      You can find it on sites like 'steamid.io' or from your Steam profile URL.")
    
    # Optional: Test if the vanity name works as a SteamID for inventory (simple heuristic)
    if app_id_for_test:
        test_url = f"https://steamcommunity.com/inventory/{vanity_name}/{app_id_for_test}/2?l=english&count=1"
        headers = {  # Define headers for this test request as well
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            Colors.debug(f"Testing if '{vanity_name}' can be used as a SteamID for inventory access...")
            response = requests.get(test_url, timeout=10, headers=headers) # Added headers
            if response.status_code == 200:
                # Check if response.json() is successful and if Steam's own success flag is true
                try:
                    data = response.json()
                    if data.get("success", True) is not False: # Steam API often returns success:true or no success field on actual success
                        Colors.info(f"Inventory accessible with '{vanity_name}'. Assuming it's a valid SteamID64 or resolvable vanity name.")
                        return vanity_name
                    else:
                        # Steam API returned success:false or an error message
                        error_msg = data.get("Error", data.get("error", "Unknown error from Steam API"))
                        Colors.warning(f"Steam API indicated failure for '{vanity_name}': {error_msg}")
                except ValueError: # JSONDecodeError
                    Colors.warning(f"Could not decode JSON response when testing vanity name '{vanity_name}'. Might not be a valid ID.")
            else:
                Colors.warning(f"HTTP {response.status_code} when testing inventory access for '{vanity_name}'.")
        except requests.exceptions.RequestException as e:
            Colors.warning(f"Network error testing inventory access for '{vanity_name}': {e}")
        except Exception as e: # Catch any other unexpected error during the test
            Colors.warning(f"Unexpected error testing inventory access for '{vanity_name}': {e}")
    
    Colors.warning(f"Could not resolve or directly validate '{vanity_name}' as a SteamID64 for inventory access. Inventory checking might fail.")
    return vanity_name # Fallback to using it directly, might fail later

STEAM_COMMUNITY_APPID = "753" # AppID for Steam Community items (cards, emoticons, etc.)
TRADING_CARD_CONTEXT_ID = "6" # Context ID for Trading Cards, Badges, etc.

def get_steam_inventory_card_count(steam_id_64, game_app_id_to_filter_for):
    """
    Fetches the count of trading cards for a specific game from a user's public inventory.
    Cards are typically under Steam AppID 753 and Context ID 6, so we query that and then filter.
    Returns card count, or -1 on error.
    """
    inventory_url = f"https://steamcommunity.com/inventory/{steam_id_64}/{STEAM_COMMUNITY_APPID}/{TRADING_CARD_CONTEXT_ID}?l=english&count=5000"
    Colors.debug(f"Fetching inventory from: {inventory_url} (AppID: {STEAM_COMMUNITY_APPID}, ContextID: {TRADING_CARD_CONTEXT_ID}, filtering for game {game_app_id_to_filter_for})")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(inventory_url, timeout=20, headers=headers)
        response.raise_for_status()  # Raises HTTPError for bad responses (4XX or 5XX)
        data = response.json()

        if data is None or not isinstance(data, dict): # Check if data is None or not a dictionary
            Colors.error("Invalid JSON response or empty data from inventory.")
            if response:
                Colors.debug(f"Response text (first 200 chars): {response.text[:200]}...")
            return -1

        if data.get("success") is False: # Check for Steam's own error reporting
            error_message = data.get("Error", data.get("error", "Unknown error"))
            # Add specific check for k_EResultNoMatch (42) which can occur with valid 753 requests if empty for context
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
            # asset["appid"] will be STEAM_COMMUNITY_APPID (e.g., 753)
            # We need to check the description for the original game's appid
            desc = description_map.get(asset["classid"])
            if desc:
                # Check 1: market_fee_app (most reliable for items that can be on market)
                is_for_correct_game = False
                if str(desc.get("market_fee_app")) == str(game_app_id_to_filter_for):
                    is_for_correct_game = True
                
                # Check 2: Tags (fallback or additional check)
                # Sometimes the game is in tags like: {'category': 'Game', 'internal_name': 'appid_440', ...}
                if not is_for_correct_game and desc.get("tags"):
                    for tag in desc["tags"]:
                        if tag.get("category") == "Game" and tag.get("internal_name") == f"appid_{game_app_id_to_filter_for}":
                            is_for_correct_game = True
                            break
                
                if not is_for_correct_game:
                    continue # Not for the game we are idling

                is_card = False
                if desc.get("tags"):
                    for tag in desc["tags"]:
                        if (tag.get("category") == "item_class" and
                            tag.get("internal_name") == "item_class_2" and
                            tag.get("localized_tag_name") == "Trading Card"):
                            is_card = True
                            break
                if is_card: # Already confirmed it's for the correct game
                    card_count += int(asset.get("amount", 1))
        
        Colors.debug(f"Found {card_count} card(s) for Game AppID {game_app_id_to_filter_for} within Steam Community Inventory.")
        return card_count
        
    except requests.exceptions.Timeout:
        Colors.error("Timeout while fetching inventory.")
        return -1
    except requests.exceptions.HTTPError as e:
        Colors.error(f"HTTP error fetching inventory: {e}")
        if e.response is not None: # Ensure response object exists
            if e.response.status_code == 403: # Forbidden, often private inventory
                 Colors.warning("Hint: Inventory might be private or inaccessible.")
            elif e.response.status_code == 429: # Too many requests
                 Colors.warning("Hint: Rate limited by Steam (HTTP 429). Try again later or increase monitoring interval.")
            Colors.debug(f"Response text (first 200 chars): {e.response.text[:200]}...")
        return -1
    except requests.exceptions.RequestException as e:
        Colors.error(f"General network error fetching inventory: {e}")
        return -1
    except ValueError:  # Includes JSONDecodeError
        Colors.error("Could not decode inventory JSON. Is the inventory public and format valid?")
        if 'response' in locals() and response:
             Colors.debug(f"Response text (first 200 chars): {response.text[:200]}...")
        return -1

# --- Main Application Logic ---
def main():
    print("--- Yet Another Steam Idler (YASI) ---")
    Colors.info("This script simulates playing a Steam game to receive card drops.")
    Colors.info("Prerequisites: Python3, 'requests' library, running Steam client,")
    Colors.info("and 'steam_api64.dll' copied next to this script from your Steamworks SDK.")
    print("-" * 30)

    parser = argparse.ArgumentParser(description="Yet Another Steam Idler (YASI)")
    parser.add_argument("-a", "--app", type=int, required=True, help="The AppID of the game to idle.")
    parser.add_argument("-c", "--cards", type=int, required=True, help="The target total number of trading cards to have for this game.") # Updated help
    parser.add_argument("-i", "--interval", type=int, default=DEFAULT_MONITORING_INTERVAL_SECONDS, 
                        help=f"The interval in seconds to check for new card drops (default: {DEFAULT_MONITORING_INTERVAL_SECONDS} seconds).")

    args = parser.parse_args()

    app_id_to_idle = args.app
    target_total_cards = args.cards # Renamed variable
    monitoring_interval = args.interval

    if target_total_cards <= 0: # Target total should still be positive
        Colors.error("Target total number of cards must be a positive integer.")
        sys.exit(1)
    
    if monitoring_interval <= 0:
        Colors.error("Monitoring interval must be a positive integer.")
        sys.exit(1)

    Colors.info(f"Target Game AppID: {app_id_to_idle}")
    Colors.info(f"Steam User for Inventory: {USER_STEAM_VANITY_NAME}")
    # Updated log message to reflect target total
    Colors.info(f"Targeting a total of {target_total_cards} card(s) for this game.")
    Colors.info(f"Inventory check interval: {monitoring_interval} seconds.")

    steam_id_64 = resolve_vanity_to_steamid64(USER_STEAM_VANITY_NAME, app_id_to_idle)
    if not steam_id_64: 
        Colors.error("Critical Error: Could not determine SteamID64. Exiting.")
        sys.exit(1)
    Colors.info(f"Using SteamID64: {steam_id_64} for inventory checks.")

    steam_simulator = SteamSimulator(app_id_to_idle)
    if not steam_simulator.init_steam():
        Colors.error("Failed to initialize Steam simulation. Please check errors above. Exiting.")
        sys.exit(1)

    Colors.info("Fetching initial card count...")
    initial_cards = get_steam_inventory_card_count(steam_id_64, app_id_to_idle)
    if initial_cards == -1:
        Colors.error("Could not get initial card count. Ensure inventory is public and accessible.")
        steam_simulator.shutdown_steam()
        sys.exit(1)
    
    Colors.info(f"Initial card count for AppID {app_id_to_idle}: {initial_cards}.")

    if initial_cards >= target_total_cards:
        Colors.info(f"You already have {initial_cards} card(s), which meets or exceeds the target of {target_total_cards}. Nothing to do.")
        steam_simulator.shutdown_steam()
        sys.exit(0)

    Colors.info(f"Monitoring until a total of {target_total_cards} card(s) are in inventory... Press Ctrl+C to stop early.")

    current_total_cards_in_inventory = initial_cards
    try:
        while current_total_cards_in_inventory < target_total_cards:
            steam_simulator.run_callbacks() # Keep Steam connection alive

            Colors.debug(f"Waiting for {monitoring_interval} seconds before next inventory check...")
            time.sleep(monitoring_interval)

            fetched_cards = get_steam_inventory_card_count(steam_id_64, app_id_to_idle)
            if fetched_cards == -1:
                Colors.warning("Failed to check inventory on this cycle. Will retry.")
                continue # Skip this cycle

            if fetched_cards > current_total_cards_in_inventory:
                Colors.info(f"Card drop(s) detected! Inventory now has {fetched_cards} card(s) (was {current_total_cards_in_inventory}).")
            elif fetched_cards < current_total_cards_in_inventory:
                Colors.warning(f"Card count decreased from {current_total_cards_in_inventory} to {fetched_cards}.")
            # No special message if count is unchanged, will be covered by the status update below

            current_total_cards_in_inventory = fetched_cards # Update our tracked count

            if current_total_cards_in_inventory >= target_total_cards:
                Colors.info(f"Target of {target_total_cards} card(s) reached! Current total: {current_total_cards_in_inventory}.")
                break
            else:
                remaining_needed = target_total_cards - current_total_cards_in_inventory
                Colors.info(f"Current: {current_total_cards_in_inventory}/{target_total_cards}. Need {remaining_needed} more card(s).")
            
    except KeyboardInterrupt:
        Colors.info("\nMonitoring interrupted by user (Ctrl+C).")
    finally:
        Colors.info("Stopping game simulation...")
        steam_simulator.shutdown_steam()
        Colors.info("YASI finished.")

if __name__ == "__main__":
    main()
