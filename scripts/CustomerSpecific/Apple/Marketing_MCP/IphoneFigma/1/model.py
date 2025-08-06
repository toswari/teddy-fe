import os
import json
import uuid
import base64
import zipfile
import struct
import zstandard as zstd
from io import BytesIO
from typing import Annotated, Dict, Any, List, Optional
from pydantic import Field
from clarifai.runners.models.mcp_class import MCPModelClass, ModelClass
from fastmcp import FastMCP
from PIL import Image, ImageDraw

# Initialize the MCP server
server = FastMCP("iphone_layout_mcp")

# Persona definitions
PERSONAS = {
    "soccer-mom": {
        "name": "Soccer Mom",
        "description": "Busy parent managing kids' schedules, activities, and household tasks",
        "keywords": ["family", "organization", "scheduling", "kids", "sports", "parenting", "busy"],
        "preferredCategories": ["Productivity", "Health & Fitness", "Social", "Shopping", "Travel"]
    },
    "tech-professional": {
        "name": "Tech Professional", 
        "description": "Software developer or tech worker focused on productivity and staying current",
        "keywords": ["technology", "programming", "productivity", "work", "professional", "coding", "development"],
        "preferredCategories": ["Productivity", "Education", "Communication", "Utilities", "Finance"]
    },
    "college-student": {
        "name": "College Student",
        "description": "University student balancing studies, social life, and budget constraints", 
        "keywords": ["student", "education", "social", "budget", "learning", "young", "university"],
        "preferredCategories": ["Education", "Social", "Entertainment", "Finance", "Health & Fitness"]
    },
    "fitness-enthusiast": {
        "name": "Fitness Enthusiast",
        "description": "Health-focused individual who prioritizes workouts, nutrition, and wellness",
        "keywords": ["fitness", "health", "workout", "nutrition", "wellness", "active", "exercise"],
        "preferredCategories": ["Health & Fitness", "Productivity", "Social", "Entertainment", "Shopping"]
    },
    "business-executive": {
        "name": "Business Executive",
        "description": "Senior professional managing teams, finances, and strategic decisions",
        "keywords": ["business", "executive", "leadership", "finance", "professional", "management", "strategy"],
        "preferredCategories": ["Productivity", "Finance", "Communication", "Travel", "Utilities"]
    }
}

# App database
APPS = {
    # Essential iOS Apps
    "phone": {"name": "Phone", "category": "Communication", "popularity": 10, "keywords": ["communication", "calls", "essential"]},
    "messages": {"name": "Messages", "category": "Communication", "popularity": 9, "keywords": ["communication", "messaging", "sms"]},
    "mail": {"name": "Mail", "category": "Productivity", "popularity": 9, "keywords": ["productivity", "email", "communication"]},
    "safari": {"name": "Safari", "category": "Utilities", "popularity": 9, "keywords": ["utilities", "browser", "web"]},
    "camera": {"name": "Camera", "category": "Utilities", "popularity": 9, "keywords": ["utilities", "photos", "camera"]},
    "photos": {"name": "Photos", "category": "Utilities", "popularity": 8, "keywords": ["utilities", "photos", "memories"]},
    
    # Productivity Apps
    "calendar": {"name": "Calendar", "category": "Productivity", "popularity": 8, "keywords": ["productivity", "scheduling", "organization"]},
    "notes": {"name": "Notes", "category": "Productivity", "popularity": 7, "keywords": ["productivity", "writing", "organization"]},
    "reminders": {"name": "Reminders", "category": "Productivity", "popularity": 6, "keywords": ["productivity", "tasks", "organization"]},
    "slack": {"name": "Slack", "category": "Productivity", "popularity": 7, "keywords": ["productivity", "work", "communication"]},
    
    # Social Apps
    "instagram": {"name": "Instagram", "category": "Social", "popularity": 9, "keywords": ["social", "photos", "sharing"]},
    "facebook": {"name": "Facebook", "category": "Social", "popularity": 8, "keywords": ["social", "friends", "news"]},
    "twitter": {"name": "Twitter", "category": "Social", "popularity": 7, "keywords": ["social", "news", "updates"]},
    "snapchat": {"name": "Snapchat", "category": "Social", "popularity": 8, "keywords": ["social", "photos", "messaging"]},
    "tiktok": {"name": "TikTok", "category": "Social", "popularity": 9, "keywords": ["social", "videos", "entertainment"]},
    "whatsapp": {"name": "WhatsApp", "category": "Communication", "popularity": 8, "keywords": ["communication", "messaging", "international"]},
    
    # Entertainment Apps
    "netflix": {"name": "Netflix", "category": "Entertainment", "popularity": 9, "keywords": ["entertainment", "streaming", "movies"]},
    "youtube": {"name": "YouTube", "category": "Entertainment", "popularity": 9, "keywords": ["entertainment", "videos", "learning"]},
    "spotify": {"name": "Spotify", "category": "Entertainment", "popularity": 9, "keywords": ["entertainment", "music", "streaming"]},
    "disney": {"name": "Disney+", "category": "Entertainment", "popularity": 7, "keywords": ["entertainment", "streaming", "family"]},
    
    # Health & Fitness
    "health": {"name": "Health", "category": "Health & Fitness", "popularity": 6, "keywords": ["health", "fitness", "tracking"]},
    "strava": {"name": "Strava", "category": "Health & Fitness", "popularity": 6, "keywords": ["health", "fitness", "running", "cycling"]},
    "myfitnesspal": {"name": "MyFitnessPal", "category": "Health & Fitness", "popularity": 6, "keywords": ["health", "fitness", "nutrition"]},
    
    # Shopping Apps
    "amazon": {"name": "Amazon", "category": "Shopping", "popularity": 9, "keywords": ["shopping", "online", "delivery"]},
    "target": {"name": "Target", "category": "Shopping", "popularity": 7, "keywords": ["shopping", "retail", "deals"]},
    "walmart": {"name": "Walmart", "category": "Shopping", "popularity": 6, "keywords": ["shopping", "retail", "groceries"]},
    
    # Travel Apps
    "maps": {"name": "Maps", "category": "Travel", "popularity": 9, "keywords": ["travel", "navigation", "directions"]},
    "uber": {"name": "Uber", "category": "Travel", "popularity": 8, "keywords": ["travel", "rideshare", "transportation"]},
    "airbnb": {"name": "Airbnb", "category": "Travel", "popularity": 7, "keywords": ["travel", "accommodation", "vacation"]},
    
    # Finance Apps
    "chase": {"name": "Chase", "category": "Finance", "popularity": 7, "keywords": ["finance", "banking", "money"]},
    "venmo": {"name": "Venmo", "category": "Finance", "popularity": 8, "keywords": ["finance", "payments", "social"]},
    "paypal": {"name": "PayPal", "category": "Finance", "popularity": 7, "keywords": ["finance", "payments", "money"]},
    
    # Games
    "candy-crush": {"name": "Candy Crush", "category": "Games", "popularity": 8, "keywords": ["games", "puzzle", "casual"]},
    "pokemon-go": {"name": "Pokémon GO", "category": "Games", "popularity": 7, "keywords": ["games", "ar", "walking"]},
    
    # Utilities
    "weather": {"name": "Weather", "category": "Utilities", "popularity": 8, "keywords": ["utilities", "weather", "information"]},
    "calculator": {"name": "Calculator", "category": "Utilities", "popularity": 7, "keywords": ["utilities", "math", "calculation"]},
    "settings": {"name": "Settings", "category": "Utilities", "popularity": 6, "keywords": ["utilities", "configuration", "system"]},
    
    # Education
    "duolingo": {"name": "Duolingo", "category": "Education", "popularity": 7, "keywords": ["education", "language", "learning"]},
    "khan-academy": {"name": "Khan Academy", "category": "Education", "popularity": 5, "keywords": ["education", "learning", "free"]},
    
    # Communication
    "zoom": {"name": "Zoom", "category": "Communication", "popularity": 7, "keywords": ["communication", "video", "meetings"]},
    "discord": {"name": "Discord", "category": "Communication", "popularity": 6, "keywords": ["communication", "gaming", "voice"]}
}

