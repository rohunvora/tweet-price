#!/usr/bin/env python3
"""
Add a new asset to the tweet-price tracker.

This script orchestrates the entire process:
1. Validates inputs (Twitter handle, CoinGecko ID, etc.)
2. Adds the asset to assets.json
3. Fetches tweets from the founder
4. Fetches price data
5. Computes statistics
6. Exports static files for the frontend
7. Caches the founder's avatar

Usage:
    # CoinGecko-listed token (simplest)
    python add_asset.py mytoken --name "My Token" --founder someuser --coingecko my-token-id

    # Solana DEX token (needs pool address)
    python add_asset.py mytoken --name "My Token" --founder someuser \\
        --network solana --pool 0x123... --mint 0xabc...

    # Update existing asset (re-fetch data)
    python add_asset.py mytoken --refresh

    # Validate only (don't add or fetch)
    python add_asset.py mytoken --name "My Token" --founder someuser --coingecko my-token-id --dry-run
"""
import argparse
import json
import subprocess
import sys
import time
import httpx
from pathlib import Path
from datetime import datetime

from config import (
    ASSETS_FILE,
    X_BEARER_TOKEN,
    X_API_BASE,
    PROJECT_ROOT,
)

# ANSI colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_step(msg: str):
    """Print a step header."""
    print(f"\n{BLUE}{BOLD}▶ {msg}{RESET}")


def print_success(msg: str):
    """Print a success message."""
    print(f"{GREEN}✓ {msg}{RESET}")


def print_error(msg: str):
    """Print an error message."""
    print(f"{RED}✗ {msg}{RESET}")


def print_warning(msg: str):
    """Print a warning message."""
    print(f"{YELLOW}⚠ {msg}{RESET}")


def validate_twitter_handle(username: str) -> tuple[bool, str]:
    """Check if Twitter handle exists. Returns (success, message)."""
    if not X_BEARER_TOKEN:
        return True, "Skipped (no X_BEARER_TOKEN)"

    url = f"{X_API_BASE}/users/by/username/{username}"
    headers = {"Authorization": f"Bearer {X_BEARER_TOKEN}"}

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                name = data.get("data", {}).get("name", username)
                return True, f"Found: {name} (@{username})"
            elif response.status_code == 404:
                return False, f"User @{username} not found"
            else:
                return False, f"Twitter API error: {response.status_code}"
    except Exception as e:
        return False, f"Network error: {e}"


def validate_coingecko_id(cg_id: str) -> tuple[bool, str]:
    """Check if CoinGecko ID exists. Returns (success, message)."""
    url = f"https://api.coingecko.com/api/v3/coins/{cg_id}"

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            if response.status_code == 200:
                data = response.json()
                name = data.get("name", cg_id)
                symbol = data.get("symbol", "").upper()
                return True, f"Found: {name} ({symbol})"
            elif response.status_code == 404:
                return False, f"CoinGecko ID '{cg_id}' not found"
            else:
                return False, f"CoinGecko API error: {response.status_code}"
    except Exception as e:
        return False, f"Network error: {e}"


def load_assets() -> dict:
    """Load assets.json config."""
    with open(ASSETS_FILE) as f:
        return json.load(f)


