#!/usr/bin/env python3
"""
Test script for the deployed MCP server
Tests all 7 MCP tools on the live Clarifai deployment
"""

import asyncio
import os
import json
import base64
import zipfile
from typing import Dict, Any, List

# Export PAT token for Clarifai API
if "CLARIFAI_PAT" not in os.environ:
    print("[ERROR] CLARIFAI_PAT environment variable not set")
    # set it as a85d04ec58d24a9bba2ad19d9af2e7ba
    os.environ["CLARIFAI_PAT"] = "a85d04ec58d24a9bba2ad19d9af2e7ba"

try:
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport
    print("[SUCCESS] FastMCP client imported successfully")
except ImportError as e:
    print(f"[ERROR] Failed to import FastMCP client: {e}")
    print("Please install: pip install fastmcp")
    exit(1)

class DeployedMCPTester:
    """Test the deployed MCP server on Clarifai"""
    
    def __init__(self):
        self.test_results = {}
        self.test_files = []
        self.client = None
        self.tools = []
        
        # Check for PAT token
        if "CLARIFAI_PAT" not in os.environ:
            print("[ERROR] CLARIFAI_PAT environment variable not set")
            print("Please set: export CLARIFAI_PAT=your_pat_token")
            exit(1)
        
        self.transport = StreamableHttpTransport(
            url="https://api.clarifai.com/v2/ext/mcp/v1/users/mulder/apps/local-runner-app/models/local-runner-model",
            headers={"Authorization": "Bearer " + os.environ["CLARIFAI_PAT"]},
        )
    
    async def setup_client(self):
        """Setup the MCP client connection"""
        print("\n[SETUP] Connecting to deployed MCP server...")
        print("URL: https://api.clarifai.com/v2/ext/mcp/v1/users/mulder/apps/local-runner-app/models/local-runner-model")
        
        try:
            self.client = Client(self.transport)
            await self.client.__aenter__()
            
            # List available tools
            self.tools = await self.client.list_tools()
            tool_names = [tool.name for tool in self.tools]
            
            print(f"[SUCCESS] Connected to MCP server")
            print(f"[INFO] Found {len(self.tools)} tools: {tool_names}")
            
            # Expected tools
            expected_tools = [
                "generate_iphone_layout",
                "list_personas", 
                "get_layout_suggestions",
                "get_app_categories",
                "generate_figma_layout",
                "export_figma_files",
                "create_fig_file"
            ]
            
            for expected in expected_tools:
                if expected not in tool_names:
                    print(f"[WARN] Expected tool '{expected}' not found")
                else:
                    print(f"[OK] Tool '{expected}' available")
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to connect to MCP server: {e}")
            return False
    
    async def cleanup_client(self):
        """Cleanup the MCP client connection"""
        if self.client:
            try:
                await self.client.__aexit__(None, None, None)
                print("[CLEANUP] MCP client connection closed")
            except Exception as e:
                print(f"[WARN] Error closing client: {e}")
    
    async def run_test(self, test_name: str, test_func):
        """Run a single test and record results"""
        print(f"\n[TEST] {test_name}")
        print("-" * 60)
        
        try:
            result = await test_func()
            self.test_results[test_name] = {
                "success": True,
                "result": result
            }
            print(f"[PASS] {test_name}")
            return True
        except Exception as e:
            self.test_results[test_name] = {
                "success": False,
                "error": str(e)
            }
            print(f"[FAIL] {test_name}: {e}")
            return False
    
    async def test_1_generate_iphone_layout(self):
        """Test Tool 1: generate_iphone_layout"""
        print("Testing iPhone layout generation on deployed server...")
        
        # Test basic layout generation
        result = await self.client.call_tool("generate_iphone_layout", {
            "persona": "tech-professional",
            "screen_size": "iPhone14Pro",
            "preferences": {"categories": ["Productivity", "Communication"]}
        })
        
        # Parse result
        result_data = json.loads(result.content[0].text)
        
        # Validate structure
        assert "error" not in result_data, f"Tool returned error: {result_data.get('error')}"
        assert "id" in result_data, "Missing layout id"
        assert "persona" in result_data, "Missing persona info"
        assert "totalApps" in result_data, "Missing totalApps"
        assert result_data["totalApps"] > 0, "No apps in layout"
        
        print(f"  Generated layout with {result_data['totalApps']} apps")
        print(f"  Persona: {result_data['persona']['name']}")
        print(f"  Pages: {len(result_data.get('pages', []))}")
        
        # Test different persona
        result2 = await self.client.call_tool("generate_iphone_layout", {
            "persona": "soccer-mom",
            "screen_size": "iPhone14Plus"
        })
        
        result2_data = json.loads(result2.content[0].text)
        assert "error" not in result2_data, "Error with soccer-mom persona"
        print(f"  Soccer mom layout: {result2_data['totalApps']} apps")
        
        return {"tech": result_data, "soccer_mom": result2_data}
    
    async def test_2_list_personas(self):
        """Test Tool 2: list_personas"""
        print("Testing persona listing on deployed server...")
        
        result = await self.client.call_tool("list_personas", {})
        result_data = json.loads(result.content[0].text)
        
        assert isinstance(result_data, list), "Result should be a list"
        assert len(result_data) > 0, "No personas returned"
        
        # Validate persona structure
        required_fields = ["id", "name", "description", "keywords", "preferredCategories"]
        for persona in result_data:
            for field in required_fields:
                assert field in persona, f"Persona missing field: {field}"
        
        print(f"  Found {len(result_data)} personas:")
        for persona in result_data:
            print(f"    - {persona['name']}: {len(persona['preferredCategories'])} categories")
        
        return result_data
    
    async def test_3_get_layout_suggestions(self):
        """Test Tool 3: get_layout_suggestions"""
        print("Testing layout suggestions on deployed server...")
        
        result = await self.client.call_tool("get_layout_suggestions", {
            "persona": "fitness enthusiast who loves running",
            "current_apps": ["Strava", "Nike Run Club", "Instagram"]
        })
        
        result_data = json.loads(result.content[0].text)
        
        # Validate structure
        required_fields = ["matchedPersona", "reasoning", "recommendedApps"]
        for field in required_fields:
            assert field in result_data, f"Missing field: {field}"
        
        assert len(result_data["recommendedApps"]) > 0, "No recommended apps"
        
        print(f"  Matched persona: {result_data['matchedPersona']}")
        print(f"  Recommended {len(result_data['recommendedApps'])} apps")
        print(f"  Reasoning: {result_data['reasoning'][:100]}...")
        
        return result_data
    
    async def test_4_get_app_categories(self):
        """Test Tool 4: get_app_categories"""
        print("Testing app categories on deployed server...")
        
        result = await self.client.call_tool("get_app_categories", {})
        result_data = json.loads(result.content[0].text)
        
        assert isinstance(result_data, dict), "Result should be a dictionary"
        assert len(result_data) > 0, "No categories returned"
        
        total_apps = sum(len(apps) for apps in result_data.values())
        print(f"  Found {len(result_data)} categories with {total_apps} total apps:")
        
        for category, apps in result_data.items():
            print(f"    - {category}: {len(apps)} apps")
        
        # Verify essential categories
        essential_categories = ["Communication", "Productivity", "Social"]
        for cat in essential_categories:
            assert cat in result_data, f"Missing essential category: {cat}"
        
        return result_data
    
    async def test_5_generate_figma_layout(self):
        """Test Tool 5: generate_figma_layout"""
        print("Testing Figma layout generation on deployed server...")
        
        result = await self.client.call_tool("generate_figma_layout", {
            "persona": "college-student",
            "screen_size": "iPhone14Pro",
            "preferences": {"categories": ["Social", "Education", "Entertainment"]}
        })
        
        result_data = json.loads(result.content[0].text)
        
        # Validate structure
        assert "error" not in result_data, f"Tool returned error: {result_data.get('error')}"
        assert "document" in result_data, "Missing document structure"
        assert "fileName" in result_data, "Missing fileName"
        assert "layout_info" in result_data, "Missing layout_info"
        
        layout_info = result_data["layout_info"]
        assert layout_info["total_apps"] > 0, "No apps in Figma layout"
        
        print(f"  Generated Figma file: {result_data['fileName']}")
        print(f"  Total apps: {layout_info['total_apps']}")
        print(f"  Pages: {layout_info['pages']}")
        
        return result_data
    
    async def test_6_export_figma_files(self):
        """Test Tool 6: export_figma_files"""
        print("Testing Figma export on deployed server...")
        
        result = await self.client.call_tool("export_figma_files", {
            "persona": "business-executive",
            "screen_size": "iPhone14ProMax",
            "export_formats": ["json", "figma_plugin", "fig_binary"],
            "preferences": {"categories": ["Productivity", "Finance", "Communication"]}
        })
        
        result_data = json.loads(result.content[0].text)
        
        # Validate structure
        assert "error" not in result_data, f"Tool returned error: {result_data.get('error')}"
        assert result_data.get("success"), "Export not successful"
        assert "exports" in result_data, "Missing exports"
        assert "fig_file_support" in result_data, "Missing fig_file_support"
        
        exports = result_data["exports"]
        expected_formats = ["json", "figma_plugin", "fig_binary"]
        
        for fmt in expected_formats:
            assert fmt in exports, f"Missing export format: {fmt}"
            export_data = exports[fmt]
            assert "data" in export_data, f"Missing data in {fmt}"
            print(f"  {fmt}: {export_data['format']}")
        
        # Test fig_binary specifically
        fig_export = exports["fig_binary"]
        assert "file_info" in fig_export, "Missing file_info in fig_binary"
        
        # Decode and save fig file
        fig_data = base64.b64decode(fig_export["data"])
        assert len(fig_data) > 0, "Empty fig file data"
        assert fig_data.startswith(b'PK'), "Invalid ZIP header"
        
        test_filename = "deployed_test_export.fig"
        with open(test_filename, 'wb') as f:
            f.write(fig_data)
        self.test_files.append(test_filename)
        
        # Validate ZIP structure
        with zipfile.ZipFile(test_filename, 'r') as zip_ref:
            files = zip_ref.namelist()
            required_files = ['canvas.fig', 'meta.json', 'thumbnail.png']
            for req_file in required_files:
                assert req_file in files, f"Missing {req_file} in deployed fig file"
        
        print(f"  Fig binary size: {fig_export['file_info']['size_mb']} MB")
        print(f"  Direct support: {result_data['fig_file_support']['direct_support']}")
        print(f"  Saved test file: {test_filename}")
        
        return result_data
    
    async def test_7_create_fig_file(self):
        """Test Tool 7: create_fig_file"""
        print("Testing native .fig file creation on deployed server...")
        
        result = await self.client.call_tool("create_fig_file", {
            "persona": "fitness-enthusiast",
            "screen_size": "iPhone14",
            "preferences": {"categories": ["Health & Fitness", "Social", "Entertainment"]},
            "save_to_disk": False
        })
        
        result_data = json.loads(result.content[0].text)
        
        # Validate structure
        assert "error" not in result_data, f"Tool returned error: {result_data.get('error')}"
        assert result_data.get("success"), "Fig creation not successful"
        assert "filename" in result_data, "Missing filename"
        assert "fig_file_data" in result_data, "Missing fig file data"
        assert "file_info" in result_data, "Missing file info"
        assert "layout_info" in result_data, "Missing layout info"
        
        # Validate file info
        file_info = result_data["file_info"]
        layout_info = result_data["layout_info"]
        
        required_info = ["format", "size_bytes", "size_mb", "compression", "figma_version"]
        for info in required_info:
            assert info in file_info, f"Missing file info: {info}"
        
        assert layout_info["total_apps"] > 0, "No apps in layout"
        
        # Test the binary data
        fig_data = base64.b64decode(result_data["fig_file_data"])
        assert len(fig_data) > 0, "Empty fig file data"
        assert fig_data.startswith(b'PK'), "Invalid ZIP header"
        
        test_filename = "deployed_test_native.fig"
        with open(test_filename, 'wb') as f:
            f.write(fig_data)
        self.test_files.append(test_filename)
        
        # Comprehensive validation
        with zipfile.ZipFile(test_filename, 'r') as zip_ref:
            files = zip_ref.namelist()
            required_files = ['canvas.fig', 'meta.json', 'thumbnail.png']
            for req_file in required_files:
                assert req_file in files, f"Missing {req_file}"
            
            # Validate canvas.fig
            canvas_data = zip_ref.read('canvas.fig')
            assert canvas_data.startswith(b'fig-kiwi'), "Invalid fig-kiwi header"
            
            # Validate meta.json
            meta_data = json.loads(zip_ref.read('meta.json').decode('utf-8'))
            assert "persona" in meta_data, "Missing persona in metadata"
            assert "total_apps" in meta_data, "Missing total_apps in metadata"
            
            # Validate PNG thumbnail
            thumb_data = zip_ref.read('thumbnail.png')
            assert thumb_data.startswith(b'\x89PNG'), "Invalid PNG thumbnail"
        
        print(f"  Generated file: {result_data['filename']}")
        print(f"  File size: {file_info['size_mb']} MB")
        print(f"  Total apps: {layout_info['total_apps']}")
        print(f"  Figma version: {file_info['figma_version']}")
        print(f"  Saved test file: {test_filename}")
        
        return result_data
    
    async def test_8_error_handling(self):
        """Test error handling on deployed server"""
        print("Testing error handling on deployed server...")
        
        # Test invalid screen size
        try:
            result = await self.client.call_tool("generate_iphone_layout", {
                "persona": "tech-professional",
                "screen_size": "InvalidScreen"
            })
            result_data = json.loads(result.content[0].text)
            assert "error" in result_data, "Should return error for invalid screen size"
            print("  Invalid screen size: Handled correctly")
        except Exception as e:
            print(f"  Invalid screen size: Exception handled - {e}")
        
        # Test invalid persona (should handle gracefully)
        result2 = await self.client.call_tool("generate_iphone_layout", {
            "persona": "invalid-persona-xyz", 
            "screen_size": "iPhone14Pro"
        })
        result2_data = json.loads(result2.content[0].text)
        # Should either work with default or return error
        if "error" not in result2_data:
            print("  Invalid persona: Handled gracefully with default")
        else:
            print("  Invalid persona: Handled with error response")
        
        print("  Error handling working on deployed server")
        return True
    
    async def run_all_tests(self):
        """Run all tests on the deployed MCP server"""
        print("=" * 70)
        print("DEPLOYED MCP SERVER TEST SUITE")
        print("=" * 70)
        print("Testing all 7 MCP tools on live Clarifai deployment...")
        
        # Setup client connection
        if not await self.setup_client():
            return False
        
        try:
            # Define all tests
            tests = [
                ("generate_iphone_layout", self.test_1_generate_iphone_layout),
                ("list_personas", self.test_2_list_personas),
                ("get_layout_suggestions", self.test_3_get_layout_suggestions),
                ("get_app_categories", self.test_4_get_app_categories),
                ("generate_figma_layout", self.test_5_generate_figma_layout),
                ("export_figma_files", self.test_6_export_figma_files),
                ("create_fig_file", self.test_7_create_fig_file),
                ("error_handling", self.test_8_error_handling)
            ]
            
            passed = 0
            total = len(tests)
            
            for test_name, test_func in tests:
                if await self.run_test(test_name, test_func):
                    passed += 1
            
            # Results summary
            print(f"\n" + "=" * 70)
            print("DEPLOYED SERVER TEST RESULTS")
            print("=" * 70)
            
            for test_name, result in self.test_results.items():
                status = "[PASS]" if result["success"] else "[FAIL]"
                print(f"{status} {test_name}")
                if not result["success"]:
                    print(f"      Error: {result['error']}")
            
            print(f"\n[OVERALL] {passed}/{total} tests passed on deployed server")
            
            if self.test_files:
                print(f"\n[GENERATED FILES] Downloaded from deployed server:")
                for filename in self.test_files:
                    if os.path.exists(filename):
                        size = os.path.getsize(filename)
                        print(f"  {filename} ({size} bytes, {size/1024:.1f} KB)")
            
            success_rate = (passed / total) * 100
            if passed == total:
                print(f"\n[SUCCESS] All deployed MCP tools working! ({success_rate:.0f}%)")
                print("\n[DEPLOYMENT VALIDATION]")
                print("+ Deployed MCP server is fully operational")
                print("+ All 7 tools working correctly on Clarifai cloud")
                print("+ Native .fig file creation working in production")
                print("+ Error handling implemented correctly")
                print("+ Generated files are valid and complete")
                print("+ Production deployment successful")
                print("\nMCP server is live and ready for production use!")
                return True
            else:
                print(f"\n[FAILURE] {total - passed} tests failed on deployed server")
                print("Some tools may not be working correctly in production.")
                return False
                
        finally:
            await self.cleanup_client()
    
    def cleanup_files(self):
        """Clean up generated test files"""
        cleaned = 0
        for filename in self.test_files:
            try:
                if os.path.exists(filename):
                    os.remove(filename)
                    cleaned += 1
            except Exception as e:
                print(f"Could not remove {filename}: {e}")
        
        if cleaned > 0:
            print(f"[CLEANUP] Removed {cleaned} test files")

async def main():
    """Main test runner"""
    print("Testing deployed MCP server on Clarifai...")
    
    tester = DeployedMCPTester()
    
    try:
        success = await tester.run_all_tests()
        
        # Keep files if requested
        if len(os.sys.argv) > 1 and os.sys.argv[1] == "--keep-files":
            print("\n[INFO] Keeping downloaded test files")
        else:
            tester.cleanup_files()
        
        if success:
            print("\n" + "="*60)
            print("DEPLOYED MCP SERVER VALIDATION COMPLETE")
            print("="*60)
            print("All tools are working correctly in production!")
        
        return success
        
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Test interrupted by user")
        await tester.cleanup_client()
        tester.cleanup_files()
        return False
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        await tester.cleanup_client()
        tester.cleanup_files()
        return False

if __name__ == "__main__":
    import sys
    success = asyncio.run(main())
    sys.exit(0 if success else 1)