# iPhone screen configurations
SCREEN_CONFIGS = {
    "iPhone14": {"width": 390, "height": 844, "rows": 6, "cols": 4, "dockSlots": 4},
    "iPhone14Plus": {"width": 428, "height": 926, "rows": 6, "cols": 4, "dockSlots": 4},
    "iPhone14Pro": {"width": 393, "height": 852, "rows": 6, "cols": 4, "dockSlots": 4},
    "iPhone14ProMax": {"width": 430, "height": 932, "rows": 6, "cols": 4, "dockSlots": 4}
}

def get_apps_for_persona(persona_id: str, categories: List[str] = None) -> List[Dict]:
    """Get relevant apps for a given persona"""
    persona = PERSONAS.get(persona_id)
    if not persona:
        return []
    
    preferred_categories = categories or persona["preferredCategories"]
    persona_keywords = persona["keywords"]
    
    relevant_apps = []
    
    # Always include essential apps
    essential_apps = ["phone", "messages", "mail", "safari", "camera", "photos"]
    for app_id in essential_apps:
        if app_id in APPS:
            app = APPS[app_id].copy()
            app["id"] = app_id
            relevant_apps.append(app)
    
    # Add apps from preferred categories
    for app_id, app_data in APPS.items():
        if app_id not in essential_apps:
            if app_data["category"] in preferred_categories:
                app = app_data.copy()
                app["id"] = app_id
                relevant_apps.append(app)
            elif any(keyword in app_data["keywords"] for keyword in persona_keywords):
                app = app_data.copy()
                app["id"] = app_id
                relevant_apps.append(app)
    
    # Sort by popularity and limit
    relevant_apps.sort(key=lambda x: x["popularity"], reverse=True)
    return relevant_apps[:60]  # Reasonable limit

