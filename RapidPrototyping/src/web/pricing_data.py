"""
Clarifai Compute Orchestration Pricing Data

This module loads pricing information from config/pricing.json and provides
helper functions for querying and analyzing compute resources.

To update pricing:
1. Edit config/pricing.json
2. Restart the application
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CloudProvider(Enum):
    AWS_US_EAST_1 = "aws-us-east-1"
    AWS_US_WEST_2 = "aws-us-west-2"
    GCP_US_EAST_4 = "gcp-us-east-4"
    VULTR_NEW_YORK = "vultr-new-york"
    VULTR_ATLANTA = "vultr-atlanta"
    VULTR_CHICAGO = "vultr-chicago"
    VULTR_SEATTLE = "vultr-seattle"
    CLARIFAI = "clarifai"


class ResourceType(Enum):
    CPU = "cpu"
    GPU = "gpu"


@dataclass
class ComputeResource:
    """Represents a compute resource with pricing information."""
    name: str
    cloud_region: str
    cloud_instance: str
    resource_type: ResourceType
    vram_gb: Optional[int]  # None for CPU instances
    on_demand_hourly: float
    on_demand_monthly: float
    on_demand_annual: float
    clarifai_hourly: float
    clarifai_annual: float
    one_yr_no_upfront_monthly: Optional[float] = None
    one_yr_no_upfront_hourly: Optional[float] = None
    one_yr_no_upfront_discount: Optional[float] = None  # As decimal, e.g., 0.2393 = 23.93%
    one_yr_upfront_annual: Optional[float] = None
    one_yr_upfront_monthly: Optional[float] = None
    one_yr_upfront_hourly: Optional[float] = None
    one_yr_upfront_discount: Optional[float] = None

    @property
    def savings_vs_on_demand(self) -> float:
        """Calculate percentage savings with Clarifai vs on-demand."""
        if self.on_demand_annual > 0:
            return ((self.on_demand_annual - self.clarifai_annual) / self.on_demand_annual) * 100
        return 0

    @property
    def monthly_clarifai(self) -> float:
        """Calculate monthly Clarifai cost."""
        return self.clarifai_annual / 12


# ============================================================================
# LOAD PRICING DATA FROM JSON
# ============================================================================

def _find_pricing_file() -> Path:
    """Find the pricing.json file in various possible locations."""
    possible_paths = [
        Path("config/pricing.json"),
        Path("/app/config/pricing.json"),
        Path(__file__).parent.parent.parent / "config" / "pricing.json",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    raise FileNotFoundError(
        f"pricing.json not found. Searched: {[str(p) for p in possible_paths]}"
    )


def _load_pricing_data() -> Dict[str, Any]:
    """Load pricing data from JSON file."""
    try:
        pricing_file = _find_pricing_file()
        logger.info(f"Loading pricing data from: {pricing_file}")
        
        with open(pricing_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading pricing data: {e}")
        raise


def _parse_compute_resources(data: Dict[str, Any]) -> List[ComputeResource]:
    """Parse compute resources from JSON data."""
    resources = []
    
    for item in data.get("compute_resources", []):
        try:
            resource = ComputeResource(
                name=item["name"],
                cloud_region=item["cloud_region"],
                cloud_instance=item["cloud_instance"],
                resource_type=ResourceType(item["resource_type"]),
                vram_gb=item.get("vram_gb"),
                on_demand_hourly=item["on_demand_hourly"],
                on_demand_monthly=item["on_demand_monthly"],
                on_demand_annual=item["on_demand_annual"],
                clarifai_hourly=item["clarifai_hourly"],
                clarifai_annual=item["clarifai_annual"],
                one_yr_no_upfront_monthly=item.get("one_yr_no_upfront_monthly"),
                one_yr_no_upfront_hourly=item.get("one_yr_no_upfront_hourly"),
                one_yr_no_upfront_discount=item.get("one_yr_no_upfront_discount"),
                one_yr_upfront_annual=item.get("one_yr_upfront_annual"),
                one_yr_upfront_monthly=item.get("one_yr_upfront_monthly"),
                one_yr_upfront_hourly=item.get("one_yr_upfront_hourly"),
                one_yr_upfront_discount=item.get("one_yr_upfront_discount"),
            )
            resources.append(resource)
        except Exception as e:
            logger.warning(f"Error parsing resource {item.get('name', 'unknown')}: {e}")
            continue
    
    return resources


# Load data on module import
_PRICING_DATA = _load_pricing_data()
COMPUTE_RESOURCES: List[ComputeResource] = _parse_compute_resources(_PRICING_DATA)
GPU_TIERS: Dict[str, Any] = _PRICING_DATA.get("gpu_tiers", {})
RECOMMENDED_REGIONS: List[Dict[str, Any]] = _PRICING_DATA.get("recommended_regions", [])
WORKLOAD_PROFILES: Dict[str, Any] = _PRICING_DATA.get("workload_profiles", {})

logger.info(f"Loaded {len(COMPUTE_RESOURCES)} compute resources from pricing.json")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def reload_pricing_data():
    """Reload pricing data from JSON file (useful for runtime updates)."""
    global COMPUTE_RESOURCES, GPU_TIERS, RECOMMENDED_REGIONS, WORKLOAD_PROFILES, _PRICING_DATA
    
    _PRICING_DATA = _load_pricing_data()
    COMPUTE_RESOURCES = _parse_compute_resources(_PRICING_DATA)
    GPU_TIERS = _PRICING_DATA.get("gpu_tiers", {})
    RECOMMENDED_REGIONS = _PRICING_DATA.get("recommended_regions", [])
    WORKLOAD_PROFILES = _PRICING_DATA.get("workload_profiles", {})
    
    logger.info(f"Reloaded {len(COMPUTE_RESOURCES)} compute resources from pricing.json")


def get_resources_by_region(region: str) -> List[ComputeResource]:
    """Get all compute resources for a specific region."""
    return [r for r in COMPUTE_RESOURCES if r.cloud_region == region]


def get_resources_by_type(resource_type: ResourceType) -> List[ComputeResource]:
    """Get all resources of a specific type (CPU or GPU)."""
    return [r for r in COMPUTE_RESOURCES if r.resource_type == resource_type]


def get_gpu_resources() -> List[ComputeResource]:
    """Get all GPU resources."""
    return get_resources_by_type(ResourceType.GPU)


def get_cpu_resources() -> List[ComputeResource]:
    """Get all CPU resources."""
    return get_resources_by_type(ResourceType.CPU)


def get_resources_by_vram(min_vram: int, max_vram: Optional[int] = None) -> List[ComputeResource]:
    """Get GPU resources within a VRAM range."""
    resources = get_gpu_resources()
    if max_vram:
        return [r for r in resources if r.vram_gb and min_vram <= r.vram_gb <= max_vram]
    return [r for r in resources if r.vram_gb and r.vram_gb >= min_vram]


def get_resource_by_instance(cloud_instance: str, region: Optional[str] = None) -> Optional[ComputeResource]:
    """Get a specific resource by cloud instance name."""
    for r in COMPUTE_RESOURCES:
        if r.cloud_instance == cloud_instance:
            if region is None or r.cloud_region == region:
                return r
    return None


def get_cheapest_gpu(min_vram: int = 16, region: Optional[str] = None) -> Optional[ComputeResource]:
    """Get the cheapest GPU meeting minimum VRAM requirements."""
    resources = get_resources_by_vram(min_vram)
    if region:
        resources = [r for r in resources if r.cloud_region == region]
    if not resources:
        return None
    return min(resources, key=lambda r: r.clarifai_annual)


def get_best_value_gpu(min_vram: int = 16, region: Optional[str] = None) -> Optional[ComputeResource]:
    """Get the best value GPU (lowest cost per GB VRAM)."""
    resources = get_resources_by_vram(min_vram)
    if region:
        resources = [r for r in resources if r.cloud_region == region]
    if not resources:
        return None
    return min(resources, key=lambda r: r.clarifai_annual / r.vram_gb if r.vram_gb else float('inf'))


def calculate_annual_savings(resource: ComputeResource) -> Dict[str, float]:
    """Calculate annual savings for a resource."""
    on_demand = resource.on_demand_annual
    clarifai = resource.clarifai_annual
    
    return {
        "on_demand_annual": on_demand,
        "clarifai_annual": clarifai,
        "savings_amount": on_demand - clarifai if clarifai < on_demand else clarifai - on_demand,
        "savings_percent": ((on_demand - clarifai) / on_demand * 100) if on_demand > 0 else 0,
        "is_savings": clarifai < on_demand,
    }


def format_price(amount: float) -> str:
    """Format a price with proper currency formatting."""
    if amount >= 1000:
        return f"${amount:,.2f}"
    return f"${amount:.2f}"


def generate_pricing_table(
    resources: List[ComputeResource],
    include_reserved: bool = True,
    markdown: bool = True
) -> str:
    """Generate a pricing comparison table."""
    if markdown:
        lines = []
        lines.append("| Resource | Cloud Instance | VRAM | On-Demand/hr | Clarifai/hr | Annual (Clarifai) |")
        lines.append("|----------|----------------|------|--------------|-------------|-------------------|")
        
        for r in resources:
            vram = f"{r.vram_gb}GB" if r.vram_gb else "N/A"
            lines.append(
                f"| {r.name} | {r.cloud_instance} | {vram} | "
                f"{format_price(r.on_demand_hourly)} | {format_price(r.clarifai_hourly)} | "
                f"{format_price(r.clarifai_annual)} |"
            )
        
        return "\n".join(lines)
    
    # Plain text format
    lines = []
    for r in resources:
        vram = f"{r.vram_gb}GB" if r.vram_gb else "N/A"
        lines.append(f"{r.name} ({r.cloud_instance})")
        lines.append(f"  VRAM: {vram}")
        lines.append(f"  On-Demand: {format_price(r.on_demand_hourly)}/hr")
        lines.append(f"  Clarifai: {format_price(r.clarifai_hourly)}/hr ({format_price(r.clarifai_annual)}/yr)")
        lines.append("")
    
    return "\n".join(lines)


def get_recommended_gpus_for_workload(
    workload_type: str,
    budget_annual: Optional[float] = None,
    min_vram: int = 16,
) -> List[Dict[str, Any]]:
    """Get GPU recommendations based on workload type."""
    
    recommendations = []
    
    # Get workload profile from config
    profile = WORKLOAD_PROFILES.get(workload_type, WORKLOAD_PROFILES.get("inference_light", {
        "min_vram": 16,
        "recommended": ["NVIDIA T4 16GB", "NVIDIA L4 24GB XL"],
        "description": "Light inference workloads, small models",
    }))
    
    effective_min_vram = max(min_vram, profile.get("min_vram", 16))
    
    for r in COMPUTE_RESOURCES:
        if r.resource_type != ResourceType.GPU:
            continue
        if r.vram_gb and r.vram_gb >= effective_min_vram:
            if budget_annual is None or r.clarifai_annual <= budget_annual:
                is_recommended = any(rec in r.name for rec in profile.get("recommended", []))
                recommendations.append({
                    "resource": r,
                    "is_recommended": is_recommended,
                    "annual_cost": r.clarifai_annual,
                    "monthly_cost": r.clarifai_annual / 12,
                    "hourly_cost": r.clarifai_hourly,
                })
    
    # Sort by recommendation status, then by cost
    recommendations.sort(key=lambda x: (not x["is_recommended"], x["annual_cost"]))
    
    return recommendations


def get_all_regions() -> List[str]:
    """Get list of all available regions."""
    return list(set(r.cloud_region for r in COMPUTE_RESOURCES))


def get_pricing_metadata() -> Dict[str, Any]:
    """Get metadata about the pricing data."""
    return _PRICING_DATA.get("_meta", {})
