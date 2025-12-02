"""
OpenRouter Uptime Stats Extractor
Extract recent uptime statistics from OpenRouter for each provider.
This script can be run hourly via GitHub Actions.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from playwright.async_api import async_playwright


class OpenRouterStatsExtractor:
    """Extract provider uptime statistics from OpenRouter."""

    def __init__(self, model_slug: str = "arcee-ai/trinity-mini"):
        """Initialize the extractor."""
        self.model_slug = model_slug
        self.base_url = "https://openrouter.ai"
        self.url = f"{self.base_url}/{model_slug}"

    async def extract(self) -> dict:
        """Extract provider statistics from the OpenRouter page."""
        try:
            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch()
                page = await browser.new_page()

                # Navigate to the page
                print(f"Loading {self.url}...")
                await page.goto(self.url, wait_until="domcontentloaded", timeout=30000)

                # Wait for content to load
                await page.wait_for_timeout(3000)

                # Click "Show more" buttons to reveal all providers
                for attempt in range(10):  # Try up to 10 times
                    try:
                        # Find all buttons and click the one that contains "Show"
                        buttons = await page.query_selector_all("button")
                        found = False
                        for button in buttons:
                            text = await button.text_content()
                            if text and "Show" in text and "more" in text:
                                await button.click()
                                await page.wait_for_timeout(500)
                                found = True
                                break

                        if not found:
                            break
                    except Exception:
                        break

                # Extract provider data using JavaScript
                provider_data = await page.evaluate(self._get_extraction_script())
                await browser.close()

                return provider_data

        except Exception as e:
            print(f"Error during extraction: {e}")
            raise

    @staticmethod
    def _get_extraction_script() -> str:
        """Get the JavaScript extraction script - only extracts Clarifai provider."""
        return """
        () => {
            const providers = [];
            
            // Get full page text
            const text = document.body.innerText;
            const lines = text.split('\\n').map(l => l.trim()).filter(l => l);
            
            // Only look for Clarifai
            const targetProvider = 'Clarifai';
            
            // Extract Clarifai section
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                
                if (line.includes(targetProvider) && !line.toLowerCase().includes('more')) {
                    // This line likely starts the Clarifai section
                    const section = lines.slice(i, Math.min(i + 20, lines.length)).join(' ');
                    
                    // Extract metrics from this section
                    const uptimeMatch = section.match(/(\\d+\\.?\\d*)\\s*(?:percent|%)/);
                    const latencyMatch = section.match(/Latency\\s+([\\d.]+)s/);
                    const throughputMatch = section.match(/Throughput\\s+([\\d.]+)tps/);
                    
                    // Extract timeline SVG as an image/HTML element
                    const svg = document.querySelector('svg[aria-label*="timeline" i], svg[aria-label*="Uptime" i]');
                    let timelineHtml = null;
                    let timelineInfo = null;
                    
                    if (svg) {
                        // Get the SVG as a string (HTML) with explicit dimensions
                        let svgHtml = svg.outerHTML;
                        
                        // Replace width="100%" with absolute width if present
                        svgHtml = svgHtml.replace(/width="100%"/g, 'width="800"');
                        // Ensure height is set
                        if (!svgHtml.includes('height=')) {
                            svgHtml = svgHtml.replace('<svg', '<svg height="32"');
                        }
                        
                        timelineHtml = svgHtml;
                        
                        const rects = svg.querySelectorAll('rect');
                        timelineInfo = {
                            total_periods: rects.length,
                            degraded_count: 0,
                            perfect_count: 0,
                            no_data_count: 0,
                            degraded_periods: []
                        };
                        
                        const now = new Date();
                        rects.forEach((rect, index) => {
                            const fill = rect.getAttribute('fill');
                            if (fill === '#30A46C') {
                                timelineInfo.perfect_count++;
                            } else if (fill === '#FFBB28' || fill === '#FFA500') {
                                timelineInfo.degraded_count++;
                                // Calculate the actual time this hour occurred
                                const hoursAgo = 72 - index;
                                const degradedTime = new Date(now.getTime() - hoursAgo * 60 * 60 * 1000);
                                // Format as HH:MM AM/PM
                                const hours = degradedTime.getUTCHours();
                                const ampm = hours >= 12 ? 'PM' : 'AM';
                                const displayHours = hours % 12 || 12;
                                const timeStr = `${displayHours}${ampm} UTC`;
                                timelineInfo.degraded_periods.push(timeStr);
                            } else {
                                timelineInfo.no_data_count++;
                            }
                        });
                        
                        // Calculate rolling average from timeline pattern
                        const periodsWithData = timelineInfo.perfect_count + timelineInfo.degraded_count;
                        if (periodsWithData > 0) {
                            timelineInfo.uptime_percent_from_timeline = ((timelineInfo.perfect_count + timelineInfo.degraded_count * 0.5) / periodsWithData * 100).toFixed(1);
                        } else {
                            timelineInfo.uptime_percent_from_timeline = 'N/A';
                        }
                    }
                    
                    const timeline = timelineInfo ? {
                        ...timelineInfo,
                        svg_html: timelineHtml
                    } : null;
                    
                    const providerObj = {
                        name: targetProvider,
                        uptime_percent: uptimeMatch ? parseFloat(uptimeMatch[1]) : null,
                        timeline: timeline
                    };
                    
                    if (latencyMatch) providerObj.latency_s = parseFloat(latencyMatch[1]);
                    if (throughputMatch) providerObj.throughput_tps = parseFloat(throughputMatch[1]);
                    
                    providers.push(providerObj);
                    break;
                }
            }
            
            return providers;
        }
        """

    def generate_report(self, data: list) -> str:
        """Generate a formatted report."""
        report = []
        report.append("=" * 70)
        report.append("OPENROUTER UPTIME STATS REPORT")
        report.append("=" * 70)
        report.append(f"Model: {self.model_slug}")
        report.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        report.append("")
        report.append(
            f"{'Provider':<20} {'Uptime':<12} {'Latency':<12} {'Throughput':<12}"
        )
        report.append("-" * 70)

        for provider in data:
            name = provider["name"]
            uptime = (
                f"{provider.get('uptime_percent', 'N/A')}%"
                if provider.get("uptime_percent")
                else "N/A"
            )
            latency = (
                f"{provider.get('latency_s', 'N/A')}s"
                if provider.get("latency_s")
                else "N/A"
            )
            throughput = (
                f"{provider.get('throughput_tps', 'N/A')} tps"
                if provider.get("throughput_tps")
                else "N/A"
            )
            report.append(f"{name:<20} {uptime:<12} {latency:<12} {throughput:<12}")

        report.append("-" * 70)
        report.append(f"Total providers: {len(data)}")
        report.append("=" * 70)

        return "\n".join(report)


async def main():
    """Main entry point."""
    # Get model slug from command line or use default
    model_slug = sys.argv[1] if len(sys.argv) > 1 else "arcee-ai/trinity-mini"
    quiet = "--quiet" in sys.argv or "--json" in sys.argv

    try:
        if not quiet:
            print("Starting OpenRouter Uptime Stats Extraction...\n")

        # Create extractor
        extractor = OpenRouterStatsExtractor(model_slug)

        # Extract data
        providers = await extractor.extract()

        # Build report dictionary
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model": model_slug,
            "url": extractor.url,
            "providers": providers,
        }

        if quiet:
            # Just output JSON for piping
            print(json.dumps(report))
        else:
            # Print formatted report
            print(extractor.generate_report(providers))
            print()
            print("JSON Output:")
            print(json.dumps(report, indent=2))

        return report

    except Exception as e:
        if not quiet:
            print(f"\n[ERROR] Error: {e}")
            import traceback

            traceback.print_exc()
        else:
            print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
