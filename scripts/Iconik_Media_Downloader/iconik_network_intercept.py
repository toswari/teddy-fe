#!/usr/bin/env python3
"""
Iconik Downloader - Intercept actual download URLs when browser accesses files
"""

import asyncio
import json
import requests
from pathlib import Path
from playwright.async_api import async_playwright


async def download_via_network_intercept(share_url, output_dir="downloads"):
    """
    Use browser to trigger downloads and intercept the signed S3 URLs
    """
    output_path = Path(output_dir).absolute()
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Iconik Downloader - Network Interception Method")
    print(f"URL: {share_url}")
    print(f"Output: {output_path}")
    print("=" * 60)
    
    downloads = []
    download_urls = {}
    
    async with async_playwright() as p:
        print("\nLaunching browser...")
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Intercept download requests
        async def handle_route(route, request):
            url = request.url
            
            # Intercept signed S3 URLs or media file requests (video AND images)
            media_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.tiff', '.bmp', '.heic']
            if any(ext in url.lower() for ext in media_extensions) and ('amazonaws.com' in url or 'storage.googleapis.com' in url):
                # Extract filename from URL or headers
                filename = url.split('/')[-1].split('?')[0]
                if not filename or '.' not in filename:
                    # Detect file type from URL or use generic name
                    if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                        filename = f"image_{len(download_urls)}.jpg"
                    else:
                        filename = f"media_{len(download_urls)}.bin"
                
                # Only add if we haven't seen this filename yet (avoid duplicates)
                if filename not in download_urls:
                    print(f"\n✓ Intercepted download URL: {url[:100]}...")
                    download_urls[filename] = url
            
            # Continue the request normally
            await route.continue_()
        
        # Enable request interception
        await page.route("**/*", handle_route)
        
        try:
            # Load the page
            print("Loading share page...")
            await page.goto(share_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)
            
            print("✓ Page loaded")
            print("\nLooking for asset elements...")
            
            # Wait for assets to load
            await page.wait_for_selector('[class*="AssetTile"], [class*="asset"], .asset-item, [data-testid*="asset"]', timeout=10000)
            
            # Get all clickable asset elements
            # Try multiple selector strategies
            selectors = [
                '[class*="AssetTile"]',
                '[class*="asset-tile"]', 
                '[class*="GridItem"]',
                'div[role="button"]',
                'a[href*="asset"]',
                '[data-testid*="asset"]'
            ]
            
            asset_elements = []
            for selector in selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    print(f"  Found {len(elements)} elements with selector: {selector}")
                    asset_elements = elements
                    break
            
            if not asset_elements:
                print("  No asset elements found. Trying to get all clickable elements...")
                asset_elements = await page.query_selector_all('div[role="button"], a, button')
                print(f"  Found {len(asset_elements)} clickable elements")
            
            num_assets = len(asset_elements)
            print(f"\nAttempting to trigger downloads for {num_assets} elements...")
            
            for idx in range(num_assets):
                try:
                    print(f"\n[{idx + 1}/{num_assets}] Re-querying elements...")
                    
                    # Re-query elements each time to avoid stale references
                    current_elements = await page.query_selector_all('a[href*="asset"]')
                    if idx >= len(current_elements):
                        print(f"  ✗ Element index out of range")
                        continue
                    
                    element = current_elements[idx]
                    
                    # Get element info
                    tag_name = await element.evaluate('el => el.tagName')
                    class_name = await element.evaluate('el => el.className')
                    print(f"  Tag: {tag_name}, Class: {class_name[:50] if class_name else 'none'}")
                    
                    # Click and wait for navigation or response
                    print(f"  Clicking...")
                    await element.click(timeout=5000)
                    await asyncio.sleep(3)
                    
                    # Look for download button in modal/overlay
                    download_selectors = [
                        'button:has-text("Download")',
                        'a:has-text("Download")',
                        '[aria-label*="Download"]',
                        '[title*="Download"]',
                        'button[class*="download"]',
                        'a[class*="download"]'
                    ]
                    
                    for dl_selector in download_selectors:
                        try:
                            dl_button = await page.query_selector(dl_selector)
                            if dl_button:
                                print(f"  ✓ Found download button: {dl_selector}")
                                await dl_button.click(timeout=5000)
                                await asyncio.sleep(3)
                                break
                        except:
                            continue
                    
                    # Try to close modal and go back
                    close_selectors = ['button:has-text("Close")', '[aria-label="Close"]', 'button[class*="close"]', '.modal-close', '.close']
                    for close_selector in close_selectors:
                        try:
                            close_btn = await page.query_selector(close_selector)
                            if close_btn:
                                await close_btn.click(timeout=2000)
                                await asyncio.sleep(1)
                                break
                        except:
                            continue
                    
                    # If modal didn't close, try going back
                    try:
                        await page.go_back(wait_until="domcontentloaded", timeout=5000)
                        await asyncio.sleep(2)
                    except:
                        pass
                    
                except Exception as e:
                    print(f"  ✗ Error: {e}")
                    continue
            
            print("\n\nWaiting for any remaining network requests...")
            await asyncio.sleep(5)
            
        finally:
            await browser.close()
    
    # Download all intercepted URLs
    if download_urls:
        print(f"\n{'=' * 60}")
        print(f"Downloading {len(download_urls)} intercepted files...")
        print(f"{'=' * 60}\n")
        
        for filename, url in download_urls.items():
            try:
                print(f"Downloading {filename}...")
                response = requests.get(url, stream=True, timeout=300)
                response.raise_for_status()
                
                save_path = output_path / filename
                counter = 1
                original_path = save_path
                while save_path.exists():
                    stem = original_path.stem
                    suffix = original_path.suffix
                    save_path = original_path.parent / f"{stem}_{counter}{suffix}"
                    counter += 1
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192 * 16):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size:
                                pct = (downloaded / total_size) * 100
                                print(f"\r  Progress: {pct:.1f}% ({downloaded / 1024 / 1024:.1f}/{total_size / 1024 / 1024:.1f} MB)", end='', flush=True)
                
                print(f"\n  ✓ Saved: {save_path.name}")
                downloads.append(save_path.name)
                
            except Exception as e:
                print(f"\n  ✗ Error: {e}")
                continue
    else:
        print("\n✗ No download URLs intercepted")
        print("The download may use a different mechanism (blob URLs, service worker, etc.)")
    
    return downloads


async def main():
    import sys
    
    url = sys.argv[1] if len(sys.argv) > 1 else "https://icnk.io/u/-HlYaqS3Mdnm/"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "Customer_Provided_Data"
    
    downloads = await download_via_network_intercept(url, output_dir)
    
    print("\n" + "=" * 60)
    print(f"DOWNLOAD COMPLETE")
    print(f"  Successfully downloaded: {len(downloads)} files")
    for f in downloads:
        print(f"    ✓ {f}")
    print(f"  Location: {Path(output_dir).absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
