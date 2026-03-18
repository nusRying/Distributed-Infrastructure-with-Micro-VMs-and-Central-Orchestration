import argparse
import asyncio
from playwright.async_api import async_playwright
import os
import sys

async def run_in_colab(notebook_url: str, code: str):
    # Using a persistent context so we can reuse Google login sessions.
    # The user must log in once manually and save cookies to `colab_profile`.
    user_data_dir = os.path.join(os.path.dirname(__file__), "colab_profile")

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )

        page = await browser.new_page()
        try:
            print(f"Navigating to {notebook_url}...", file=sys.stderr)
            await page.goto(notebook_url, wait_until="networkidle")

            # Check if we are being asked to login
            if "accounts.google.com" in page.url:
                print("Error: You need to log in to Google first. Please run this script with headless=False once to log in.", file=sys.stderr)
                await browser.close()
                sys.exit(1)

            # Wait for Colab to load completely
            await page.wait_for_selector('colab-status-bar', timeout=60000)
            print("Notebook loaded. Injecting new cell...", file=sys.stderr)

            # Wait a moment for dynamic elements to settle
            await page.wait_for_timeout(3000)

            # Click the '+ Code' button in the toolbar
            # Usually it's within a colab-toolbar-button element
            add_code_btn = page.locator('colab-toolbar-button#toolbar-add-code')
            if await add_code_btn.count() > 0:
                await add_code_btn.click()
            else:
                # Fallback to shortcut (Ctrl+M B -> add code cell below)
                await page.keyboard.press("Control+m")
                await page.keyboard.press("b")

            await page.wait_for_timeout(1000)

            # The new cell should now be focused, we can just type the code.
            print("Typing code...", file=sys.stderr)
            # Find the active cell's Monaco editor text area
            active_editor = page.locator('.cell.selected focused-editor textarea')
            if await active_editor.count() == 0:
                # Just general fallback
                active_editor = page.locator('.cell.selected .view-lines')

            await page.keyboard.type(code)
            await page.wait_for_timeout(500)

            # Click the run button
            print("Executing code...", file=sys.stderr)
            # Ctrl+Enter runs the currently selected cell
            await page.keyboard.press("Control+Enter")

            # Wait for execution to finish
            # The play button shows a spinner while running, need to wait until it's back to normal
            run_button = page.locator('.cell.selected .cell-execution-container colab-run-button')
            
            # Wait for status to change to running
            await page.wait_for_timeout(1000)
            
            # Wait until there is no paper-spinner active
            print("Waiting for completion...", file=sys.stderr)
            
            # Wait until execution completes (simplistic check for Colab output node)
            # Normally we check for the output div inside the selected cell
            output_locator = page.locator('.cell.selected .output_subarea')
            
            # Since some commands output slowly, we wait up to 120s for an output container
            # or for the run button not to have the 'running' attribute (Colab uses custom DOM elements)
            
            # Example polling logic: wait for output to stabilize
            try:
                await page.wait_for_selector('.cell.selected .output-info-container', timeout=120000)
                await page.wait_for_timeout(1000) # Give it an extra second after it completes
            except Exception as e:
                print(f"Warning: Timeout waiting for explicit output indicator. {e}", file=sys.stderr)

            # Scrape output text
            if await output_locator.count() > 0:
                output_text = await output_locator.inner_text()
                print("--- Output ---", file=sys.stderr)
                print(output_text.strip())
            else:
                print("No output found or execution failed.", file=sys.stderr)
                print("")

        except Exception as e:
            print(f"Automation failed: {e}", file=sys.stderr)
            sys.exit(1)
        finally:
            await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Colab Headless Runner")
    parser.add_argument("--notebook", required=True, help="URL of the Google Colab Notebook")
    parser.add_argument("--code", required=True, help="Python code to execute")
    args = parser.parse_args()

    asyncio.run(run_in_colab(args.notebook, args.code))
