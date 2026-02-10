#Requires -Version 5.1
<#
.SYNOPSIS
    Manages running yasi.py for multiple games specified in an input file.
.DESCRIPTION
    This script reads a file where each line contains a game AppID and a target card specification.
    It then executes yasi.py for each game.
.PARAMETER FilePath
    The path to the input file. Each line in the file should be in the format: <AppID> <TargetSpec>
    Example: 448780 r1
.EXAMPLE
    .\yasi_manager.ps1 -FilePath .\apps.txt
    .\yasi_manager.ps1 C:\path\to\your\gameslist.txt
#>
param (
    [Parameter(Mandatory=$false, Position=0)]
    [string]$FilePath = "apps.txt"
)

# Status prefix constants
$PREFIX_DONE = "# DONE "
$PREFIX_FAIL = "# FAIL "

# Function to update a line in apps.txt with a status prefix
function Update-AppLine {
    param(
        [string]$FilePath,
        [string]$OriginalLine,
        [string]$Prefix
    )

    # Skip if line already has a prefix
    if ($OriginalLine.TrimStart().StartsWith("#")) {
        return
    }

    try {
        $content = Get-Content -Path $FilePath -Raw
        $lines = $content -split "`r?`n"

        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($lines[$i] -eq $OriginalLine) {
                $lines[$i] = $Prefix + $OriginalLine
                break
            }
        }

        # Write back to file
        $lines -join "`r`n" | Set-Content -Path $FilePath -NoNewline
        Write-Host "Updated line in $FilePath with prefix: $Prefix"
    } catch {
        Write-Warning "Failed to update line in $FilePath : $($_.Exception.Message)"
    }
}

# Get the directory where this script is located
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$YasiScriptPath = Join-Path -Path $ScriptDir -ChildPath "yasi.py"
$ConfigPath = Join-Path -Path $ScriptDir -ChildPath "config.json"
$PythonExecutable = "python" # Or "python3" or the full path to your python.exe

# Load configuration
$Config = Get-Content -Raw -Path $ConfigPath | ConvertFrom-Json
$PauseBetweenGamesSeconds = $Config.pause_between_games_seconds

# Validate yasi.py exists
if (-not (Test-Path $YasiScriptPath)) {
    Write-Error "yasi.py not found at $YasiScriptPath. Please ensure it's in the same directory as this script."
    exit 1
}

# Validate input file exists
if (-not (Test-Path $FilePath)) {
    Write-Error "Input file not found: $FilePath"
    exit 1
}

Write-Host "--- YASI Manager (PowerShell) ---"
Write-Host "Using yasi.py from: $YasiScriptPath"
Write-Host "Reading game list from: $FilePath"
Write-Host "Pause between games: $PauseBetweenGamesSeconds seconds"
Write-Host "---------------------------------"

$gamesProcessedCount = 0
try {
    # Load file content into memory first to avoid file locking issues
    $fileLines = @(Get-Content $FilePath)

    foreach ($lineFromFile in $fileLines) {
        $line = $lineFromFile.Trim()
        $originalLine = $lineFromFile  # Capture original line (untrimmed) for updating later

        # Skip empty lines and comments (lines starting with # or //)
        if ($line -eq "" -or $line.StartsWith("#") -or $line.StartsWith("//")) {
            continue # Skips to the next line in foreach
        }

        $parts = $line -split '\s+' # Split by one or more whitespace characters

        if ($parts.Length -eq 2) {
            $rawAppIdInput = $parts[0]
            $targetSpec = $parts[1]
            $appId = $null # Initialize $appId

            # Try to extract AppID from URL patterns or treat as plain AppID
            if ($rawAppIdInput -match '/gamecards/(\d+)') { # Matches .../gamecards/APPID...
                $appId = $matches[1]
            } elseif ($rawAppIdInput -match '/app/(\d+)') { # Matches .../app/APPID... (e.g., store pages)
                $appId = $matches[1]
            } elseif ($rawAppIdInput -match '^\d+$') { # Matches if it's already a plain numeric AppID
                $appId = $rawAppIdInput
            }

            # Validate the extracted AppID
            if ($null -eq $appId) { # If $appId is still null, no valid pattern was matched
                Write-Warning "Skipping malformed line: '$line'. Could not extract a valid AppID from '$rawAppIdInput'."
                continue # Skips to the next line in foreach
            }

            # At this point, $appId should hold the numeric string AppID
            # The original validation 'if ($appId -notmatch '^\d+$')' is now implicitly handled by the extraction logic.

            if ($gamesProcessedCount -gt 0 -and $PauseBetweenGamesSeconds -gt 0) {
                Write-Host "Pausing for $PauseBetweenGamesSeconds seconds before next game..."
                Start-Sleep -Seconds $PauseBetweenGamesSeconds
            }

            Write-Host "--- Running YASI for AppID: $appId, Target: $targetSpec ---"
            $commandArgsArray = @("-a", $appId, "-c", $targetSpec) # Keep as array for clarity

            # Display the command that will be executed
            Write-Host "Executing: & `"$PythonExecutable`" `"$YasiScriptPath`" $($commandArgsArray -join ' ')"

            # Execute yasi.py directly, allowing its output to stream to the console
            try {
                & $PythonExecutable $YasiScriptPath @commandArgsArray
                $exitCode = $LASTEXITCODE

                if ($exitCode -eq 2) {
                    # Exit code 2 means Steam is not running - stop batch processing without marking as FAIL
                    Write-Host ""
                    Write-Host "========================================" -ForegroundColor Yellow
                    Write-Host "Steam is not running." -ForegroundColor Yellow
                    Write-Host "Stopping batch processing." -ForegroundColor Yellow
                    Write-Host "Please start Steam and run yasim again." -ForegroundColor Yellow
                    Write-Host "========================================" -ForegroundColor Yellow
                    Write-Host ""
                    exit 0
                } elseif ($exitCode -ne 0) {
                    Write-Warning "yasi.py exited with error code $exitCode for AppID $appId."
                    Update-AppLine -FilePath $FilePath -OriginalLine $originalLine -Prefix $PREFIX_FAIL
                } else {
                    Write-Host "Successfully processed AppID $appId."
                    Update-AppLine -FilePath $FilePath -OriginalLine $originalLine -Prefix $PREFIX_DONE
                }
            } catch {
                # This catch block handles errors if PowerShell fails to launch the process (e.g., python not found)
                Write-Error "An error occurred while trying to launch yasi.py for AppID ${appId}: $($_.Exception.Message)"
                Update-AppLine -FilePath $FilePath -OriginalLine $originalLine -Prefix $PREFIX_FAIL
            }

            $gamesProcessedCount++
            Write-Host "---------------------------------"
        } else {
            Write-Warning "Skipping malformed line: '$line'. Expected format: AppID TargetSpec"
        }
    }
} catch {
    Write-Error "An error occurred while reading or processing the file: $($_.Exception.Message)"
    exit 1
}

if ($gamesProcessedCount -eq 0) {
    Write-Host "No valid game entries found in $FilePath."
} else {
    Write-Host "Finished processing $gamesProcessedCount game(s) from $FilePath."
}

Write-Host "--- YASI Manager (PowerShell) Finished ---"