def save_assets(config: dict):
    """Save assets.json config."""
    with open(ASSETS_FILE, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def asset_exists(config: dict, asset_id: str) -> bool:
    """Check if asset already exists."""
    return any(a["id"] == asset_id for a in config.get("assets", []))


def add_asset_to_config(
    config: dict,
    asset_id: str,
    name: str,
    founder: str,
    coingecko_id: str = None,
    network: str = None,
    pool_address: str = None,
    token_mint: str = None,
    color: str = "#3B82F6",
    launch_date: str = None,
) -> dict:
    """Add a new asset to the config."""

    # Determine price source based on inputs
    if network and pool_address:
        price_source = "geckoterminal"
        backfill_source = "birdeye" if network == "solana" else None
    elif coingecko_id:
        price_source = "coingecko"
        backfill_source = None
        network = network or "ethereum"  # Default for CoinGecko tokens
    else:
        raise ValueError("Must provide either coingecko_id or (network + pool_address)")

    asset = {
        "id": asset_id,
        "name": name,
        "founder": founder,
        "network": network,
        "pool_address": pool_address,
        "token_mint": token_mint,
        "coingecko_id": coingecko_id,
        "price_source": price_source,
        "backfill_source": backfill_source,
        "launch_date": launch_date or datetime.now().strftime("%Y-%m-%dT00:00:00Z"),
        "color": color,
        "enabled": True,
        "logo": f"/logos/{asset_id}.png",
    }

    # Remove None values for cleaner JSON
    asset = {k: v for k, v in asset.items() if v is not None}

    config["assets"].append(asset)
    return config


def run_script(script_name: str, args: list = None) -> bool:
    """Run a Python script and return success status."""
    cmd = [sys.executable, str(PROJECT_ROOT / "scripts" / script_name)]
    if args:
        cmd.extend(args)

    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT / "scripts",
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )

        if result.returncode != 0:
            print(f"  stdout: {result.stdout[-500:] if result.stdout else '(empty)'}")
            print(f"  stderr: {result.stderr[-500:] if result.stderr else '(empty)'}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print_error(f"Script timed out after 10 minutes")
        return False
    except Exception as e:
        print_error(f"Failed to run script: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Add a new asset to the tweet-price tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # CoinGecko-listed token
  python add_asset.py mytoken --name "My Token" --founder user123 --coingecko my-token-id

  # Solana DEX token
  python add_asset.py mytoken --name "My Token" --founder user123 --network solana --pool 0x123...

  # Update existing asset
  python add_asset.py mytoken --refresh
        """,
    )

    parser.add_argument("asset_id", help="Unique asset ID (lowercase, no spaces)")
    parser.add_argument("--name", help="Display name for the asset")
    parser.add_argument("--founder", help="Twitter handle of the founder (without @)")
    parser.add_argument("--coingecko", dest="coingecko_id", help="CoinGecko ID for price data")
    parser.add_argument("--network", choices=["solana", "ethereum", "bsc", "base"], help="Blockchain network")
    parser.add_argument("--pool", dest="pool_address", help="DEX pool address (for GeckoTerminal)")
    parser.add_argument("--mint", dest="token_mint", help="Token mint/contract address")
    parser.add_argument("--color", default="#3B82F6", help="Brand color (hex, default: #3B82F6)")
    parser.add_argument("--launch-date", help="Launch date (YYYY-MM-DD)")
    parser.add_argument("--refresh", action="store_true", help="Refresh data for existing asset")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, don't add or fetch")
    parser.add_argument("--skip-tweets", action="store_true", help="Skip tweet fetching")
    parser.add_argument("--skip-prices", action="store_true", help="Skip price fetching")

    args = parser.parse_args()

    print("=" * 60)
    print(f"{BOLD}Add Asset: {args.asset_id}{RESET}")
    print("=" * 60)

    # Load existing config
    config = load_assets()
    exists = asset_exists(config, args.asset_id)

    # Handle refresh mode
    if args.refresh:
        if not exists:
            print_error(f"Asset '{args.asset_id}' not found. Use without --refresh to add it.")
            sys.exit(1)
        print(f"Refreshing existing asset: {args.asset_id}")
    else:
        # Validate required fields for new asset
        if exists:
            print_error(f"Asset '{args.asset_id}' already exists. Use --refresh to update it.")
            sys.exit(1)

        if not args.name:
            print_error("--name is required for new assets")
            sys.exit(1)
        if not args.founder:
            print_error("--founder is required for new assets")
            sys.exit(1)
        if not args.coingecko_id and not args.pool_address:
            print_error("Must provide --coingecko or --pool for price data")
            sys.exit(1)

    # Validation step
    print_step("Validating inputs")

    if not args.refresh:
        # Validate Twitter handle
        print(f"  Checking Twitter handle @{args.founder}...")
        success, msg = validate_twitter_handle(args.founder)
        if success:
            print_success(f"  {msg}")
        else:
            print_error(f"  {msg}")
            sys.exit(1)

        # Validate CoinGecko ID if provided
        if args.coingecko_id:
            print(f"  Checking CoinGecko ID '{args.coingecko_id}'...")
            success, msg = validate_coingecko_id(args.coingecko_id)
            if success:
                print_success(f"  {msg}")
            else:
                print_error(f"  {msg}")
                sys.exit(1)

        # Validate pool address format if provided
        if args.pool_address:
            if not args.network:
                print_error("--network is required when using --pool")
                sys.exit(1)
            print_success(f"  Pool: {args.pool_address[:20]}... on {args.network}")

    if args.dry_run:
        print_success("\nDry run complete - validation passed!")
        print("Run without --dry-run to add the asset and fetch data.")
        sys.exit(0)

    # Add to config (if new)
    if not args.refresh:
        print_step("Adding to assets.json")

        launch_date = None
        if args.launch_date:
            launch_date = f"{args.launch_date}T00:00:00Z"

        config = add_asset_to_config(
            config,
            args.asset_id,
            args.name,
            args.founder,
            coingecko_id=args.coingecko_id,
            network=args.network,
            pool_address=args.pool_address,
            token_mint=args.token_mint,
            color=args.color,
            launch_date=launch_date,
        )
        save_assets(config)
        print_success(f"Added {args.asset_id} to assets.json")

    # Run pipeline scripts
    steps = []

    if not args.skip_tweets:
        steps.append(("Fetching tweets", "fetch_tweets.py", ["--asset", args.asset_id]))

    if not args.skip_prices:
        steps.append(("Fetching prices", "fetch_prices.py", ["--asset", args.asset_id]))

    steps.extend([
        ("Computing statistics", "compute_stats.py", ["--asset", args.asset_id]),
        ("Exporting static files", "export_static.py", ["--asset", args.asset_id]),
        ("Caching avatar", "cache_avatars.py", ["--asset", args.asset_id]),
    ])

    failed = False
    for step_name, script, script_args in steps:
        print_step(step_name)
        if run_script(script, script_args):
            print_success(f"  {step_name} complete")
        else:
            print_error(f"  {step_name} failed")
            failed = True
            # Continue with other steps even if one fails

    # Summary
    print("\n" + "=" * 60)
    if failed:
        print(f"{YELLOW}⚠ Asset added with some errors{RESET}")
        print("Check the output above for details.")
        print("You may need to re-run with --refresh after fixing issues.")
    else:
        print(f"{GREEN}{BOLD}✓ Asset '{args.asset_id}' added successfully!{RESET}")
        print(f"\nNext steps:")
        print(f"  1. Add a logo to: web/public/logos/{args.asset_id}.png")
        print(f"  2. Commit and push to deploy")
        print(f"     git add -A && git commit -m 'Add asset: {args.name or args.asset_id}'")
        print(f"     git push")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