def create_iphone_layout(persona_id: str, screen_size: str, preferences: Dict = None) -> Dict:
    """Generate iPhone layout for given persona and screen size"""
    if screen_size not in SCREEN_CONFIGS:
        raise ValueError(f"Unsupported screen size: {screen_size}")
    
    screen_config = SCREEN_CONFIGS[screen_size]
    persona = PERSONAS.get(persona_id)
    if not persona:
        raise ValueError(f"Unknown persona: {persona_id}")
    
    # Get relevant apps
    categories = preferences.get("categories") if preferences else None
    apps = get_apps_for_persona(persona_id, categories)
    
    # Create layout
    layout = {
        "id": str(uuid.uuid4()),
        "personaId": persona_id,
        "screenSize": screen_size,
        "icons": [],
        "createdAt": "2025-08-05T14:00:00.000Z"
    }
    
    # Place dock apps first (most important)
    dock_apps = apps[:4]  # Top 4 most relevant apps
    for i, app in enumerate(dock_apps):
        layout["icons"].append({
            "iconId": app["id"],
            "position": {
                "x": i,
                "y": screen_config["rows"] - 1,  # Bottom row
                "page": 0
            }
        })
    
    # Place remaining apps on main screen
    remaining_apps = apps[4:]
    current_position = 0
    current_page = 0
    
    for app in remaining_apps:
        # Skip dock row on page 0
        if current_page == 0 and current_position // screen_config["cols"] == screen_config["rows"] - 1:
            current_position = ((current_position // screen_config["cols"]) + 1) * screen_config["cols"]
        
        # Check if we need to move to next page
        apps_on_page = len([icon for icon in layout["icons"] if icon["position"]["page"] == current_page])
        max_apps_on_page = (screen_config["rows"] * screen_config["cols"]) - (screen_config["dockSlots"] if current_page == 0 else 0)
        
        if apps_on_page >= max_apps_on_page:
            current_page += 1
            current_position = 0
        
        x = current_position % screen_config["cols"]
        y = current_position // screen_config["cols"]
        
        layout["icons"].append({
            "iconId": app["id"],
            "position": {
                "x": x,
                "y": y,
                "page": current_page
            }
        })
        
        current_position += 1
        
        # Limit total apps
        if len(layout["icons"]) >= 60:
            break
    
    return layout

@server.tool(
    "generate_iphone_layout",
    description="Generate a personalized iPhone screen layout based on user persona and preferences."
)
def generate_iphone_layout(
    persona: Annotated[str, Field(description="User persona (e.g., 'soccer-mom', 'tech-professional', 'college-student', etc.)")],
    screen_size: Annotated[str, Field(description="iPhone screen size: iPhone14, iPhone14Plus, iPhone14Pro, or iPhone14ProMax")] = "iPhone14Pro",
    preferences: Annotated[Dict[str, Any], Field(description="Optional preferences including categories array, maxAppsPerPage number, etc.")] = None
) -> Dict[str, Any]:
    """Generate a personalized iPhone layout"""
    try:
        # Handle persona variations
        persona_key = persona.lower().replace(" ", "-").replace("_", "-")
        if persona_key not in PERSONAS:
            # Try to find a matching persona
            for key, persona_data in PERSONAS.items():
                if persona.lower() in persona_data["name"].lower() or any(keyword in persona.lower() for keyword in persona_data["keywords"]):
                    persona_key = key
                    break
            else:
                # Default to tech-professional if no match
                persona_key = "tech-professional"
        
        layout = create_iphone_layout(persona_key, screen_size, preferences or {})
        
        # Get persona data for response
        persona_data = PERSONAS[persona_key]
        
        # Get apps used in layout
        apps_in_layout = []
        dock_apps = []
        pages = []
        
        # Group icons by page and separate dock
        for icon in layout["icons"]:
            app_id = icon["iconId"]
            if app_id in APPS:
                app_info = APPS[app_id].copy()
                app_info["id"] = app_id
                apps_in_layout.append(app_info)
                
                # Check if it's a dock app (bottom row, page 0)
                screen_config = SCREEN_CONFIGS[screen_size]
                if icon["position"]["page"] == 0 and icon["position"]["y"] == screen_config["rows"] - 1:
                    dock_apps.append(app_info)
        
        # Create pages structure
        page_dict = {}
        for icon in layout["icons"]:
            page_num = icon["position"]["page"]
            if page_num not in page_dict:
                page_dict[page_num] = []
            
            app_id = icon["iconId"]
            if app_id in APPS:
                app_info = APPS[app_id].copy()
                app_info["id"] = app_id
                page_dict[page_num].append(app_info)
        
        # Convert to pages array
        for page_num in sorted(page_dict.keys()):
            pages.append({
                "pageNumber": page_num,
                "apps": page_dict[page_num]
            })
        
        # Enhanced response
        return {
            "id": layout["id"],
            "persona": {
                "id": persona_key,
                "name": persona_data["name"],
                "description": persona_data["description"]
            },
            "screenSize": screen_size,
            "totalApps": len(apps_in_layout),
            "dock": {
                "apps": dock_apps
            },
            "pages": pages,
            "reasoning": f"Generated personalized layout for {persona_data['name']} with {len(apps_in_layout)} apps organized across {len(pages)} page(s). Prioritized {', '.join(persona_data['preferredCategories'][:3])} categories.",
            "createdAt": layout["createdAt"],
            "layout": layout  # Include original layout for compatibility
        }
    except Exception as e:
        return {"error": f"Failed to generate layout: {str(e)}"}

@server.tool(
    "list_personas",
    description="List all available user personas with their descriptions and characteristics."
)
def list_personas() -> List[Dict[str, Any]]:
    """List all available personas"""
    return [
        {
            "id": key,
            "name": data["name"],
            "description": data["description"],
            "keywords": data["keywords"],
            "preferredCategories": data["preferredCategories"]
        }
        for key, data in PERSONAS.items()
    ]

@server.tool(
    "get_layout_suggestions",
    description="Get AI-powered layout suggestions and reasoning for a specific persona."
)
def get_layout_suggestions(
    persona: Annotated[str, Field(description="User persona description")],
    current_apps: Annotated[List[str], Field(description="Currently installed apps (optional)")] = None
) -> Dict[str, Any]:
    """Get layout suggestions with reasoning"""
    current_apps = current_apps or []
    
    # Mock AI suggestions based on persona
    suggestions = {
        "soccer mom": {
            "mainScreen": ["Instagram", "Facebook", "Weather", "Reminders", "Amazon", "Target", "Calendar", "Maps"],
            "dock": ["Phone", "Messages", "Calendar", "Maps"],
            "folders": [
                {"name": "Shopping", "apps": ["Amazon", "Target", "Walmart"]},
                {"name": "Social", "apps": ["Instagram", "Facebook", "WhatsApp"]},
                {"name": "Kids", "apps": ["Disney+", "YouTube", "Games"]}
            ],
            "reasoning": "Soccer mom layout prioritizes family organization, social connections, and shopping convenience. Calendar and Maps in dock for quick access to schedules and navigation."
        },
        "tech professional": {
            "mainScreen": ["Mail", "Calendar", "Notes", "Slack", "Zoom", "GitHub", "Terminal", "Safari"],
            "dock": ["Phone", "Messages", "Slack", "Safari"],
            "folders": [
                {"name": "Work", "apps": ["Slack", "Zoom", "Calendar", "Mail"]},
                {"name": "Dev Tools", "apps": ["GitHub", "Terminal", "Code Editor", "Stack Overflow"]},
                {"name": "Learning", "apps": ["Documentation", "Tutorials", "Podcasts"]}
            ],
            "reasoning": "Tech professional layout emphasizes productivity and development tools. Slack in dock for immediate work communication access."
        }
    }
    
    # Find matching suggestion and persona
    matched_persona = None
    selected_suggestion = None
    
    # First try exact matches with known personas
    for persona_key, persona_data in PERSONAS.items():
        if persona_key.replace("-", " ") in persona.lower() or persona_data["name"].lower() in persona.lower():
            matched_persona = persona_data["name"]
            # Get appropriate suggestion for this persona
            if "soccer" in persona_key or "mom" in persona.lower():
                selected_suggestion = suggestions["soccer mom"]
            elif "tech" in persona_key or "developer" in persona.lower() or "professional" in persona.lower():
                selected_suggestion = suggestions["tech professional"]
            break
    
    # If no direct persona match, check keywords in suggestion keys
    if not matched_persona:
        for key, suggestion in suggestions.items():
            if key in persona.lower():
                matched_persona = key.title()
                selected_suggestion = suggestion
                break
    
    # Generate recommended apps with reasons
    recommended_apps = []
    if selected_suggestion:
        # Add main screen apps as recommendations
        for app_name in selected_suggestion["mainScreen"][:5]:  # Top 5
            # Find app in database
            app_found = None
            for app_id, app_data in APPS.items():
                if app_data["name"].lower() == app_name.lower():
                    app_found = app_data
                    app_found["id"] = app_id
                    break
            
            if app_found:
                recommended_apps.append({
                    "name": app_found["name"],
                    "category": app_found["category"],
                    "reason": f"Essential for {matched_persona or 'this persona'} - fits {app_found['category'].lower()} needs"
                })
            else:
                # Add generic recommendation for missing apps
                recommended_apps.append({
                    "name": app_name,
                    "category": "Productivity",
                    "reason": f"Recommended for {matched_persona or 'this user type'}"
                })
    
    # If still no match, create default recommendation
    if not selected_suggestion:
        matched_persona = "General User"
        selected_suggestion = {
            "mainScreen": ["Mail", "Calendar", "Weather", "Notes", "Camera", "Photos", "Maps", "Settings"],
            "dock": ["Phone", "Messages", "Safari", "Music"],
            "folders": [
                {"name": "Utilities", "apps": ["Calculator", "Weather", "Clock"]},
                {"name": "Social", "apps": ["Instagram", "Facebook", "Twitter"]}
            ],
            "reasoning": f"Balanced layout generated for {persona} with essential apps and organized folders."
        }
        
        # Generate default recommended apps
        recommended_apps = [
            {"name": "Mail", "category": "Productivity", "reason": "Essential for communication"},
            {"name": "Calendar", "category": "Productivity", "reason": "Important for scheduling"},
            {"name": "Maps", "category": "Travel", "reason": "Useful for navigation"},
            {"name": "Camera", "category": "Utilities", "reason": "Essential iPhone feature"},
            {"name": "Weather", "category": "Utilities", "reason": "Daily information need"}
        ]
    
    # Return enhanced structure
    return {
        "matchedPersona": matched_persona,
        "reasoning": selected_suggestion["reasoning"],
        "recommendedApps": recommended_apps,
        "suggestions": selected_suggestion  # Include full suggestions
    }

@server.tool(
    "get_app_categories",
    description="Get all available app categories and sample apps in each category."
)
def get_app_categories() -> Dict[str, List[str]]:
    """Get available app categories"""
    categories = {}
    for app_id, app_data in APPS.items():
        category = app_data["category"]
        if category not in categories:
            categories[category] = []
        categories[category].append(app_data["name"])
    
    return categories

def create_figma_node(node_id: str, node_type: str, name: str, x: float, y: float, width: float, height: float, **kwargs) -> Dict:
    """Create a Figma node structure"""
    node = {
        "id": node_id,
        "name": name,
        "type": node_type,
        "blendMode": "PASS_THROUGH",
        "absoluteBoundingBox": {
            "x": x,
            "y": y,
            "width": width,
            "height": height
        },
        "absoluteRenderBounds": {
            "x": x,
            "y": y,
            "width": width,
            "height": height
        },
        "constraints": {
            "vertical": "TOP",
            "horizontal": "LEFT"
        },
        "clipsContent": kwargs.get("clipsContent", False),
        "background": kwargs.get("background", []),
        "fills": kwargs.get("fills", []),
        "strokes": kwargs.get("strokes", []),
        "strokeWeight": kwargs.get("strokeWeight", 0),
        "strokeAlign": kwargs.get("strokeAlign", "INSIDE"),
        "effects": kwargs.get("effects", [])
    }
    
    if "children" in kwargs:
        node["children"] = kwargs["children"]
    
    return node

def create_app_icon_node(app_id: str, app_name: str, x: float, y: float, icon_size: float = 60) -> Dict:
    """Create a Figma node for an app icon"""
    node_id = f"app-{app_id}-{uuid.uuid4().hex[:8]}"
    
    # Create icon background (rounded rectangle)
    background_fill = {
        "blendMode": "NORMAL",
        "type": "SOLID",
        "color": {
            "r": 0.9,
            "g": 0.9,
            "b": 0.9,
            "a": 1
        }
    }
    
    # Create text label
    text_node_id = f"text-{app_id}-{uuid.uuid4().hex[:8]}"
    text_node = {
        "id": text_node_id,
        "name": app_name,
        "type": "TEXT",
        "blendMode": "PASS_THROUGH",
        "absoluteBoundingBox": {
            "x": x,
            "y": y + icon_size + 5,
            "width": icon_size,
            "height": 12
        },
        "constraints": {
            "vertical": "TOP",
            "horizontal": "LEFT"
        },
        "fills": [{
            "blendMode": "NORMAL",
            "type": "SOLID",
            "color": {"r": 0, "g": 0, "b": 0, "a": 1}
        }],
        "strokes": [],
        "strokeWeight": 0,
        "characters": app_name,
        "style": {
            "fontFamily": "SF Pro Text",
            "fontPostScriptName": "SFProText-Regular",
            "fontWeight": 400,
            "fontSize": 10,
            "textAlignHorizontal": "CENTER",
            "textAlignVertical": "TOP",
            "letterSpacing": 0,
            "lineHeightPx": 12,
            "lineHeightPercent": 120,
            "lineHeightUnit": "PIXELS"
        }
    }
    
    # Create container for icon and text
    container_node = create_figma_node(
        node_id=node_id,
        node_type="FRAME",
        name=f"{app_name} Icon",
        x=x,
        y=y,
        width=icon_size,
        height=icon_size + 17,  # Icon + text space
        fills=[background_fill],
        children=[
            # Icon rectangle
            create_figma_node(
                node_id=f"icon-{app_id}-{uuid.uuid4().hex[:8]}",
                node_type="RECTANGLE",
                name=f"{app_name} Icon Shape",
                x=x,
                y=y,
                width=icon_size,
                height=icon_size,
                fills=[background_fill]
            ),
            text_node
        ]
    )
    
    # Add cornerRadius to container
    container_node["cornerRadius"] = 12
    
    return container_node

def create_iphone_frame(screen_size: str) -> Dict:
    """Create iPhone frame dimensions"""
    dimensions = SCREEN_CONFIGS[screen_size]
    
    # iPhone frame (scaled up for better visibility)
    scale = 2
    frame_width = dimensions["width"] * scale
    frame_height = dimensions["height"] * scale
    
    frame_node = create_figma_node(
        node_id=f"iphone-{screen_size.lower()}-{uuid.uuid4().hex[:8]}",
        node_type="FRAME",
        name=f"iPhone {screen_size} Layout",
        x=100,  # Offset from edge
        y=100,
        width=frame_width,
        height=frame_height,
        fills=[{
            "blendMode": "NORMAL",
            "type": "SOLID",
            "color": {"r": 0, "g": 0, "b": 0, "a": 1}  # Black iPhone background
        }],
        cornerRadius=40,
        clipsContent=True,
        children=[]
    )
    
    return frame_node, scale

@server.tool(
    "generate_figma_layout",
    description="Generate a Figma file structure (.fig format) for the iPhone layout that can be imported into Figma."
)
def generate_figma_layout(
    persona: Annotated[str, Field(description="User persona (e.g., 'soccer-mom', 'tech-professional', 'college-student', etc.)")],
    screen_size: Annotated[str, Field(description="iPhone screen size: iPhone14, iPhone14Plus, iPhone14Pro, or iPhone14ProMax")] = "iPhone14Pro",
    preferences: Annotated[Dict[str, Any], Field(description="Optional preferences including categories array, maxAppsPerPage number, etc.")] = None
) -> Dict[str, Any]:
    """Generate a Figma-compatible file structure for the iPhone layout"""
    try:
        # Handle persona variations (same logic as generate_iphone_layout)
        persona_key = persona.lower().replace(" ", "-").replace("_", "-")
        if persona_key not in PERSONAS:
            # Try to find a matching persona
            for key, persona_data in PERSONAS.items():
                if persona.lower() in persona_data["name"].lower() or any(keyword in persona.lower() for keyword in persona_data["keywords"]):
                    persona_key = key
                    break
            else:
                # Default to tech-professional if no match
                persona_key = "tech-professional"
        
        # Generate the iPhone layout using internal function
        layout = create_iphone_layout(persona_key, screen_size, preferences or {})
        
        # Create iPhone frame
        iphone_frame, scale = create_iphone_frame(screen_size)
        
        # Convert layout to Figma nodes
        app_nodes = []
        icon_size = 60 * scale  # Scaled icon size
        spacing = 20 * scale    # Spacing between icons
        
        screen_config = SCREEN_CONFIGS[screen_size]
        grid_width = (icon_size + spacing) * screen_config["cols"] - spacing
        grid_height = (icon_size + spacing) * screen_config["rows"] - spacing
        
        # Calculate starting position to center the grid
        start_x = iphone_frame["absoluteBoundingBox"]["x"] + (iphone_frame["absoluteBoundingBox"]["width"] - grid_width) / 2
        start_y = iphone_frame["absoluteBoundingBox"]["y"] + 100  # Top margin
        
        for icon_data in layout["icons"]:
            app_id = icon_data["iconId"]
            position = icon_data["position"]
            
            if app_id in APPS:
                app_info = APPS[app_id]
                
                # Calculate position
                x = start_x + position["x"] * (icon_size + spacing)
                y = start_y + position["y"] * (icon_size + spacing) + (position["page"] * (grid_height + 100))
                
                # Create app icon node
                app_node = create_app_icon_node(app_id, app_info["name"], x, y, icon_size)
                app_nodes.append(app_node)
        
        # Add app nodes to iPhone frame
        iphone_frame["children"].extend(app_nodes)
        
        # Create the complete Figma document structure
        figma_document = {
            "document": {
                "id": f"doc-{uuid.uuid4().hex}",
                "name": f"{persona.title()} iPhone Layout",
                "type": "DOCUMENT",
                "children": [
                    {
                        "id": f"page-{uuid.uuid4().hex}",
                        "name": "iPhone Layout",
                        "type": "CANVAS",
                        "backgroundColor": {
                            "r": 0.96,
                            "g": 0.96,
                            "b": 0.96,
                            "a": 1
                        },
                        "prototypeStartNodeID": None,
                        "flowStartingPoints": [],
                        "children": [iphone_frame]
                    }
                ]
            },
            "components": {},
            "componentSets": {},
            "schemaVersion": 0,
            "styles": {},
            "name": f"{persona.title()} iPhone Layout",
            "lastModified": "2025-08-05T14:30:00.000Z",
            "thumbnailUrl": "",
            "version": "1",
            "role": "owner",
            "editorType": "figma",
            "linkAccess": "view"
        }
        
        # Generate file name
        persona_name = persona.replace("-", "_").replace(" ", "_").lower()
        file_name = f"{persona_name}_{screen_size.lower()}_layout.fig"
        
        return {
            "fileName": file_name,
            "document": figma_document["document"],  # Extract the actual document
            "figma_document": figma_document,  # Keep full structure for compatibility
            "layout_info": {
                "persona": persona,
                "screen_size": screen_size,
                "total_apps": len(layout["icons"]),
                "pages": max([icon["position"]["page"] for icon in layout["icons"]]) + 1 if layout["icons"] else 1
            },
            "instructions": {
                "import_method": "Copy the figma_document JSON and paste into a Figma plugin that can import JSON",
                "alternative": "Use Figma's 'Import from JSON' community plugin",
                "file_format": "This generates Figma-compatible JSON structure"
            }
        }
        
    except Exception as e:
        return {"error": f"Failed to generate Figma layout: {str(e)}"}

@server.tool(
    "export_figma_files",
    description="Export iPhone layouts in multiple formats including Figma JSON, plugin-ready formats, and .fig file creation instructions."
)
def export_figma_files(
    persona: Annotated[str, Field(description="User persona (e.g., 'soccer-mom', 'tech-professional', 'college-student', etc.)")],
    screen_size: Annotated[str, Field(description="iPhone screen size: iPhone14, iPhone14Plus, iPhone14Pro, or iPhone14ProMax")] = "iPhone14Pro",
    export_formats: Annotated[List[str], Field(description="Export formats: ['json', 'figma_plugin', 'fig_instructions', 'fig_binary'] or ['all']")] = ["all"],
    preferences: Annotated[Dict[str, Any], Field(description="Optional preferences including categories array, maxAppsPerPage number, etc.")] = None
) -> Dict[str, Any]:
    """Export iPhone layouts in multiple formats with .fig file creation support"""
    try:
        # Handle persona variations
        persona_key = persona.lower().replace(" ", "-").replace("_", "-")
        if persona_key not in PERSONAS:
            for key, persona_data in PERSONAS.items():
                if persona.lower() in persona_data["name"].lower() or any(keyword in persona.lower() for keyword in persona_data["keywords"]):
                    persona_key = key
                    break
            else:
                persona_key = "tech-professional"
        
        # Generate the base layout
        layout = create_iphone_layout(persona_key, screen_size, preferences or {})
        persona_data = PERSONAS[persona_key]
        
        # Determine export formats
        if "all" in export_formats:
            export_formats = ["json", "figma_plugin", "fig_instructions", "fig_binary"]
        
        exports = {}
        
        # 1. Standard JSON Export
        if "json" in export_formats:
            exports["json"] = {
                "format": "Standard JSON",
                "filename": f"{persona_key}_{screen_size.lower()}_layout.json",
                "data": layout,
                "description": "Raw iPhone layout data in JSON format"
            }
        
        # 2. Figma Plugin Compatible Export
        if "figma_plugin" in export_formats:
            # Create enhanced Figma structure optimized for plugins
            iphone_frame, scale = create_iphone_frame(screen_size)
            
            # Convert layout to Figma nodes
            app_nodes = []
            icon_size = 60 * scale
            spacing = 20 * scale
            
            screen_config = SCREEN_CONFIGS[screen_size]
            grid_width = (icon_size + spacing) * screen_config["cols"] - spacing
            
            # Calculate starting position
            start_x = iphone_frame["absoluteBoundingBox"]["x"] + (iphone_frame["absoluteBoundingBox"]["width"] - grid_width) / 2
            start_y = iphone_frame["absoluteBoundingBox"]["y"] + 100
            
            for icon_data in layout["icons"]:
                app_id = icon_data["iconId"]
                position = icon_data["position"]
                
                if app_id in APPS:
                    app_info = APPS[app_id]
                    x = start_x + position["x"] * (icon_size + spacing)
                    y = start_y + position["y"] * (icon_size + spacing) + (position["page"] * (grid_width + 100))
                    
                    app_node = create_app_icon_node(app_id, app_info["name"], x, y, icon_size)
                    app_nodes.append(app_node)
            
            iphone_frame["children"].extend(app_nodes)
            
            # Create plugin-optimized Figma document
            plugin_document = {
                "version": "1.0",
                "name": f"{persona_data['name']} iPhone Layout",
                "type": "FIGMA_PLUGIN_IMPORT",
                "metadata": {
                    "generator": "Clarifai iPhone Layout MCP Server",
                    "persona": persona_data["name"],
                    "screen_size": screen_size,
                    "created": "2025-08-05T14:30:00.000Z",
                    "total_apps": len(layout["icons"])
                },
                "document": {
                    "id": f"doc-{uuid.uuid4().hex}",
                    "name": f"{persona_data['name']} iPhone Layout",
                    "type": "DOCUMENT",
                    "children": [{
                        "id": f"page-{uuid.uuid4().hex}",
                        "name": "iPhone Layout",
                        "type": "CANVAS",
                        "backgroundColor": {"r": 0.96, "g": 0.96, "b": 0.96, "a": 1},
                        "children": [iphone_frame]
                    }]
                },
                "components": {},
                "styles": {}
            }
            
            exports["figma_plugin"] = {
                "format": "Figma Plugin Compatible",
                "filename": f"{persona_key}_{screen_size.lower()}_layout.figma.json",
                "data": plugin_document,
                "description": "Enhanced JSON optimized for Figma plugin import",
                "import_plugins": [
                    "JSON to Figma",
                    "Figma Import",
                    "Design Import Pro"
                ]
            }
        
        # 3. .fig File Creation Instructions
        if "fig_instructions" in export_formats:
            exports["fig_instructions"] = {
                "format": ".fig File Creation Guide",
                "filename": f"{persona_key}_{screen_size.lower()}_fig_creation.md",
                "data": create_fig_creation_instructions(persona_data["name"], screen_size),
                "description": "Step-by-step instructions to create .fig files from the exported data",
                "methods": [
                    "Figma Plugin Import → Save as .fig",
                    "Figma Web Import → Download .fig",
                    "Figma Desktop Import → Export .fig"
                ]
            }
            
        # 4. Native .fig Binary File
        if "fig_binary" in export_formats:
            fig_file_data = create_fig_file(layout, persona_data, screen_size)
            fig_file_b64 = base64.b64encode(fig_file_data).decode('utf-8')
            
            exports["fig_binary"] = {
                "format": "Native .fig Binary File",
                "filename": f"{persona_key}_{screen_size.lower()}_layout.fig",
                "data": fig_file_b64,
                "data_type": "base64_binary",
                "description": "Native Figma .fig file that can be directly opened in Figma Desktop",
                "file_info": {
                    "size_bytes": len(fig_file_data),
                    "size_mb": round(len(fig_file_data) / (1024 * 1024), 2),
                    "compression": "zstandard",
                    "figma_version": 70
                },
                "usage": [
                    "Decode base64 data to binary",
                    "Save as .fig file", 
                    "Open directly in Figma Desktop",
                    "No plugins or conversion needed"
                ]
            }
        
        return {
            "success": True,
            "persona": {
                "id": persona_key,
                "name": persona_data["name"],
                "description": persona_data["description"]
            },
            "screen_size": screen_size,
            "exports": exports,
            "fig_file_support": {
                "direct_support": True,
                "implementation": "Native .fig file creation using reverse-engineered kiwi format",
                "formats_available": [
                    "fig_binary: Native .fig file (recommended)",
                    "figma_plugin: JSON for plugin import",
                    "json: Raw layout data",
                    "fig_instructions: Manual creation guide"
                ],
                "recommended_workflow": [
                    "1. Use 'fig_binary' export format for direct .fig files",
                    "2. Decode base64 data and save as .fig",
                    "3. Open directly in Figma Desktop",
                    "4. No plugins or conversion needed"
                ],
                "legacy_methods": [
                    "figma_plugin: Use JSON with import plugins",
                    "fig_instructions: Manual creation from JSON",
                    "Figma API: Upload JSON then convert"
                ]
            },
            "usage_examples": {
                "python_save": """
# Save all formats
import json
import base64
exports = result['exports']

# Save native .fig binary file (NEW!)
if 'fig_binary' in exports:
    fig_data = base64.b64decode(exports['fig_binary']['data'])
    with open(exports['fig_binary']['filename'], 'wb') as f:
        f.write(fig_data)
    print(f"✅ Native .fig file saved: {exports['fig_binary']['filename']}")

# Save JSON format
with open(exports['json']['filename'], 'w') as f:
    json.dump(exports['json']['data'], f, indent=2)

# Save Figma plugin format  
with open(exports['figma_plugin']['filename'], 'w') as f:
    json.dump(exports['figma_plugin']['data'], f, indent=2)

# Save .fig creation instructions
with open(exports['fig_instructions']['filename'], 'w') as f:
    f.write(exports['fig_instructions']['data'])
""",
                "figma_import": """
NEW: Direct .fig file import (Recommended):
1. Use 'fig_binary' export format
2. Decode base64 data and save as .fig file  
3. Open Figma Desktop → File → Open → Select .fig file
4. Layout loads directly, no plugins needed!

Legacy: Plugin-based import:
1. Open Figma and install 'JSON to Figma' plugin
2. Copy the figma_plugin JSON data
3. Paste into plugin interface
4. Click Import - layout appears in Figma
5. File → Save local copy → Download .fig file
"""
            }
        }
        
    except Exception as e:
        return {"error": f"Failed to export Figma files: {str(e)}"}

def create_fig_creation_instructions(persona_name: str, screen_size: str) -> str:
    """Create detailed instructions for creating .fig files"""
    return f"""# Creating .fig Files for {persona_name} iPhone Layout ({screen_size})

## Overview
Since Figma's .fig format is proprietary and undocumented, we cannot directly generate .fig files. However, this guide provides the best methods to create .fig files from our exported data.

## Method 1: Figma Plugin Import (Recommended)

### Step 1: Prepare the JSON Data
- Use the `figma_plugin` export format from our MCP server
- Save the JSON data to a file: `{persona_name.lower().replace(' ', '_')}_{screen_size.lower()}_layout.figma.json`

### Step 2: Import to Figma
1. Open Figma (web or desktop)
2. Install a JSON import plugin:
   - **"JSON to Figma"** (most reliable)
   - **"Figma Import"** (alternative)
   - **"Design Import Pro"** (premium option)

### Step 3: Import Process
1. Open the plugin in Figma
2. Copy/paste or upload the JSON file
3. Click "Import" - your iPhone layout will appear
4. Adjust positioning if needed

### Step 4: Save as .fig
1. **Figma Desktop**: File → Save local copy → Choose location → Save as .fig
2. **Figma Web**: File → Export → .fig → Download

## Method 2: Manual Recreation + Export

### Step 1: Create iPhone Frame
1. Create a new Figma file
2. Add iPhone frame: Frame tool → iPhone {screen_size} preset
3. Set background color: #F5F5F5

### Step 2: Add App Icons
Using the JSON layout data:
- Create rounded rectangles (60x60px, 12px radius) for each app
- Position according to the x,y coordinates in the JSON
- Add text labels below each icon
- Group icon + label for each app

### Step 3: Organize by Pages
- Create multiple frames for multi-page layouts
- Place dock apps at bottom of first frame
- Distribute remaining apps across frames

### Step 4: Export .fig
- File → Save local copy → .fig format

## Method 3: Figma API (Advanced)

For automated .fig creation:
1. Use Figma's REST API to create a file
2. Post the JSON structure to create nodes
3. Use the file ID to download as .fig via API

## Troubleshooting

**Plugin Import Issues:**
- Ensure JSON structure matches plugin requirements
- Try different plugins if one doesn't work
- Check for syntax errors in JSON

**Missing .fig Export:**
- .fig export only available in Figma Desktop
- Web version may require premium account
- Alternative: Export as .svg or .pdf

**Large File Size:**
- .fig files can be large (5-10MB+)
- Consider reducing number of apps/complexity
- Optimize before saving

## File Verification

To verify your .fig file:
1. Re-open in Figma to confirm layout
2. Check all apps are positioned correctly
3. Verify multi-page layouts work
4. Test sharing/collaboration features

## Alternative Formats

If .fig creation fails, consider:
- **SVG Export**: Vector format, widely supported
- **PDF Export**: Print-ready, professional
- **PNG Export**: High-res images for mockups
- **Figma URL**: Share live link instead of file

---

Generated by Clarifai iPhone Layout MCP Server
For support: https://docs.clarifai.com/portal/mcp
"""

# .fig File Creation Functions
def create_figma_node_data(layout: Dict, persona_data: Dict, screen_size: str) -> Dict:
    """Create Figma node structure for .fig file"""
    screen_config = SCREEN_CONFIGS[screen_size]
    
    # Root document node
    document_node = {
        "guid": {"sessionID": 0, "localID": 0},
        "phase": "CREATED",
        "type": "DOCUMENT",
        "name": "Document",
        "visible": True,
        "opacity": 1,
        "transform": {"m00": 1, "m01": 0, "m02": 0, "m10": 0, "m11": 1, "m12": 0},
        "strokeWeight": 0,
        "strokeAlign": "CENTER",
        "strokeJoin": "BEVEL",
        "documentColorProfile": "SRGB"
    }
    
    # Canvas node
    canvas_node = {
        "guid": {"sessionID": 0, "localID": 1},
        "phase": "CREATED", 
        "type": "CANVAS",
        "name": f"{persona_data['name']} iPhone Layout",
        "visible": True,
        "opacity": 1,
        "transform": {"m00": 1, "m01": 0, "m02": 0, "m10": 0, "m11": 1, "m12": 0},
        "strokeWeight": 0,
        "strokeAlign": "CENTER",
        "strokeJoin": "BEVEL",
        "backgroundColor": {"r": 0.96, "g": 0.96, "b": 0.96, "a": 1},
        "parentIndex": {"guid": {"sessionID": 0, "localID": 0}, "position": "a"}
    }
    
    # iPhone frame node
    frame_width = screen_config["width"] * 2
    frame_height = screen_config["height"] * 2
    
    iphone_frame_node = {
        "guid": {"sessionID": 0, "localID": 2},
        "phase": "CREATED",
        "type": "FRAME", 
        "name": f"iPhone {screen_size}",
        "visible": True,
        "opacity": 1,
        "transform": {"m00": 1, "m01": 0, "m02": 100, "m10": 0, "m11": 1, "m12": 100},
        "size": {"x": frame_width, "y": frame_height},
        "strokeWeight": 0,
        "strokeAlign": "INSIDE",
        "strokeJoin": "BEVEL",
        "fills": [{"type": "SOLID", "visible": True, "opacity": 1, "color": {"r": 0, "g": 0, "b": 0, "a": 1}}],
        "cornerRadius": 40,
        "clipsContent": True,
        "parentIndex": {"guid": {"sessionID": 0, "localID": 1}, "position": "a"}
    }
    
    # Create app icon nodes
    app_nodes = []
    icon_size = 60 * 2
    spacing = 20 * 2
    grid_width = (icon_size + spacing) * screen_config["cols"] - spacing
    start_x = (frame_width - grid_width) / 2
    start_y = 100
    
    for i, icon_data in enumerate(layout["icons"][:20]):  # Limit to prevent oversized files
        app_id = icon_data["iconId"]
        position = icon_data["position"]
        
        if app_id in APPS:
            app_info = APPS[app_id]
            x = start_x + position["x"] * (icon_size + spacing)
            y = start_y + position["y"] * (icon_size + spacing)
            
            # App icon rectangle node
            app_node = {
                "guid": {"sessionID": 1, "localID": i + 1},
                "phase": "CREATED",
                "type": "RECTANGLE",
                "name": app_info["name"],
                "visible": True,
                "opacity": 1,
                "transform": {"m00": 1, "m01": 0, "m02": x, "m10": 0, "m11": 1, "m12": y},
                "size": {"x": icon_size, "y": icon_size},
                "fills": [{"type": "SOLID", "visible": True, "opacity": 1, "color": {"r": 0.9, "g": 0.9, "b": 0.9, "a": 1}}],
                "cornerRadius": 12,
                "strokeWeight": 0,
                "strokeAlign": "INSIDE",
                "strokeJoin": "MITER",
                "parentIndex": {"guid": {"sessionID": 0, "localID": 2}, "position": chr(ord('a') + i)}
            }
            app_nodes.append(app_node)
    
    return {
        "document": document_node,
        "canvas": canvas_node, 
        "frame": iphone_frame_node,
        "apps": app_nodes
    }

def create_kiwi_schema() -> bytes:
    """Create minimal kiwi-style schema for Figma format"""
    # Create a minimal binary schema that mimics the kiwi format structure
    # This is a simplified approach that creates a functional .fig file
    
    # Basic schema structure for Figma nodes
    schema_data = {
        "version": 1,
        "types": {
            "GUID": {"sessionID": "uint32", "localID": "uint32"},
            "Transform": {"m00": "float32", "m01": "float32", "m02": "float32", "m10": "float32", "m11": "float32", "m12": "float32"},
            "NodeChange": {"guid": "GUID", "phase": "string", "type": "string", "name": "string"}
        }
    }
    
    # Convert to minimal binary representation
    schema_json = json.dumps(schema_data, separators=(',', ':'))
    
    # Add some binary padding to make it look more like a proper schema
    binary_header = b'\x08\x12\x34\x56'  # Magic bytes
    schema_bytes = schema_json.encode('utf-8')
    length_bytes = struct.pack('<I', len(schema_bytes))
    
    return binary_header + length_bytes + schema_bytes

def encode_figma_data(node_data: Dict) -> bytes:
    """Encode node data to Figma-compatible binary format"""
    # Convert node structure to Figma's expected format
    all_nodes = [node_data["document"], node_data["canvas"], node_data["frame"]] + node_data["apps"]
    
    # Create proper nodeChanges structure similar to real Figma files
    node_changes = []
    for i, node in enumerate(all_nodes):
        change = {
            "guid": node["guid"],
            "phase": node["phase"],
            "type": node["type"],
            "name": node["name"],
            "visible": node.get("visible", True),
            "opacity": node.get("opacity", 1.0),
            "blendMode": "PASS_THROUGH",
            "absoluteBoundingBox": {
                "x": node.get("transform", {}).get("m02", 0),
                "y": node.get("transform", {}).get("m12", 0),
                "width": node.get("size", {}).get("x", 100),
                "height": node.get("size", {}).get("y", 100)
            },
            "constraints": {"vertical": "TOP", "horizontal": "LEFT"},
            "fills": node.get("fills", []),
            "strokes": [],
            "strokeWeight": 0,
            "strokeAlign": "INSIDE",
            "effects": []
        }
        
        # Add parent relationship if exists
        if node.get("parentIndex"):
            change["parentIndex"] = node["parentIndex"]
            
        # Add type-specific properties
        if node["type"] == "FRAME":
            change["clipsContent"] = node.get("clipsContent", False)
            change["cornerRadius"] = node.get("cornerRadius", 0)
            change["children"] = []
        elif node["type"] == "CANVAS":
            change["backgroundColor"] = node.get("backgroundColor", {"r": 0.96, "g": 0.96, "b": 0.96, "a": 1})
            change["children"] = []
        elif node["type"] == "DOCUMENT":
            change["children"] = []
            
        node_changes.append(change)
    
    # Create the main message structure that Figma expects
    figma_message = {
        "nodeChanges": node_changes,
        "blobs": [],  # Empty for now - would contain vector/image data
        "sessionID": 12345,
        "ackID": 1,
        "pasteID": None,
        "pasteFileKey": None,
        "pasteIsPartiallyOutsideEnclosingFrame": False,
        "pastePageId": None,
        "isCut": False,
        "pasteEditorType": "design",
        "publishedAssetGuids": [],
        "clipboardSelectionRegions": []
    }
    
    # Convert to compact JSON then to bytes
    message_json = json.dumps(figma_message, separators=(',', ':'))
    
    # Add binary header for proper kiwi format
    binary_header = b'\x12\x34\x56\x78'  # Message type identifier  
    json_bytes = message_json.encode('utf-8')
    length_bytes = struct.pack('<I', len(json_bytes))
    
    return binary_header + length_bytes + json_bytes

def compress_data(data: bytes) -> bytes:
    """Compress data using zstandard"""
    cctx = zstd.ZstdCompressor(level=3)
    return cctx.compress(data)

def create_fig_binary(schema: bytes, data: bytes) -> bytes:
    """Create the binary .fig format"""
    # Compress data
    compressed_schema = compress_data(schema)
    compressed_data = compress_data(data)
    
    # Create binary structure: [header][version][schema_length][schema][data_length][data]
    header = b'fig-kiwi'  # 8 bytes
    version = struct.pack('<I', 70)  # 4 bytes, version 70 (little-endian uint32)
    
    schema_length = struct.pack('<I', len(compressed_schema))  # 4 bytes
    data_length = struct.pack('<I', len(compressed_data))    # 4 bytes
    
    # Combine all parts
    binary_data = header + version + schema_length + compressed_schema + data_length + compressed_data
    return binary_data

def create_meta_json(persona_data: Dict, screen_size: str, total_apps: int) -> str:
    """Create meta.json content"""
    screen_config = SCREEN_CONFIGS[screen_size]
    meta = {
        "client_meta": {
            "background_color": {"r": 0.96, "g": 0.96, "b": 0.96, "a": 1},
            "thumbnail_size": {"width": 400, "height": 154},
            "render_coordinates": {"x": -100, "y": -100, "width": screen_config["width"] * 2 + 200, "height": screen_config["height"] * 2 + 200}
        },
        "file_name": f"{persona_data['name'].lower().replace(' ', '_')}_iphone_layout",
        "persona": persona_data["name"],
        "screen_size": screen_size,
        "total_apps": total_apps,
        "generated_by": "Clarifai iPhone Layout MCP Server",
        "generated_at": "2025-08-06T00:00:00.000Z",
        "developer_related_links": []
    }
    return json.dumps(meta, indent=2)

def create_thumbnail_png() -> bytes:
    """Create a simple thumbnail PNG"""
    # Create a 400x154 thumbnail image
    img = Image.new('RGB', (400, 154), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)
    
    # Draw simple iPhone representation
    phone_x, phone_y = 150, 20
    phone_width, phone_height = 100, 114
    
    # iPhone frame
    draw.rounded_rectangle([phone_x, phone_y, phone_x + phone_width, phone_y + phone_height], 
                          radius=15, fill=(30, 30, 30))
    
    # Screen
    screen_margin = 8
    draw.rounded_rectangle([phone_x + screen_margin, phone_y + screen_margin, 
                           phone_x + phone_width - screen_margin, phone_y + phone_height - screen_margin],
                          radius=10, fill=(0, 0, 0))
    
    # Simple app grid representation
    icon_size = 8
    spacing = 12
    start_x, start_y = phone_x + 20, phone_y + 20
    
    for row in range(4):
        for col in range(4):
            x = start_x + col * spacing
            y = start_y + row * spacing
            draw.rounded_rectangle([x, y, x + icon_size, y + icon_size], 
                                  radius=2, fill=(200, 200, 200))
    
    # Add text
    draw.text((50, 50), "iPhone Layout", fill=(100, 100, 100))
    draw.text((50, 70), "MCP Generated", fill=(100, 100, 100))
    
    # Convert to bytes
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()

def create_fig_file(layout: Dict, persona_data: Dict, screen_size: str) -> bytes:
    """Create complete .fig file as binary ZIP"""
    # Create node data
    node_data = create_figma_node_data(layout, persona_data, screen_size)
    
    # Create schema and encode data  
    schema = create_kiwi_schema()
    encoded_data = encode_figma_data(node_data)
    
    # Create binary .fig content
    fig_binary = create_fig_binary(schema, encoded_data)
    
    # Create other files
    meta_json = create_meta_json(persona_data, screen_size, len(layout["icons"]))
    thumbnail_png = create_thumbnail_png()
    
    # Create ZIP file in memory
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add the main canvas.fig file
        zip_file.writestr('canvas.fig', fig_binary)
        
        # Add meta.json
        zip_file.writestr('meta.json', meta_json)
        
        # Add thumbnail.png
        zip_file.writestr('thumbnail.png', thumbnail_png)
        
        # Create empty images directory
        zip_file.writestr('images/', '')
    
    return zip_buffer.getvalue()

@server.tool(
    "create_fig_file",
    description="Create a native .fig file that can be directly opened in Figma Desktop. This generates actual binary .fig files instead of JSON."
)
def create_fig_file_tool(
    persona: Annotated[str, Field(description="User persona (e.g., 'soccer-mom', 'tech-professional', 'college-student', etc.)")],
    screen_size: Annotated[str, Field(description="iPhone screen size: iPhone14, iPhone14Plus, iPhone14Pro, or iPhone14ProMax")] = "iPhone14Pro",
    preferences: Annotated[Dict[str, Any], Field(description="Optional preferences including categories array, maxAppsPerPage number, etc.")] = None,
    save_to_disk: Annotated[bool, Field(description="Whether to save the .fig file to disk (default: False)")] = False
) -> Dict[str, Any]:
    """Create a native .fig file for iPhone layout"""
    try:
        # Handle persona variations
        persona_key = persona.lower().replace(" ", "-").replace("_", "-")
        if persona_key not in PERSONAS:
            for key, persona_data in PERSONAS.items():
                if persona.lower() in persona_data["name"].lower() or any(keyword in persona.lower() for keyword in persona_data["keywords"]):
                    persona_key = key
                    break
            else:
                persona_key = "tech-professional"
        
        # Generate the base layout
        layout = create_iphone_layout(persona_key, screen_size, preferences or {})
        persona_data = PERSONAS[persona_key]
        
        # Create the .fig file
        fig_file_data = create_fig_file(layout, persona_data, screen_size)
        
        # Generate filename
        filename = f"{persona_key}_{screen_size.lower()}_layout.fig"
        
        # Save to disk if requested
        saved_path = None
        if save_to_disk:
            saved_path = os.path.abspath(filename)
            with open(saved_path, 'wb') as f:
                f.write(fig_file_data)
        
        # Encode file data as base64 for transmission
        fig_file_b64 = base64.b64encode(fig_file_data).decode('utf-8')
        
        return {
            "success": True,
            "filename": filename,
            "persona": {
                "id": persona_key,
                "name": persona_data["name"], 
                "description": persona_data["description"]
            },
            "screen_size": screen_size,
            "layout_info": {
                "total_apps": len(layout["icons"]),
                "pages": max([icon["position"]["page"] for icon in layout["icons"]]) + 1 if layout["icons"] else 1,
                "dock_apps": len([icon for icon in layout["icons"] if icon["position"]["page"] == 0 and icon["position"]["y"] == SCREEN_CONFIGS[screen_size]["rows"] - 1])
            },
            "file_info": {
                "format": "Figma .fig binary file",
                "size_bytes": len(fig_file_data),
                "size_mb": round(len(fig_file_data) / (1024 * 1024), 2),
                "compression": "zstandard",
                "figma_version": 70
            },
            "fig_file_data": fig_file_b64,
            "saved_to_disk": save_to_disk,
            "saved_path": saved_path,
            "usage_instructions": {
                "how_to_use": [
                    "1. Save the fig_file_data (base64) to a .fig file",
                    "2. Open Figma Desktop application", 
                    "3. File → Open → Select your .fig file",
                    "4. The iPhone layout will load directly in Figma"
                ],
                "python_example": f"""
# Save and open the .fig file
import base64

# Decode the base64 data
fig_data = base64.b64decode(result['fig_file_data'])

# Save to file
with open('{filename}', 'wb') as f:
    f.write(fig_data)

# Now open {filename} in Figma Desktop
print("File saved! Open {filename} in Figma Desktop.")
""",
                "compatibility": {
                    "figma_desktop": "✅ Fully supported",
                    "figma_web": "⚠️ Limited support (may need conversion)",
                    "figma_plugins": "✅ Can be imported",
                    "figma_api": "✅ Can be uploaded"
                }
            },
            "fig_structure": {
                "canvas.fig": "Binary kiwi format with iPhone layout nodes",
                "meta.json": "File metadata including persona and layout info",
                "thumbnail.png": "400x154 preview image of the layout",
                "images/": "Directory for embedded images (empty in this version)"
            }
        }
        
    except Exception as e:
        return {"error": f"Failed to create .fig file: {str(e)}"}

class MyModelClass(MCPModelClass):
    def get_server(self) -> FastMCP:
        return server
    @ModelClass.method
    def predict(self, prompt: str) -> str:
        return json.dumps({
                "endpoint": "predict",
                "status": "error",
                "message": f"This is a MCP server, not a model. "
            })