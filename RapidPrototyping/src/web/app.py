"""
FastAPI Web Application for Clarifai Rapid Prototyping Framework.

Provides a web interface for:
- Uploading customer documents and files
- Managing project information
- Generating proposals focused on Compute Orchestration
- Dynamic industry question management
"""

import os
import json
import uuid
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel, Field

from src.config import get_config, init_config
from src.agents import ProposalAgent, DiscoveryAgent, SolutionAgent
from src.processors import DocumentProcessor, ImageProcessor
from src.web.industry_questions import IndustryQuestionManager
from src.web.pricing_data import (
    COMPUTE_RESOURCES, GPU_TIERS, RECOMMENDED_REGIONS,
    get_gpu_resources, get_resources_by_region, get_recommended_gpus_for_workload,
    generate_pricing_table, format_price, calculate_annual_savings,
    get_cheapest_gpu, get_best_value_gpu, ResourceType
)
from src.web.huggingface_models import (
    get_models_for_use_case, get_model_recommendations_for_project,
    generate_model_section_for_proposal, format_model_recommendations,
    get_all_vlm_models, get_all_llm_models, get_embedding_models,
    ModelTask, HuggingFaceModel, USE_CASE_TO_TASKS
)


logger = logging.getLogger(__name__)

# Initialize configuration
init_config()

app = FastAPI(
    title="Clarifai Rapid Prototyping Framework",
    description="AI-powered Solution Engineering assistant for Clarifai Compute Orchestration",
    version="1.0.0",
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
UPLOAD_DIR = Path("uploads")
PROJECTS_DIR = Path("projects")
UPLOAD_DIR.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)

# Industry question manager
question_manager = IndustryQuestionManager()


# ============== Pydantic Models ==============

class ProjectCreate(BaseModel):
    """Model for creating a new project."""
    customer_name: str
    project_name: str
    industry: str
    contact_email: Optional[str] = None
    goals: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    budget_range: Optional[str] = None
    timeline: Optional[str] = None
    compute_requirements: Optional[Dict[str, Any]] = None


class ProjectResponse(BaseModel):
    """Response model for project data."""
    id: str
    customer_name: str
    project_name: str
    industry: str
    status: str
    created_at: str
    files: List[str]
    outputs: List[str]


class GenerateRequest(BaseModel):
    """Request model for generation endpoints."""
    project_id: str
    generation_type: str  # proposal, discovery, solution, compute_analysis
    options: Dict[str, Any] = Field(default_factory=dict)


class IndustryQuestion(BaseModel):
    """Model for industry-specific questions."""
    question: str
    category: str
    importance: str = "medium"  # low, medium, high, critical
    follow_ups: List[str] = Field(default_factory=list)
    compute_relevant: bool = False


class AddIndustryQuestions(BaseModel):
    """Request to add new industry questions."""
    industry: str
    questions: List[IndustryQuestion]
    source: Optional[str] = None  # Where these questions came from


# ============== Project Storage ==============

class ProjectStore:
    """Simple file-based project storage."""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(exist_ok=True)
    
    def create(self, project: ProjectCreate) -> Dict[str, Any]:
        """Create a new project."""
        project_id = str(uuid.uuid4())[:8]
        project_dir = self.base_dir / project_id
        project_dir.mkdir(exist_ok=True)
        (project_dir / "uploads").mkdir(exist_ok=True)
        (project_dir / "outputs").mkdir(exist_ok=True)
        
        data = {
            "id": project_id,
            "customer_name": project.customer_name,
            "project_name": project.project_name,
            "industry": project.industry,
            "contact_email": project.contact_email,
            "goals": project.goals,
            "constraints": project.constraints,
            "budget_range": project.budget_range,
            "timeline": project.timeline,
            "compute_requirements": project.compute_requirements or {},
            "status": "created",
            "created_at": datetime.now().isoformat(),
            "files": [],
            "outputs": [],
        }
        
        self._save_metadata(project_id, data)
        return data
    
    def get(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project by ID."""
        meta_path = self.base_dir / project_id / "metadata.json"
        if not meta_path.exists():
            return None
        return json.loads(meta_path.read_text())
    
    def list_all(self) -> List[Dict[str, Any]]:
        """List all projects."""
        projects = []
        for project_dir in self.base_dir.iterdir():
            if project_dir.is_dir():
                data = self.get(project_dir.name)
                if data:
                    projects.append(data)
        return sorted(projects, key=lambda x: x["created_at"], reverse=True)
    
    def update(self, project_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update project metadata."""
        data = self.get(project_id)
        if not data:
            return None
        data.update(updates)
        self._save_metadata(project_id, data)
        return data
    
    def add_file(self, project_id: str, filename: str) -> bool:
        """Add a file to project."""
        data = self.get(project_id)
        if not data:
            return False
        if filename not in data["files"]:
            data["files"].append(filename)
            self._save_metadata(project_id, data)
        return True
    
    def add_output(self, project_id: str, filename: str) -> bool:
        """Add an output file to project."""
        data = self.get(project_id)
        if not data:
            return False
        if filename not in data["outputs"]:
            data["outputs"].append(filename)
            self._save_metadata(project_id, data)
        return True
    
    def _save_metadata(self, project_id: str, data: Dict[str, Any]):
        """Save project metadata."""
        meta_path = self.base_dir / project_id / "metadata.json"
        meta_path.write_text(json.dumps(data, indent=2))
    
    def delete(self, project_id: str) -> bool:
        """Delete a project and all its associated data."""
        project_dir = self.base_dir / project_id
        if not project_dir.exists():
            return False
        try:
            shutil.rmtree(project_dir)
            logger.info(f"Deleted project: {project_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting project {project_id}: {e}")
            return False


project_store = ProjectStore(PROJECTS_DIR)


# ============== API Endpoints ==============

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main web application."""
    return FileResponse("src/web/static/index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# ----- Project Management -----

@app.post("/api/projects", response_model=Dict[str, Any])
async def create_project(project: ProjectCreate):
    """Create a new customer project."""
    data = project_store.create(project)
    logger.info(f"Created project: {data['id']} for {project.customer_name}")
    return data


@app.get("/api/projects", response_model=List[Dict[str, Any]])
async def list_projects():
    """List all projects."""
    return project_store.list_all()


@app.get("/api/projects/{project_id}", response_model=Dict[str, Any])
async def get_project(project_id: str):
    """Get a specific project."""
    data = project_store.get(project_id)
    if not data:
        raise HTTPException(status_code=404, detail="Project not found")
    return data


@app.put("/api/projects/{project_id}", response_model=Dict[str, Any])
async def update_project(project_id: str, updates: Dict[str, Any]):
    """Update a project."""
    data = project_store.update(project_id, updates)
    if not data:
        raise HTTPException(status_code=404, detail="Project not found")
    return data


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and all associated files."""
    project = project_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    success = project_store.delete(project_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete project")
    
    return {
        "status": "deleted",
        "project_id": project_id,
        "message": f"Project '{project['project_name']}' and all associated data has been deleted."
    }


# ----- File Upload -----

@app.post("/api/projects/{project_id}/upload")
async def upload_file(
    project_id: str,
    file: UploadFile = File(...),
    file_type: str = Form(default="document")
):
    """Upload a file to a project."""
    project = project_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Save file
    upload_dir = PROJECTS_DIR / project_id / "uploads"
    file_path = upload_dir / file.filename
    
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    project_store.add_file(project_id, file.filename)
    
    # Process file if it's a document
    analysis = None
    if file_type == "document" and file.filename.endswith(('.md', '.txt', '.pdf', '.docx')):
        try:
            processor = DocumentProcessor()
            doc = processor.process(str(file_path), generate_summary=False)
            analysis = {
                "chunks": len(doc.chunks),
                "preview": doc.full_text[:500] + "..." if len(doc.full_text) > 500 else doc.full_text
            }
        except Exception as e:
            logger.error(f"Error processing document: {e}")
    
    return {
        "filename": file.filename,
        "file_type": file_type,
        "size": file_path.stat().st_size,
        "analysis": analysis,
    }


@app.get("/api/projects/{project_id}/files")
async def list_files(project_id: str):
    """List files in a project."""
    project = project_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    upload_dir = PROJECTS_DIR / project_id / "uploads"
    files = []
    for f in upload_dir.iterdir():
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
    return files


# ----- Generation Endpoints -----

@app.post("/api/generate/discovery")
async def generate_discovery(request: GenerateRequest, background_tasks: BackgroundTasks):
    """Generate discovery questions for a project."""
    project = project_store.get(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get industry-specific questions
    industry_questions = question_manager.get_questions(project["industry"])
    
    # Build context from uploaded files
    context = _build_project_context(project)
    
    agent = DiscoveryAgent()
    result = agent.generate_questions(
        customer_context=context,
        industry=project["industry"],
        existing_info={"goals": project["goals"], "compute_requirements": project.get("compute_requirements", {})},
    )
    
    # Save output
    output_filename = f"discovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    output_path = PROJECTS_DIR / request.project_id / "outputs" / output_filename
    
    # Add compute orchestration focus
    compute_section = _generate_compute_discovery_section(project)
    full_content = result.content + "\n\n" + compute_section
    
    # Add dynamic industry questions
    if industry_questions:
        full_content += "\n\n## Industry-Specific Questions (Dynamic)\n\n"
        for q in industry_questions:
            full_content += f"### {q['question']}\n"
            full_content += f"**Category:** {q['category']} | **Importance:** {q['importance']}\n"
            if q.get('follow_ups'):
                full_content += "**Follow-ups:**\n"
                for fu in q['follow_ups']:
                    full_content += f"- {fu}\n"
            full_content += "\n"
    
    output_path.write_text(full_content)
    project_store.add_output(request.project_id, output_filename)
    
    return {
        "content": full_content,
        "output_file": output_filename,
    }


@app.post("/api/generate/proposal")
async def generate_proposal(request: GenerateRequest):
    """Generate a proposal focused on Compute Orchestration."""
    project = project_store.get(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    context = _build_project_context(project)
    
    agent = ProposalAgent()
    result = agent.generate_proposal(
        customer_name=project["customer_name"],
        project_name=project["project_name"],
        goals=project["goals"],
        industry=project["industry"],
        constraints=project["constraints"],
        documents_summary=context,
    )
    
    # Enhance with Compute Orchestration focus
    compute_section = _generate_compute_proposal_section(project)
    roi_section = _generate_compute_roi_section(project)
    
    # Add trending open-source model recommendations
    model_recommendations = generate_model_section_for_proposal(
        project["goals"], 
        project["industry"]
    )
    
    full_content = result.content + "\n\n" + compute_section + "\n\n---\n\n## Open-Source Model Recommendations\n\n" + model_recommendations + "\n\n" + roi_section
    
    # Save output
    output_filename = f"proposal_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    output_path = PROJECTS_DIR / request.project_id / "outputs" / output_filename
    output_path.write_text(full_content)
    project_store.add_output(request.project_id, output_filename)
    
    return {
        "content": full_content,
        "output_file": output_filename,
    }


@app.post("/api/generate/compute-analysis")
async def generate_compute_analysis(request: GenerateRequest):
    """Generate a Compute Orchestration analysis and recommendation."""
    project = project_store.get(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    context = _build_project_context(project)
    compute_reqs = project.get("compute_requirements", {})
    
    agent = SolutionAgent()
    
    # Build compute-focused prompt
    compute_prompt = f"""
Analyze the following customer requirements and provide a comprehensive 
Clarifai Compute Orchestration recommendation.

Customer: {project['customer_name']}
Industry: {project['industry']}
Goals: {', '.join(project['goals'])}

Current Compute Requirements:
{json.dumps(compute_reqs, indent=2)}

Additional Context:
{context}

Focus on:
1. GPU requirements (type, quantity, utilization patterns)
2. Yearly reservation benefits vs on-demand pricing
3. ROI analysis for dedicated compute
4. Recommended Clarifai Compute tier
5. Scaling strategy and growth planning
6. Cost optimization opportunities
"""
    
    result = agent.design_architecture(
        requirements=compute_prompt,
        constraints=project["constraints"],
    )
    
    # Add specific compute orchestration content
    compute_content = _generate_detailed_compute_analysis(project, compute_reqs)
    
    full_content = f"""# Clarifai Compute Orchestration Analysis

**Customer:** {project['customer_name']}
**Date:** {datetime.now().strftime('%B %d, %Y')}

---

{compute_content}

---

## Technical Architecture Recommendation

{result.content}
"""
    
    # Save output
    output_filename = f"compute_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    output_path = PROJECTS_DIR / request.project_id / "outputs" / output_filename
    output_path.write_text(full_content)
    project_store.add_output(request.project_id, output_filename)
    
    return {
        "content": full_content,
        "output_file": output_filename,
    }


@app.post("/api/generate/se-guide")
async def generate_se_guide(request: GenerateRequest):
    """Generate a Solution Engineer step-by-step implementation guide."""
    project = project_store.get(request.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Build context including all generated outputs (proposals, discovery docs)
    context = _build_project_context(project, include_outputs=True)
    compute_reqs = project.get("compute_requirements", {})
    
    # Extract refined goals from proposal if available
    refined_goals = _extract_refined_goals_from_outputs(project)
    goals_for_recommendations = refined_goals if refined_goals else project["goals"]
    
    # Get model recommendations based on refined goals
    model_recs = get_model_recommendations_for_project(goals_for_recommendations, project["industry"])
    
    # Create an enhanced project dict with refined goals for the SE guide
    enhanced_project = project.copy()
    if refined_goals:
        enhanced_project["refined_goals"] = refined_goals
        enhanced_project["goals_source"] = "proposal"
    else:
        enhanced_project["goals_source"] = "initial"
    
    # Generate the SE guide content
    se_guide_content = _generate_se_implementation_guide(enhanced_project, compute_reqs, model_recs, context)
    
    # Save output
    output_filename = f"se_guide_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    output_path = PROJECTS_DIR / request.project_id / "outputs" / output_filename
    output_path.write_text(se_guide_content)
    project_store.add_output(request.project_id, output_filename)
    
    return {
        "content": se_guide_content,
        "output_file": output_filename,
    }


def _extract_refined_goals_from_outputs(project: Dict[str, Any]) -> List[str]:
    """Extract refined/specific goals from generated proposal outputs."""
    outputs_dir = PROJECTS_DIR / project["id"] / "outputs"
    if not outputs_dir.exists():
        return []
    
    refined_goals = []
    
    # Look for proposal files first (most likely to have refined goals)
    for f in sorted(outputs_dir.iterdir(), reverse=True):  # Most recent first
        if 'proposal' in f.name.lower() and f.suffix.lower() == '.md':
            try:
                content = f.read_text(encoding='utf-8')
                import re
                
                # Pattern 1: Extract from Executive Summary table - get full goal with context
                exec_table = re.search(r'\|\s*Goal\s*\|.*?\n\|[-|]+\|\n((?:\|.+\|\n?)+)', content, re.IGNORECASE)
                if exec_table:
                    rows = exec_table.group(1).strip().split('\n')
                    for row in rows:
                        cols = row.split('|')
                        if len(cols) >= 3:
                            goal = cols[1].strip()
                            how = cols[2].strip() if len(cols) > 2 else ""
                            # Remove markdown formatting
                            goal = re.sub(r'\*\*([^*]+)\*\*', r'\1', goal)
                            how = re.sub(r'\*\*([^*]+)\*\*', r'\1', how)
                            if goal and len(goal) > 15 and goal.lower() not in ['goal', '---']:
                                # Combine goal with implementation approach for richer context
                                full_goal = goal
                                if how and len(how) > 20:
                                    # Extract key approach
                                    full_goal = f"{goal} - Implementation: {how[:200]}"
                                refined_goals.append(full_goal)
                
                # Pattern 2: Extract VLM requirements with their advantages
                req_table = re.search(r'\|\s*Requirement\s*\|.*?(?:advantage|VLM).*?\n\|[-|]+\|\n((?:\|.+\|\n?)+)', content, re.IGNORECASE)
                if req_table:
                    rows = req_table.group(1).strip().split('\n')
                    for row in rows:
                        cols = row.split('|')
                        if len(cols) >= 3:
                            req = cols[1].strip()
                            advantage = cols[2].strip() if len(cols) > 2 else ""
                            req = re.sub(r'\*\*([^*]+)\*\*', r'\1', req)
                            advantage = re.sub(r'\*\*([^*]+)\*\*', r'\1', advantage)
                            advantage = re.sub(r'\*([^*]+)\*', r'\1', advantage)  # Remove italics too
                            if req and len(req) > 10 and req.lower() not in ['requirement', '---']:
                                # Include the capability description
                                if advantage and len(advantage) > 20:
                                    full_req = f"{req}: {advantage[:150]}"
                                else:
                                    full_req = req
                                if full_req not in refined_goals:
                                    refined_goals.append(full_req)
                
                # Pattern 3: Extract from Workflow/Prompt Design - get the actual prompt content
                layer_table = re.search(r'\|\s*Layer\s*\|.*?Prompt.*?\n\|[-|]+\|\n((?:\|.+\|\n?)+)', content, re.IGNORECASE)
                if layer_table:
                    rows = layer_table.group(1).strip().split('\n')
                    for row in rows:
                        cols = row.split('|')
                        if len(cols) >= 3:
                            layer = cols[1].strip()
                            prompt_desc = cols[2].strip() if len(cols) > 2 else ""
                            layer = re.sub(r'\*\*([^*]+)\*\*', r'\1', layer)
                            # Clean up the prompt description
                            prompt_desc = re.sub(r'["\']', '', prompt_desc)
                            if layer and len(layer) > 3 and layer.lower() not in ['layer', '---']:
                                if prompt_desc and len(prompt_desc) > 30:
                                    # Extract key checks from the prompt
                                    goal = f"{layer} Layer: {prompt_desc[:250]}"
                                else:
                                    goal = f"{layer} verification and quality assessment"
                                if goal not in refined_goals:
                                    refined_goals.append(goal)
                
                # Pattern 4: Extract deliverables with descriptions
                deliverable_table = re.search(r'\|\s*Deliverable\s*\|.*?\n\|[-|]+\|\n((?:\|.+\|\n?)+)', content, re.IGNORECASE)
                if deliverable_table:
                    rows = deliverable_table.group(1).strip().split('\n')
                    for row in rows[:5]:  # Top 5 deliverables
                        cols = row.split('|')
                        if len(cols) >= 3:
                            deliverable = cols[1].strip()
                            description = cols[2].strip() if len(cols) > 2 else ""
                            deliverable = re.sub(r'\*\*([^*]+)\*\*', r'\1', deliverable)
                            deliverable = re.sub(r'[0-9️⃣]+\s*', '', deliverable)  # Remove emoji numbers
                            if deliverable and len(deliverable) > 5 and deliverable.lower() not in ['deliverable', '---']:
                                if description and len(description) > 10:
                                    goal = f"Deliver: {deliverable} - {description[:100]}"
                                else:
                                    goal = f"Deliver: {deliverable}"
                                if goal not in refined_goals:
                                    refined_goals.append(goal)
                
                # Pattern 5: Extract success criteria and KPIs
                criteria_matches = re.findall(
                    r'(?:≥|>=|>)\s*(\d+)\s*%\s*([a-zA-Z\s]+?)(?:\s*[,;.|]|\s+(?:on|for|in))',
                    content
                )
                for pct, metric in criteria_matches[:3]:
                    metric = metric.strip()
                    if len(metric) > 3:
                        goal = f"Achieve ≥{pct}% {metric}"
                        if goal not in refined_goals:
                            refined_goals.append(goal)
                
                # Pattern 6: Extract from Problem Statement - pain points to address
                problem_section = re.search(
                    r'(?:##?\s*\d*\.?\s*Problem\s+Statement)(.*?)(?=##?\s*\d*\.?\s*(?:Proposed|Solution))',
                    content, re.IGNORECASE | re.DOTALL
                )
                if problem_section:
                    pain_table = re.search(r'\|\s*Area\s*\|.*?\n\|[-|]+\|\n((?:\|.+\|\n?)+)', problem_section.group(1))
                    if pain_table:
                        rows = pain_table.group(1).strip().split('\n')
                        for row in rows[:4]:
                            cols = row.split('|')
                            if len(cols) >= 3:
                                area = cols[1].strip()
                                pain = cols[2].strip()
                                area = re.sub(r'\*\*([^*]+)\*\*', r'\1', area)
                                if area and pain and len(pain) > 20 and area.lower() not in ['area', '---']:
                                    goal = f"Solve: {area} - {pain[:120]}"
                                    if goal not in refined_goals:
                                        refined_goals.append(goal)
                
                # Filter out goals that claim non-existent VLM capabilities
                # VLMs return text only - no heatmaps, attention maps, bounding boxes, or visual output
                false_capability_patterns = [
                    r'heat[\s-]?map',
                    r'attention[\s-]?map',
                    r'visual[\s-]?overlay',
                    r'bounding[\s-]?box',
                    r'segmentation[\s-]?mask',
                    r'localize.*visual',
                    r'draw.*on.*image',
                    r'annotate.*image',
                ]
                filtered_goals = []
                for goal in refined_goals:
                    goal_lower = goal.lower()
                    has_false_claim = False
                    for pattern in false_capability_patterns:
                        if re.search(pattern, goal_lower):
                            # Check if it's claiming VLM does this (vs. mentioning it as a separate need)
                            if any(vlm in goal_lower for vlm in ['vlm', 'mm-poly', 'vision-language', 'via built-in']):
                                has_false_claim = True
                                logger.warning(f"Filtered goal with false VLM capability claim: {goal[:80]}")
                                break
                    if not has_false_claim:
                        filtered_goals.append(goal)
                
                refined_goals = filtered_goals
                
                # If we found refined goals, return them
                if refined_goals:
                    logger.info(f"Extracted {len(refined_goals)} refined goals from {f.name}")
                    return refined_goals[:15]  # Allow up to 15 rich goals
                    
            except Exception as e:
                logger.error(f"Error extracting goals from {f}: {e}")
    
    return refined_goals


# ----- Industry Questions Management -----

@app.get("/api/industries")
async def list_industries():
    """List all industries with question counts."""
    return question_manager.list_industries()


@app.get("/api/industries/{industry}/questions")
async def get_industry_questions(industry: str):
    """Get questions for a specific industry."""
    return question_manager.get_questions(industry)


@app.post("/api/industries/{industry}/questions")
async def add_industry_questions(industry: str, request: AddIndustryQuestions):
    """Add new questions to an industry."""
    questions = [q.dict() for q in request.questions]
    question_manager.add_questions(industry, questions, request.source)
    return {"status": "success", "added": len(questions)}


@app.post("/api/industries/{industry}/questions/generate")
async def generate_industry_questions(industry: str, context: Dict[str, Any]):
    """Dynamically generate new industry questions based on provided context."""
    agent = DiscoveryAgent()
    
    prompt = f"""Based on the following customer context for the {industry} industry, 
generate 5-10 NEW discovery questions that are specific to their situation.

Focus on questions that help understand:
1. Their compute and GPU requirements
2. Yearly reservation potential
3. ROI opportunities
4. Technical integration needs

Customer Context:
{json.dumps(context, indent=2)}

Format each question with:
- The question itself
- Category (business, technical, compute, integration, budget)
- Importance (low, medium, high, critical)
- Whether it's relevant to compute orchestration (true/false)
- 1-2 follow-up questions

Return as a structured list.
"""
    
    result = agent.generate(prompt)
    
    # Parse and save new questions
    # In production, we'd parse the AI response more carefully
    new_questions = _parse_generated_questions(result.content, industry)
    
    if new_questions:
        question_manager.add_questions(industry, new_questions, "ai_generated")
    
    return {
        "generated_content": result.content,
        "questions_added": len(new_questions),
    }


@app.get("/api/outputs/{project_id}/{filename}")
async def get_output_file(project_id: str, filename: str):
    """Download a generated output file."""
    file_path = PROJECTS_DIR / project_id / "outputs" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)


# ============== Hugging Face Model Discovery API ==============

@app.get("/api/models/search")
async def search_models(
    use_case: str,
    max_results: int = 5,
):
    """
    Search for recommended open-source models based on use case.
    
    Args:
        use_case: Description of the use case (e.g., "visual understanding", "chatbot", "document analysis")
        max_results: Maximum number of models to return (default 5)
    """
    models = get_models_for_use_case(use_case, max_results)
    
    return {
        "use_case": use_case,
        "models": [
            {
                "model_id": m.model_id,
                "task": m.task,
                "parameters": m.parameters,
                "license": m.license,
                "downloads": m.downloads,
                "likes": m.likes,
                "tags": m.tags,
                "recommended_gpu": m.recommended_gpu,
                "huggingface_url": f"https://huggingface.co/{m.model_id}",
                "clarifai_search_url": m.clarifai_url,
            }
            for m in models
        ],
        "count": len(models),
    }


@app.get("/api/models/vlms")
async def get_vlm_models():
    """Get recommended Vision-Language Models (VLMs) for multi-modal tasks."""
    models = get_all_vlm_models()
    
    return {
        "task": "vision-language",
        "models": [
            {
                "model_id": m.model_id,
                "parameters": m.parameters,
                "license": m.license,
                "recommended_gpu": m.recommended_gpu,
                "huggingface_url": f"https://huggingface.co/{m.model_id}",
            }
            for m in models
        ],
    }


@app.get("/api/models/llms")
async def get_llm_models():
    """Get recommended Large Language Models (LLMs) for text generation."""
    models = get_all_llm_models()
    
    return {
        "task": "text-generation",
        "models": [
            {
                "model_id": m.model_id,
                "parameters": m.parameters,
                "license": m.license,
                "recommended_gpu": m.recommended_gpu,
                "huggingface_url": f"https://huggingface.co/{m.model_id}",
            }
            for m in models
        ],
    }


@app.get("/api/models/embeddings")
async def get_embedding_models_api():
    """Get recommended embedding models for RAG and search."""
    models = get_embedding_models()
    
    return {
        "task": "feature-extraction",
        "models": [
            {
                "model_id": m.model_id,
                "parameters": m.parameters,
                "license": m.license,
                "recommended_gpu": m.recommended_gpu,
                "huggingface_url": f"https://huggingface.co/{m.model_id}",
            }
            for m in models
        ],
    }


@app.get("/api/models/recommendations/{project_id}")
async def get_model_recommendations(project_id: str):
    """Get model recommendations for a specific project based on its goals."""
    project = project_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    recs = get_model_recommendations_for_project(project["goals"], project["industry"])
    
    return {
        "project_id": project_id,
        "goals": project["goals"],
        "industry": project["industry"],
        "recommendations": {
            "primary_models": [
                {
                    "model_id": m.model_id,
                    "task": m.task,
                    "parameters": m.parameters,
                    "license": m.license,
                    "recommended_gpu": m.recommended_gpu,
                    "huggingface_url": f"https://huggingface.co/{m.model_id}",
                }
                for m in recs["primary_models"]
            ],
            "embedding_models": [
                {
                    "model_id": m.model_id,
                    "parameters": m.parameters,
                    "recommended_gpu": m.recommended_gpu,
                    "huggingface_url": f"https://huggingface.co/{m.model_id}",
                }
                for m in recs["embedding_models"]
            ],
            "alternative_models": [
                {
                    "model_id": m.model_id,
                    "parameters": m.parameters,
                    "license": m.license,
                    "recommended_gpu": m.recommended_gpu,
                }
                for m in recs["alternative_models"]
            ],
            "gpu_summary": recs["gpu_summary"],
        },
    }


@app.get("/api/models/tasks")
async def list_model_tasks():
    """List all supported model tasks and their descriptions."""
    return {
        "tasks": {
            "text-generation": "Text generation and chat (LLMs)",
            "image-text-to-text": "Vision-language models (VLMs)",
            "image-classification": "Image classification",
            "object-detection": "Object detection in images",
            "image-segmentation": "Image segmentation (SAM, etc.)",
            "feature-extraction": "Embeddings for RAG/search",
            "automatic-speech-recognition": "Speech to text (Whisper)",
            "text-to-image": "Image generation (SDXL, FLUX)",
            "visual-question-answering": "VQA tasks",
        },
        "use_case_keywords": list(USE_CASE_TO_TASKS.keys()),
    }


# ============== Pricing API Endpoints ==============

@app.get("/api/pricing/gpus")
async def get_gpu_pricing(
    region: Optional[str] = None,
    min_vram: Optional[int] = None,
    max_vram: Optional[int] = None,
):
    """Get GPU pricing data with optional filters."""
    resources = [r for r in COMPUTE_RESOURCES if r.resource_type == ResourceType.GPU]
    
    if region:
        resources = [r for r in resources if r.cloud_region == region]
    
    if min_vram:
        resources = [r for r in resources if r.vram_gb and r.vram_gb >= min_vram]
    
    if max_vram:
        resources = [r for r in resources if r.vram_gb and r.vram_gb <= max_vram]
    
    return {
        "gpus": [
            {
                "name": r.name,
                "cloud_region": r.cloud_region,
                "cloud_instance": r.cloud_instance,
                "vram_gb": r.vram_gb,
                "on_demand_hourly": r.on_demand_hourly,
                "on_demand_annual": r.on_demand_annual,
                "clarifai_hourly": r.clarifai_hourly,
                "clarifai_annual": r.clarifai_annual,
            }
            for r in resources
        ],
        "count": len(resources),
    }


@app.get("/api/pricing/cpus")
async def get_cpu_pricing(region: Optional[str] = None):
    """Get CPU pricing data with optional filters."""
    resources = [r for r in COMPUTE_RESOURCES if r.resource_type == ResourceType.CPU]
    
    if region:
        resources = [r for r in resources if r.cloud_region == region]
    
    return {
        "cpus": [
            {
                "name": r.name,
                "cloud_region": r.cloud_region,
                "cloud_instance": r.cloud_instance,
                "on_demand_hourly": r.on_demand_hourly,
                "on_demand_annual": r.on_demand_annual,
                "clarifai_hourly": r.clarifai_hourly,
                "clarifai_annual": r.clarifai_annual,
            }
            for r in resources
        ],
        "count": len(resources),
    }


@app.get("/api/pricing/regions")
async def get_available_regions():
    """Get list of available regions with resource counts."""
    regions = {}
    for r in COMPUTE_RESOURCES:
        if r.cloud_region not in regions:
            regions[r.cloud_region] = {"gpus": 0, "cpus": 0}
        if r.resource_type == ResourceType.GPU:
            regions[r.cloud_region]["gpus"] += 1
        else:
            regions[r.cloud_region]["cpus"] += 1
    
    return {
        "regions": [
            {"region": k, "gpu_count": v["gpus"], "cpu_count": v["cpus"]}
            for k, v in regions.items()
        ]
    }


@app.get("/api/pricing/tiers")
async def get_gpu_tiers():
    """Get GPU tier information for quick reference."""
    return {"tiers": GPU_TIERS}


@app.get("/api/pricing/recommendations")
async def get_pricing_recommendations(
    workload: str = "inference_light",
    budget_annual: Optional[float] = None,
    min_vram: int = 16,
):
    """Get GPU recommendations based on workload type."""
    recommendations = get_recommended_gpus_for_workload(
        workload_type=workload,
        budget_annual=budget_annual,
        min_vram=min_vram,
    )
    
    return {
        "workload": workload,
        "recommendations": [
            {
                "name": r["resource"].name,
                "cloud_region": r["resource"].cloud_region,
                "vram_gb": r["resource"].vram_gb,
                "is_recommended": r["is_recommended"],
                "hourly_cost": r["hourly_cost"],
                "monthly_cost": r["monthly_cost"],
                "annual_cost": r["annual_cost"],
            }
            for r in recommendations[:10]  # Limit results
        ],
    }


@app.get("/api/pricing/compare")
async def compare_pricing(gpu_name: str):
    """Compare pricing for a specific GPU across all regions."""
    resources = [r for r in COMPUTE_RESOURCES if gpu_name.lower() in r.name.lower()]
    
    if not resources:
        raise HTTPException(status_code=404, detail="GPU not found")
    
    return {
        "gpu_name": gpu_name,
        "comparisons": [
            {
                "name": r.name,
                "cloud_region": r.cloud_region,
                "cloud_instance": r.cloud_instance,
                "vram_gb": r.vram_gb,
                "on_demand_hourly": r.on_demand_hourly,
                "on_demand_annual": r.on_demand_annual,
                "clarifai_hourly": r.clarifai_hourly,
                "clarifai_annual": r.clarifai_annual,
                "one_yr_upfront_annual": r.one_yr_upfront_annual,
                "one_yr_upfront_discount": f"{r.one_yr_upfront_discount*100:.1f}%" if r.one_yr_upfront_discount else None,
            }
            for r in resources
        ],
    }


# ============== Helper Functions ==============

def _build_project_context(project: Dict[str, Any], include_outputs: bool = True) -> str:
    """Build context string from project data, uploaded files, and generated outputs."""
    parts = [
        f"Customer: {project['customer_name']}",
        f"Project: {project['project_name']}",
        f"Industry: {project['industry']}",
        f"Initial Goals: {', '.join(project['goals'])}",
    ]
    
    if project.get("constraints"):
        parts.append(f"Constraints: {', '.join(project['constraints'])}")
    
    if project.get("budget_range"):
        parts.append(f"Budget: {project['budget_range']}")
    
    if project.get("timeline"):
        parts.append(f"Timeline: {project['timeline']}")
    
    if project.get("compute_requirements"):
        parts.append(f"Compute Requirements: {json.dumps(project['compute_requirements'])}")
    
    # Add content from uploaded files
    upload_dir = PROJECTS_DIR / project["id"] / "uploads"
    if upload_dir.exists():
        processor = DocumentProcessor()
        supported_extensions = ['.md', '.txt', '.pdf', '.docx']
        
        for f in upload_dir.iterdir():
            if f.suffix.lower() in supported_extensions:
                try:
                    doc = processor.process(str(f))
                    # Include more content from uploaded docs (up to 8000 chars per file)
                    # gpt-oss-120b supports large input token counts
                    content_preview = doc.full_text[:8000]
                    if len(doc.full_text) > 8000:
                        content_preview += f"\n... [truncated, {len(doc.full_text)} total chars]"
                    parts.append(f"\n--- Content from {f.name} ---\n{content_preview}")
                    logger.info(f"Included {len(doc.full_text)} chars from {f.name} in context")
                except Exception as e:
                    logger.error(f"Error reading {f}: {e}")
    
    # Add content from generated outputs (proposals, discovery docs, etc.)
    if include_outputs:
        outputs_dir = PROJECTS_DIR / project["id"] / "outputs"
        if outputs_dir.exists():
            # Prioritize proposal outputs as they contain refined understanding
            output_files = sorted(outputs_dir.iterdir(), key=lambda f: (
                0 if 'proposal' in f.name.lower() else
                1 if 'discovery' in f.name.lower() else
                2 if 'compute' in f.name.lower() else 3
            ))
            
            for f in output_files:
                if f.suffix.lower() == '.md':
                    try:
                        content = f.read_text()
                        # Include substantial content from outputs (up to 10000 chars)
                        content_preview = content[:10000]
                        if len(content) > 10000:
                            content_preview += f"\n... [truncated, {len(content)} total chars]"
                        parts.append(f"\n--- Generated Output: {f.name} ---\n{content_preview}")
                        logger.info(f"Included {len(content)} chars from output {f.name} in context")
                    except Exception as e:
                        logger.error(f"Error reading output {f}: {e}")
    
    return "\n".join(parts)


def _generate_compute_discovery_section(project: Dict[str, Any]) -> str:
    """Generate compute-focused discovery questions section."""
    return """
---

## Clarifai Compute Orchestration Discovery

### Model Selection Discovery

**1. Can a Vision-Language Model (VLM) solve this?**
- Can you describe what a human would look for when evaluating these images?
- Is this something a knowledgeable person could assess without specialized training?
- Do you need the AI to explain WHY it made a decision?

**2. What are your latency and throughput requirements?**
- What response time is acceptable? (1-5 sec = VLMs work great, <100ms = may need optimization)
- How many images/documents per second at peak?
- Is batch processing acceptable or must it be real-time?

**3. How often do your requirements change?**
- Will the rules/criteria for evaluation evolve over time?
- How quickly do you need to adapt to new requirements?
- (Frequent changes favor VLMs - update via prompts, no retraining)

**4. What accuracy is required?**
- What false positive/negative rates are acceptable?
- Is 90-95% accuracy sufficient, or do you need 99%+?
- How will edge cases be handled?

### GPU & Infrastructure Requirements

**5. What is your current GPU infrastructure?**
- Do you have existing GPU resources (on-prem or cloud)?
- What GPU types are you currently using?
- What is your current monthly GPU spend?

**6. What are your compute workload patterns?**
- Is your workload consistent or variable?
- What are your peak usage times?
- How predictable is your demand?

**7. What performance requirements do you have?**
- Required inference latency (ms)?
- Throughput requirements (predictions/second)?
- Availability requirements (uptime SLA)?

### Yearly Reservation Opportunity

**8. What is your expected usage over the next 12-24 months?**
- Growth projections for AI workloads?
- New use cases planned?
- Scaling timeline?

**9. Budget planning cycle?**
- Annual budget allocation process?
- Ability to commit to yearly reservations?
- CapEx vs OpEx preferences?

**10. Current pain points with compute?**
- Cost unpredictability?
- Availability issues?
- Management overhead?
"""


def _generate_compute_proposal_section(project: Dict[str, Any]) -> str:
    """Generate compute orchestration section for proposals with real pricing."""
    
    # Get specific GPU examples from pricing data
    t4 = next((r for r in COMPUTE_RESOURCES if "T4 16GB" in r.name and r.cloud_region == "aws-us-east-1"), None)
    l4 = next((r for r in COMPUTE_RESOURCES if "L4 24GB XL" in r.name and r.cloud_region == "aws-us-east-1"), None)
    l40s = next((r for r in COMPUTE_RESOURCES if "L40S 48GB XL" in r.name and r.cloud_region == "aws-us-east-1"), None)
    a100 = next((r for r in COMPUTE_RESOURCES if r.name == "NVIDIA A100 80GB XL" and r.cloud_region == "gcp-us-east-4"), None)
    h100 = next((r for r in COMPUTE_RESOURCES if r.name == "NVIDIA H100 80GB XL" and r.cloud_region == "clarifai"), None)
    h100_8x = next((r for r in COMPUTE_RESOURCES if r.name == "8x NVIDIA H100 80GB XL" and r.cloud_region == "clarifai"), None)
    
    # Build dynamic pricing table
    gpu_rows = []
    if t4:
        gpu_rows.append(f"| NVIDIA T4 16GB | Inference, Dev/Test | ${t4.clarifai_hourly:.4f} | ${t4.clarifai_annual:,.0f} |")
    if l4:
        gpu_rows.append(f"| NVIDIA L4 24GB | Production Inference | ${l4.clarifai_hourly:.4f} | ${l4.clarifai_annual:,.0f} |")
    if l40s:
        gpu_rows.append(f"| NVIDIA L40S 48GB | Training, LLM Inference | ${l40s.clarifai_hourly:.4f} | ${l40s.clarifai_annual:,.0f} |")
    if a100:
        gpu_rows.append(f"| NVIDIA A100 80GB | Large Model Training | ${a100.clarifai_hourly:.4f} | ${a100.clarifai_annual:,.0f} |")
    if h100:
        gpu_rows.append(f"| NVIDIA H100 80GB | Enterprise AI | ${h100.clarifai_hourly:.4f} | ${h100.clarifai_annual:,.0f} |")
    if h100_8x:
        gpu_rows.append(f"| 8x NVIDIA H100 | Distributed Training | ${h100_8x.clarifai_hourly:.2f} | ${h100_8x.clarifai_annual:,.0f} |")
    
    gpu_table = "\n".join(gpu_rows)
    
    return f"""
---

## Clarifai Platform Capabilities

Full documentation: https://docs.clarifai.com/

### Key Platform Features

| Capability | Description | Documentation |
|------------|-------------|---------------|
| **Model Library** | 1000+ pre-built models (VLMs, LLMs, CV, Audio) | [clarifai.com/explore](https://clarifai.com/explore) |
| **Workflows** | Chain multiple models in pipelines | [docs.clarifai.com/create/workflows](https://docs.clarifai.com/create/workflows/) |
| **AI Agents** | Autonomous agents with tool calling | [docs.clarifai.com/compute/agents](https://docs.clarifai.com/compute/agents/) |
| **Vector Search** | Semantic search for RAG applications | [docs.clarifai.com/create/search](https://docs.clarifai.com/create/search/) |
| **Pipelines** | Async, long-running MLOps workflows | [docs.clarifai.com/compute/pipelines](https://docs.clarifai.com/compute/pipelines/) |
| **Compute Orchestration** | Deploy anywhere with auto-scaling | [docs.clarifai.com/compute/overview](https://docs.clarifai.com/compute/overview) |
---

## Model Selection Strategy

### Vision-Language Models (VLMs) vs Legacy CV Models

Modern vision-language models significantly outperform traditional computer vision models for most enterprise use cases. We recommend VLMs as the default approach:

| Capability | Vision-Language Models (VLMs) | Legacy CV Models |
|------------|------------------------------|------------------|
| **Understanding** | Comprehends image context and meaning | Pattern matching only |
| **Reasoning** | Can explain WHY something was detected | Binary yes/no output |
| **Flexibility** | Adapt via natural language prompts | Requires retraining |
| **Edge Cases** | Handles novel situations naturally | Fails on unseen patterns |
| **Deployment** | Days (no training needed) | Weeks to months |
| **Maintenance** | Update prompts as needed | Retrain for any change |

### Recommended Models

| Use Case | Recommended Model | Parameters | GPU Tier |
|----------|------------------|------------|----------|
| **Visual Understanding** | mm-poly-8b *(Clarifai)* | 8B | Standard (24GB) |
| **Document Analysis** | Llama 3.2 Vision | 11B | Standard (24GB) |
| **Complex Reasoning** | Qwen2-VL | 7-72B | Standard to Enterprise |
| **Cost-Sensitive** | Phi-3 Vision | 4.2B | Entry (16GB) |
| **High Accuracy** | LLaVA 1.6 | 7-34B | Standard to Performance |

### Model Size → GPU Requirements

When selecting a model, the parameter count determines the minimum GPU VRAM needed:

| Model Size | VRAM (FP16) | VRAM (INT8) | Recommended GPU Tier | Example Models |
|------------|-------------|-------------|---------------------|----------------|
| **1-3B** | 6-8 GB | 3-4 GB | Entry (16GB) | Small VLMs, embedders |
| **7-8B** | 14-16 GB | 7-8 GB | Entry (16GB) or Standard (24GB) | Llama 3.1 8B, Mistral 7B |
| **13-14B** | 26-28 GB | 13-14 GB | Standard (24GB) or Performance (48GB) | Llama 2 13B |
| **30-34B** | 60-70 GB | 30-35 GB | Performance (48GB) or Enterprise (80GB) | CodeLlama 34B |
| **70B** | 140 GB | 70 GB | Enterprise (80GB) or Multi-GPU | Llama 3.1 70B |
| **100B+** | 200+ GB | 100+ GB | Multi-GPU (2-8x H100) | Large proprietary models |

**Notes:**
- FP16 (half precision) is standard for quality inference
- INT8 quantization reduces VRAM ~50% with minimal quality loss
- Add 20-30% overhead for KV cache during inference
- Clarifai's GPU fractioning allows multiple smaller models on one GPU

### Model Evaluation Phase (Recommended)

Before finalizing the architecture, we recommend a **2-week Model Evaluation Phase**:

1. **Curate Evaluation Dataset** (100-500 representative samples)
2. **Benchmark VLMs**:
   - Start with Clarifai's mm-poly-8b for vision tasks
   - Test 2-3 alternative VLMs for comparison
   - Evaluate accuracy, latency, and cost tradeoffs
3. **Measure Key Metrics**:
   - Accuracy on your specific use cases
   - Latency per request
   - Cost per 1,000 predictions
4. **Document Results** and select best model per use case
5. **Only consider custom training** if VLMs cannot meet requirements

### When Custom Training May Be Needed

Custom model training should only be considered when:
- VLMs cannot achieve required accuracy after prompt optimization
- Latency requirements are <20ms per prediction
- Throughput requirements exceed 500 images/second
- Offline/edge deployment is mandatory
- Cost optimization at massive scale (after validation)

---

## GPU Reservation Recommendation

Clarifai Compute Orchestration handles all infrastructure. You simply reserve the GPU capacity you need.

### Compute Orchestration Benefits (https://docs.clarifai.com/compute/overview)

- **Auto-scaling**: Scale from zero to infinity based on demand
- **GPU Fractioning**: Run multiple models per GPU for efficiency
- **Model Packing**: Up to 3.7x compute efficiency
- **Cost Savings**: 60-90% savings possible vs. raw cloud GPUs
- **Zero Management**: Clarifai handles all infrastructure

### Estimated GPU Requirements

Based on your project scope, we recommend:

| Phase | GPUs | Tier | Monthly Cost | Use Case |
|-------|------|------|--------------|----------|
| Pilot | 1-2 | Standard (24GB) | ~$750-1,500 | Initial development and testing |
| Production | 2-4 | Standard/Performance | ~$1,500-5,000 | Production inference workloads |
| Scale | 4+ | Performance (48GB) | ~$5,000+ | High-volume production |

### GPU Tier Guide

| Tier | Annual Cost | Best For |
|------|-------------|----------|
| Entry (16GB) | ~$5,000-6,000 | Development, testing, light inference |
| Standard (24GB) | ~$8,000-13,000 | Production inference |
| Performance (48GB) | ~$18,000-25,000 | LLM inference, high throughput |
| Enterprise (80GB+) | ~$21,000-65,000 | Large models, enterprise scale |

### What You Get

- **Guaranteed GPU availability** - No capacity concerns
- **Predictable annual costs** - Fixed pricing for budgeting
- **Zero infrastructure management** - Clarifai handles everything
- **Dedicated support** - Solution Engineering assistance

---

## Integration Approach

### Clarifai API (https://docs.clarifai.com/compute/inference/)

Integration is straightforward using Clarifai's managed API:

```python
from clarifai.client import Model

# Select a model from clarifai.com/explore
model = Model(url="https://clarifai.com/user/app/models/model-id")

# Make predictions
response = model.predict(inputs=[your_data])
```

### OpenAI-Compatible Endpoint

Use existing OpenAI code with Clarifai models:

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.clarifai.com/v2/ext/openai/v1",
    api_key="your_clarifai_pat"
)

response = client.chat.completions.create(
    model="clarifai/model-url",
    messages=[{{"role": "user", "content": "Your prompt"}}]
)
```

### Available SDKs

| SDK | Installation | Best For |
|-----|--------------|----------|
| Python | `pip install clarifai` | Backend services, data pipelines |
| Node.js | `npm install clarifai` | Web applications, serverless |
| OpenAI-compatible | Base URL: `https://api.clarifai.com/v2/ext/openai/v1` | Easy migration |
| LiteLLM | See [docs](https://docs.clarifai.com/compute/inference/litellm) | Multi-provider abstraction |
| Vercel AI SDK | See [docs](https://docs.clarifai.com/compute/inference/vercel) | Next.js applications |
| REST API | Direct HTTP calls | Any language/platform |

### Authentication

1. Create a PAT (Personal Access Token) at clarifai.com
2. Set environment variable: `export CLARIFAI_PAT=your_token`
3. Start making API calls

**No custom services or infrastructure required.**
"""


def _generate_compute_roi_section(project: Dict[str, Any]) -> str:
    """Generate simplified next steps section."""
    
    return """
---

## Next Steps

### 1. Model Evaluation (Week 1-2)
- Test VLMs (starting with mm-poly-8b) against your sample data
- Benchmark accuracy, latency, and cost
- Select best model(s) for your use cases

### 2. Integration Development (Week 2-4)
- Integrate Clarifai SDK into your application ([docs](https://docs.clarifai.com/compute/inference/))
- Implement API calls for each use case
- Set up error handling and monitoring
- Consider [Workflows](https://docs.clarifai.com/create/workflows/) for multi-model pipelines
- Use [Vector Search](https://docs.clarifai.com/create/search/) for RAG applications

### 3. GPU Reservation
- Based on evaluation, determine GPU requirements
- Reserve appropriate capacity through Clarifai
- Leverage [Compute Orchestration](https://docs.clarifai.com/compute/overview) benefits

### 4. Production Deployment
- Deploy integrated application
- Monitor performance and adjust as needed
- Scale GPU reservation as usage grows

### Resources

| Resource | Link |
|----------|------|
| **API Documentation** | https://docs.clarifai.com/ |
| **Model Library** | https://clarifai.com/explore |
| **Inference Docs** | https://docs.clarifai.com/compute/inference/ |
| **Workflows** | https://docs.clarifai.com/create/workflows/ |
| **AI Agents** | https://docs.clarifai.com/compute/agents/ |
| **Vector Search** | https://docs.clarifai.com/create/search/ |
| **Compute Orchestration** | https://docs.clarifai.com/compute/overview |
| **Python SDK** | `pip install clarifai` |

---

*Clarifai manages all compute infrastructure. You focus on building your application.*
"""


def _generate_detailed_compute_analysis(project: Dict[str, Any], compute_reqs: Dict[str, Any]) -> str:
    """Generate simplified compute analysis focused on GPU reservation."""
    
    # Get pricing for recommendations
    l4 = next((r for r in COMPUTE_RESOURCES if "L4 24GB XL" in r.name and r.cloud_region == "aws-us-east-1"), None)
    l40s = next((r for r in COMPUTE_RESOURCES if "L40S 48GB XL" in r.name and r.cloud_region == "aws-us-east-1"), None)
    
    # Calculate phased costs
    phase1_monthly = l4.clarifai_annual / 12 * 2 if l4 else 1500
    phase2_monthly = l40s.clarifai_annual / 12 * 2 if l40s else 3400
    phase3_monthly = l40s.clarifai_annual / 12 * 4 if l40s else 6800
    
    total_year1 = (phase1_monthly * 3) + (phase2_monthly * 3) + (phase3_monthly * 6)
    
    # Get model recommendations based on project goals
    model_section = generate_model_section_for_proposal(project["goals"], project["industry"])
    
    return f"""
## Executive Summary

This analysis provides GPU reservation recommendations for {project['customer_name']}. 
Clarifai Compute Orchestration handles all infrastructure - you simply reserve the capacity you need.

**Full Documentation:** https://docs.clarifai.com/

## Your Requirements

{json.dumps(compute_reqs, indent=2) if compute_reqs else "To be determined during discovery"}

**Project Goals:** {', '.join(project['goals']) if project['goals'] else 'To be defined'}

---

## Trending Open-Source Models (From Hugging Face)

Based on your project goals, here are recommended open-source models available on Clarifai:

{model_section}

## Clarifai Platform Capabilities

| Capability | Use For | Documentation |
|------------|---------|---------------|
| **Model Library** | Pre-built VLMs, LLMs, CV models | [clarifai.com/explore](https://clarifai.com/explore) |
| **Workflows** | Multi-model pipelines | [docs.clarifai.com/create/workflows](https://docs.clarifai.com/create/workflows/) |
| **AI Agents** | Autonomous multi-step tasks | [docs.clarifai.com/compute/agents](https://docs.clarifai.com/compute/agents/) |
| **Vector Search** | RAG, semantic search | [docs.clarifai.com/create/search](https://docs.clarifai.com/create/search/) |
| **Pipelines** | Async MLOps workflows | [docs.clarifai.com/compute/pipelines](https://docs.clarifai.com/compute/pipelines/) |

## Recommended Approach

### 1. Start with Model Evaluation

Before reserving GPUs, evaluate Vision-Language Models (VLMs) against your data:
- Start with Clarifai's mm-poly-8b for vision tasks
- Test 2-3 alternative models for comparison
- Measure accuracy on your specific use cases

### Model Size → GPU Selection

Choose your GPU tier based on the model size you need:

| Model Size | VRAM (FP16) | VRAM (INT8) | Recommended GPU | Examples |
|------------|-------------|-------------|-----------------|----------|
| 1-3B | 6-8 GB | 3-4 GB | T4 16GB | Small VLMs, embedders |
| 7-8B | 14-16 GB | 7-8 GB | T4/L4 16-24GB | Llama 3.1 8B, Mistral 7B |
| 13-14B | 26-28 GB | 13-14 GB | L4/L40S 24-48GB | Llama 2 13B |
| 30-34B | 60-70 GB | 30-35 GB | L40S/A100 48-80GB | CodeLlama 34B |
| 70B | 140 GB | 70 GB | A100 80GB or Multi-GPU | Llama 3.1 70B |
| 100B+ | 200+ GB | 100+ GB | Multi-GPU (2-8x H100) | Large models |

**Tip:** Use INT8 quantization to reduce VRAM ~50% with minimal quality loss.

### 2. Integrate via Clarifai API

Use Clarifai's managed API - no custom infrastructure needed:

```python
from clarifai.client import Model

model = Model(url="https://clarifai.com/user/app/models/model-id")
response = model.predict(inputs=[your_data])
```

**Documentation:** https://docs.clarifai.com/compute/inference/

**SDK Options:**
- Python: `pip install clarifai` (recommended)
- Node.js: `npm install clarifai`
- OpenAI-compatible: `https://api.clarifai.com/v2/ext/openai/v1`
- LiteLLM, Vercel AI SDK also supported

### 3. Reserve GPU Capacity

Based on your workload, reserve appropriate capacity:

| Phase | GPUs | Tier | Monthly Cost |
|-------|------|------|--------------|
| Pilot (Months 1-3) | 1-2 | Standard (24GB) | ~${phase1_monthly:,.0f} |
| Production (Months 4-6) | 2-3 | Standard/Performance | ~${phase2_monthly:,.0f} |
| Scale (Months 7-12) | 3-4+ | Performance (48GB) | ~${phase3_monthly:,.0f} |

**Estimated Year 1 Investment:** ~${total_year1:,.0f}

## GPU Tier Reference

| Tier | VRAM | Annual Cost | Best For |
|------|------|-------------|----------|
| Entry | 16GB | ~$5,000-6,000 | Development, testing |
| Standard | 24GB | ~$8,000-13,000 | Production inference |
| Performance | 48GB | ~$18,000-25,000 | LLM inference, high throughput |
| Enterprise | 80GB+ | ~$21,000-65,000 | Large models, enterprise scale |

## Compute Orchestration Benefits

([Full details](https://docs.clarifai.com/compute/overview))

- **Auto-scaling**: Scale from zero to infinity based on demand
- **GPU Fractioning**: Run multiple models per GPU
- **Model Packing**: Up to 3.7x compute efficiency
- **Cost Savings**: 60-90% savings vs. raw cloud GPUs

## What Clarifai Handles

- ✅ GPU provisioning and management
- ✅ Infrastructure scaling (auto-scale to zero)
- ✅ Model hosting and serving
- ✅ API availability and uptime
- ✅ Security and compliance
- ✅ Updates and maintenance

## What You Do

- ✅ Select models from Clarifai's library
- ✅ Integrate SDK/API into your application
- ✅ Reserve GPU capacity based on needs
- ✅ Monitor usage and adjust as needed

## Next Steps

1. **Model Evaluation** - Test VLMs on your data (start with mm-poly-8b)
2. **Integration** - Use Clarifai SDK (Python, Node.js, or REST)
3. **GPU Reservation** - Reserve capacity based on evaluation results
4. **Go Live** - Deploy and scale as needed

**Resources:**
| Resource | Link |
|----------|------|
| API Docs | https://docs.clarifai.com/ |
| Model Library | https://clarifai.com/explore |
| Inference | https://docs.clarifai.com/compute/inference/ |
| Workflows | https://docs.clarifai.com/create/workflows/ |
| Compute Orchestration | https://docs.clarifai.com/compute/overview |
"""


def _generate_se_implementation_guide(project: Dict[str, Any], compute_reqs: Dict[str, Any], model_recs: Dict[str, Any], context: str) -> str:
    """Generate a comprehensive SE implementation guide with step-by-step instructions."""
    
    # Get primary model recommendation
    primary_model = model_recs.get("primary_models", [{}])[0] if model_recs.get("primary_models") else {}
    primary_model_name = primary_model.model_id.split("/")[-1] if hasattr(primary_model, 'model_id') else "mm-poly-8b"
    
    # Determine GPU tier based on compute requirements or defaults
    gpu_type = compute_reqs.get("gpu_type", "L4")
    gpu_count = compute_reqs.get("gpu_count", 2)
    
    # Use refined goals from proposal if available, otherwise fall back to initial goals
    goals_to_use = project.get('refined_goals', project['goals'])
    goals_source = project.get('goals_source', 'initial')
    
    # Build goals section with source indication
    if goals_source == 'proposal' and project.get('refined_goals'):
        goals_section = f"""**Refined Project Goals** *(extracted from proposal)*:
{chr(10).join(f"- {goal}" for goal in goals_to_use)}

**Original Goals:**
{chr(10).join(f"- {goal}" for goal in project['goals'])}"""
    else:
        goals_section = f"""**Project Goals:**
{chr(10).join(f"- {goal}" for goal in goals_to_use) if goals_to_use else "- To be defined during discovery"}"""

    return f"""# Solution Engineer Implementation Guide

**Customer:** {project['customer_name']}
**Project:** {project['project_name']}
**Industry:** {project['industry']}
**Generated:** {datetime.now().strftime('%B %d, %Y')}

---

## Overview

This guide provides step-by-step instructions for implementing the {project['project_name']} solution for {project['customer_name']}. Follow each phase in order, checking off tasks as you complete them.

{goals_section}

---

## Phase 1: Discovery & Requirements (Week 1)

### 1.1 Schedule Kickoff Call

**Objective:** Align on project scope, timeline, and success criteria.

**Agenda Template:**
```
1. Introductions (5 min)
2. Project goals review (10 min)
3. Technical requirements deep-dive (20 min)
4. Data & integration discussion (15 min)
5. Timeline & milestones (10 min)
6. Q&A and next steps (10 min)
```

**Key Questions to Ask:**
- "Can you walk me through a typical workflow that this AI will support?"
- "What does success look like in 3 months? 6 months?"
- "Who are the end users and what's their technical comfort level?"
- "What existing systems need to integrate with this solution?"

### 1.2 Gather Sample Data

**Objective:** Collect representative samples for model evaluation.

**Checklist:**
- [ ] Request 100-500 sample images/documents
- [ ] Get examples of "good" and "bad" cases
- [ ] Understand edge cases and exceptions
- [ ] Document labeling/annotation requirements

**Sample Request Email:**
```
Subject: Sample Data Request for {project['project_name']} POC

Hi [Customer Contact],

To begin our model evaluation, we need representative samples of your data. 
Could you provide:

1. 100-500 typical examples (images/documents)
2. Examples of edge cases or difficult scenarios
3. Any existing labels or annotations
4. Sample of expected output format

We'll use these to benchmark models and ensure accuracy 
meets your requirements.

Best regards,
[Your Name]
```

### 1.3 Document Technical Requirements

**Template to Complete:**

| Requirement | Customer Response | Notes |
|-------------|------------------|-------|
| Throughput (requests/sec) | | |
| Latency requirement | | |
| Accuracy threshold | | |
| Data format (image/doc/video) | | |
| Output format needed | | |
| Integration points | | |
| Security/compliance needs | | |

---

## Phase 2: Model Evaluation (Week 2)

### 2.1 Set Up Evaluation Environment

**Objective:** Prepare Clarifai environment for testing.

**Step 1: Create Clarifai App**
```python
from clarifai.client.user import User

# Initialize client
client = User(user_id="your_user_id")

# Create app for this customer
app = client.create_app(
    app_id="{project['customer_name'].lower().replace(' ', '-')}-poc",
    base_workflow="Universal"
)
print(f"App created: {{app.url}}")
```

**Step 2: Upload Sample Data**
```python
from clarifai.client.input import Inputs

inputs = Inputs(app_id=app.id)

# Upload images from local folder
inputs.upload_from_folder(
    folder_path="./customer_samples/",
    input_type="image"
)
```

### 2.2 Benchmark VLM Models

**Objective:** Test recommended models against customer data.

**Recommended Models to Test:**
1. **mm-poly-8b** (Clarifai) - Start here ⭐
2. **Llama 3.2 Vision** - Document analysis
3. **Qwen2-VL** - Complex reasoning

**Evaluation Script:**
```python
from clarifai.client import Model
import json

# Test mm-poly-8b (recommended first choice)
model = Model(url="https://clarifai.com/clarifai/mm-poly/models/mm-poly-8b")

# Define your evaluation prompt based on customer use case
eval_prompt = \"\"\"
Analyze this image and determine:
1. [Specific criteria for {project['industry']}]
2. [Quality/compliance check]
3. Provide confidence score (0-100)

Output as JSON with fields: result, confidence, reasoning
\"\"\"

# Run evaluation on sample dataset
results = []
for image_path in sample_images:
    response = model.predict_by_filepath(
        image_path,
        inference_params={{"prompt": eval_prompt}}
    )
    results.append({{
        "image": image_path,
        "output": response.outputs[0].data.text.raw
    }})

# Save results for analysis
with open("evaluation_results.json", "w") as f:
    json.dump(results, f, indent=2)
```

### 2.3 Calculate Accuracy Metrics

**Metrics Template:**

| Model | Accuracy | Precision | Recall | Avg Latency | Cost/1K |
|-------|----------|-----------|--------|-------------|---------|
| mm-poly-8b | | | | | |
| Llama 3.2 Vision | | | | | |
| Qwen2-VL | | | | | |

**Accuracy Calculation Script:**
```python
import json

def calculate_metrics(predictions, ground_truth):
    correct = sum(1 for p, gt in zip(predictions, ground_truth) if p == gt)
    accuracy = correct / len(predictions) * 100
    
    # Calculate precision/recall if binary classification
    tp = sum(1 for p, gt in zip(predictions, ground_truth) if p == gt == 1)
    fp = sum(1 for p, gt in zip(predictions, ground_truth) if p == 1 and gt == 0)
    fn = sum(1 for p, gt in zip(predictions, ground_truth) if p == 0 and gt == 1)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    
    return {{
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall
    }}
```

---

## Phase 3: Solution Architecture (Week 3)

### 3.1 Design Workflow

**Objective:** Create the model pipeline for production.

**For {project['industry']} - Recommended Architecture:**

```
Input → Preprocessing → VLM Analysis → Post-processing → Output
         (resize/format)  (mm-poly-8b)   (format/filter)
```

**Workflow Creation:**
```python
from clarifai.client.workflow import Workflow

# Create workflow with VLM
workflow = app.create_workflow(
    workflow_id="{project['project_name'].lower().replace(' ', '-')}-workflow",
    nodes=[
        {{
            "id": "vlm-analysis",
            "model": {{
                "model_id": "mm-poly-8b",
                "user_id": "clarifai",
                "app_id": "mm-poly"
            }}
        }}
    ]
)
```

### 3.2 Configure Compute Resources

**Recommended Setup for {project['customer_name']}:**

| Resource | Specification | Purpose |
|----------|--------------|---------|
| GPU Type | {gpu_type} | Model inference |
| GPU Count | {gpu_count} | Production capacity |
| Region | aws-us-east-1 | Low latency |

**Request Compute Reservation:**
1. Log into Clarifai Console
2. Navigate to Compute → Reservations
3. Select GPU type: {gpu_type}
4. Quantity: {gpu_count}
5. Duration: Annual (for best pricing)

### 3.3 Set Up Monitoring

**Key Metrics to Monitor:**
- Request latency (p50, p95, p99)
- Throughput (requests/second)
- Error rate
- GPU utilization

---

## Phase 4: Integration Development (Week 4)

### 4.1 API Integration

**Choose Integration Method:**

**Option A: Python SDK (Recommended)**
```python
from clarifai.client import Model

# Initialize model
model = Model(url="https://clarifai.com/clarifai/mm-poly/models/mm-poly-8b")

def analyze_image(image_url: str, prompt: str) -> dict:
    \"\"\"Analyze image using Clarifai VLM.\"\"\"
    response = model.predict_by_url(
        image_url,
        inference_params={{"prompt": prompt}}
    )
    return {{
        "result": response.outputs[0].data.text.raw,
        "status": "success"
    }}
```

**Option B: OpenAI-Compatible (Easy Migration)**
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://api.clarifai.com/v2/ext/openai/v1",
    api_key="YOUR_CLARIFAI_PAT"
)

response = client.chat.completions.create(
    model="https://clarifai.com/clarifai/mm-poly/models/mm-poly-8b",
    messages=[
        {{
            "role": "user",
            "content": [
                {{"type": "text", "text": "Analyze this image for {project['industry']} use case"}},
                {{"type": "image_url", "image_url": {{"url": image_url}}}}
            ]
        }}
    ]
)
```

**Option C: REST API (Any Language)**
```bash
curl -X POST "https://api.clarifai.com/v2/users/clarifai/apps/mm-poly/models/mm-poly-8b/outputs" \\
  -H "Authorization: Key YOUR_PAT" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "inputs": [{{
      "data": {{
        "image": {{"url": "IMAGE_URL"}},
        "text": {{"raw": "Your analysis prompt"}}
      }}
    }}]
  }}'
```

### 4.2 Error Handling

**Implement Robust Error Handling:**
```python
from clarifai.client import Model
from clarifai.errors import ApiError
import time

def analyze_with_retry(image_url: str, prompt: str, max_retries: int = 3) -> dict:
    \"\"\"Analyze image with retry logic.\"\"\"
    model = Model(url="https://clarifai.com/clarifai/mm-poly/models/mm-poly-8b")
    
    for attempt in range(max_retries):
        try:
            response = model.predict_by_url(
                image_url,
                inference_params={{"prompt": prompt}}
            )
            return {{
                "result": response.outputs[0].data.text.raw,
                "status": "success"
            }}
        except ApiError as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            return {{"error": str(e), "status": "failed"}}
```

### 4.3 Batch Processing (If Needed)

**For High-Volume Processing:**
```python
from concurrent.futures import ThreadPoolExecutor
from clarifai.client import Model

model = Model(url="https://clarifai.com/clarifai/mm-poly/models/mm-poly-8b")

def process_batch(image_urls: list, prompt: str, max_workers: int = 10) -> list:
    \"\"\"Process multiple images in parallel.\"\"\"
    
    def process_single(url):
        try:
            response = model.predict_by_url(url, inference_params={{"prompt": prompt}})
            return {{"url": url, "result": response.outputs[0].data.text.raw}}
        except Exception as e:
            return {{"url": url, "error": str(e)}}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_single, image_urls))
    
    return results
```

---

## Phase 5: Testing & Validation (Week 5)

### 5.1 Functional Testing

**Test Checklist:**
- [ ] Single image analysis works correctly
- [ ] Batch processing handles 100+ images
- [ ] Error handling catches edge cases
- [ ] Response format matches requirements
- [ ] Latency meets SLA requirements

### 5.2 Load Testing

**Load Test Script:**
```python
import asyncio
import aiohttp
import time

async def load_test(num_requests: int = 100):
    \"\"\"Run load test against API.\"\"\"
    
    async def single_request(session, url):
        start = time.time()
        async with session.post(url, json={{...}}) as response:
            await response.json()
            return time.time() - start
    
    async with aiohttp.ClientSession() as session:
        tasks = [single_request(session, API_URL) for _ in range(num_requests)]
        latencies = await asyncio.gather(*tasks)
    
    print(f"Requests: {{num_requests}}")
    print(f"Avg Latency: {{sum(latencies)/len(latencies):.2f}}s")
    print(f"P95 Latency: {{sorted(latencies)[int(len(latencies)*0.95)]:.2f}}s")

asyncio.run(load_test(100))
```

### 5.3 Customer UAT

**UAT Preparation:**
1. Set up demo environment
2. Prepare test cases covering all use cases
3. Create user documentation
4. Schedule UAT session with customer

**UAT Session Agenda:**
```
1. Solution overview (10 min)
2. Live demo of key workflows (20 min)
3. Customer testing (30 min)
4. Feedback collection (15 min)
5. Next steps and sign-off (15 min)
```

---

## Phase 6: Deployment & Handoff (Week 6)

### 6.1 Production Deployment

**Deployment Checklist:**
- [ ] GPU reservation confirmed and active
- [ ] Production API keys generated
- [ ] Monitoring dashboards configured
- [ ] Alerting rules set up
- [ ] Runbook documentation complete

### 6.2 Customer Training

**Training Topics:**
1. Clarifai Console navigation
2. API usage and authentication
3. Monitoring and troubleshooting
4. Scaling and optimization
5. Support channels and escalation

### 6.3 Documentation Handoff

**Deliverables:**
- [ ] API documentation with examples
- [ ] Integration guide
- [ ] Runbook for common issues
- [ ] Architecture diagram
- [ ] Contact information for support

---

{_generate_tailored_prompt(project['project_name'], project.get('refined_goals', project['goals']), project['industry'], project.get('document_types', ['images']), context)}

---

## Appendix B: Quick Reference

### API Endpoints
| Endpoint | Purpose |
|----------|---------|
| `https://api.clarifai.com/v2/users/{{user}}/apps/{{app}}/models/{{model}}/outputs` | Predict |
| `https://api.clarifai.com/v2/users/{{user}}/apps/{{app}}/inputs` | Upload data |
| `https://api.clarifai.com/v2/users/{{user}}/apps/{{app}}/workflows/{{workflow}}/results` | Workflow |

### SDK Installation
```bash
pip install clarifai
npm install clarifai
```

### Authentication
```bash
export CLARIFAI_PAT="your_personal_access_token"
```

### Support Contacts
- Technical Support: support@clarifai.com
- Documentation: https://docs.clarifai.com/
- Community: https://community.clarifai.com/

---

*Generated by Clarifai Rapid Prototyping Assistant*
"""


def _generate_tailored_prompt(project_name: str, goals: List[str], industry: str, document_types: List[str], context: str) -> str:
    """Generate a tailored prompt specifically for the user's use case."""
    
    # Combine goals into a clear task description
    primary_goal = goals[0] if goals else "analyze visual content"
    secondary_goals = goals[1:3] if len(goals) > 1 else []
    
    # Determine the prompt type based on goals
    all_goals_text = " ".join(goals).lower()
    
    # Determine document type descriptions
    doc_type_descriptions = {
        "images": "images",
        "photos": "photographs",
        "documents": "documents",
        "pdfs": "PDF documents",
        "screenshots": "screenshots",
        "scans": "scanned documents",
        "video_frames": "video frames",
        "medical_images": "medical images",
        "satellite": "satellite imagery",
        "microscopy": "microscopy images"
    }
    
    doc_description = "images"
    for dtype in document_types:
        if dtype.lower() in doc_type_descriptions:
            doc_description = doc_type_descriptions[dtype.lower()]
            break
    
    # Build the primary task instruction
    task_instruction = f"Analyze this {doc_description} and {primary_goal}"
    if secondary_goals:
        task_instruction += f", also {' and '.join(secondary_goals)}"
    
    # Determine what kind of output is needed based on goals
    output_fields = _determine_output_fields(all_goals_text, industry)
    
    # Build JSON output schema
    json_schema = _build_json_schema(output_fields)
    
    # Generate the tailored prompt
    prompt = f'''{task_instruction}.

Provide comprehensive analysis including:
1. Primary task result with high specificity
2. Confidence score (0-100) for each finding
3. Location/region information where applicable
4. Any relevant attributes or metadata
5. Recommendations or flags for human review if needed

{_get_industry_context(industry)}

Output as JSON:
{json_schema}'''

    # Build the full section
    section = f"""
## Appendix A: Tailored Prompt for This Project

This prompt is specifically generated for **{project_name}** based on the project goals and requirements.

### Your Production-Ready Prompt

Use this prompt with Clarifai's mm-poly-8b model for your specific use case:

```
{prompt}
```

### How to Use This Prompt

**Python SDK:**
```python
from clarifai.client import Model

# Initialize the mm-poly-8b model (recommended for {industry} use cases)
model = Model(url="https://clarifai.com/clarifai/mm-poly/models/mm-poly-8b")

# Your tailored prompt
prompt = \"\"\"{prompt}\"\"\"

# Process a single image
response = model.predict_by_filepath(
    "path/to/your/{doc_description.replace(' ', '_')}.jpg",
    inference_params={{"prompt": prompt}}
)

# Get the result
result = response.outputs[0].data.text.raw
print(result)

# Parse as JSON
import json
parsed = json.loads(result)
```

**Batch Processing:**
```python
import json
from pathlib import Path
from clarifai.client import Model

model = Model(url="https://clarifai.com/clarifai/mm-poly/models/mm-poly-8b")

prompt = \"\"\"{prompt}\"\"\"

def process_batch(image_paths):
    results = []
    for path in image_paths:
        response = model.predict_by_filepath(
            str(path),
            inference_params={{"prompt": prompt}}
        )
        result = json.loads(response.outputs[0].data.text.raw)
        results.append({{"file": str(path), "result": result}})
    return results

# Process all images in a directory
images = list(Path("./input").glob("*.jpg"))
batch_results = process_batch(images)
```

### Expected Output Schema

The prompt will return JSON with this structure:

```json
{json_schema}
```

### Customization Notes

You may want to adjust the prompt for:
- **More specific detection criteria**: Add explicit item names or categories you're looking for
- **Different output format**: Modify the JSON schema to match your database or API requirements
- **Threshold adjustments**: Add minimum confidence thresholds in your post-processing
- **Language/localization**: The prompt works in English; for other languages, translate the instructions

"""
    
    return section


def _determine_output_fields(goals_text: str, industry: str) -> List[Dict[str, str]]:
    """Determine what output fields are needed based on goals."""
    fields = []
    
    # Detection-related fields
    if any(word in goals_text for word in ["detect", "find", "identify", "locate", "recognize"]):
        fields.append({"name": "detections", "type": "array", "description": "List of detected items with location and confidence"})
        fields.append({"name": "total_count", "type": "integer", "description": "Total number of items detected"})
    
    # Classification-related fields
    if any(word in goals_text for word in ["classify", "categorize", "type", "sort", "label"]):
        fields.append({"name": "classification", "type": "string", "description": "Primary classification result"})
        fields.append({"name": "categories", "type": "array", "description": "All applicable categories with confidence"})
    
    # Extraction-related fields
    if any(word in goals_text for word in ["extract", "read", "parse", "ocr", "capture"]):
        fields.append({"name": "extracted_data", "type": "object", "description": "Key-value pairs of extracted information"})
        fields.append({"name": "text_content", "type": "array", "description": "All text found in the image"})
    
    # Quality/Inspection-related fields
    if any(word in goals_text for word in ["quality", "inspect", "check", "verify", "defect", "compliance"]):
        fields.append({"name": "pass_fail", "type": "boolean", "description": "Overall pass/fail status"})
        fields.append({"name": "issues", "type": "array", "description": "List of issues found with severity"})
        fields.append({"name": "quality_score", "type": "integer", "description": "Overall quality score 0-100"})
    
    # Counting-related fields
    if any(word in goals_text for word in ["count", "inventory", "tally", "quantity", "number"]):
        fields.append({"name": "counts", "type": "object", "description": "Counts by category"})
        fields.append({"name": "total", "type": "integer", "description": "Total count"})
    
    # Comparison/Matching fields
    if any(word in goals_text for word in ["compare", "match", "verify", "validate", "similar"]):
        fields.append({"name": "match_result", "type": "boolean", "description": "Whether items match"})
        fields.append({"name": "differences", "type": "array", "description": "List of differences found"})
        fields.append({"name": "similarity_score", "type": "integer", "description": "Similarity percentage 0-100"})
    
    # Always include these base fields
    fields.append({"name": "confidence", "type": "integer", "description": "Overall confidence score 0-100"})
    fields.append({"name": "processing_notes", "type": "string", "description": "Any notes about the analysis"})
    
    # Remove duplicates while preserving order
    seen = set()
    unique_fields = []
    for field in fields:
        if field["name"] not in seen:
            seen.add(field["name"])
            unique_fields.append(field)
    
    return unique_fields


def _build_json_schema(fields: List[Dict[str, str]]) -> str:
    """Build a JSON schema string from field definitions."""
    schema_lines = ["{"]
    
    for i, field in enumerate(fields):
        field_type = field["type"]
        if field_type == "array":
            if "detection" in field["name"]:
                value = '[{"item": "", "location": "", "confidence": 0, "attributes": {}}]'
            elif "issue" in field["name"]:
                value = '[{"issue": "", "severity": "low/medium/high", "location": ""}]'
            elif "categor" in field["name"]:
                value = '[{"category": "", "confidence": 0}]'
            elif "text" in field["name"]:
                value = '["text found"]'
            elif "difference" in field["name"]:
                value = '["difference description"]'
            else:
                value = '[]'
        elif field_type == "object":
            if "extracted" in field["name"]:
                value = '{"field_name": "value"}'
            elif "count" in field["name"]:
                value = '{"category_name": 0}'
            else:
                value = '{}'
        elif field_type == "boolean":
            value = "true/false"
        elif field_type == "integer":
            value = "0"
        else:
            value = '""' 
        
        comma = "," if i < len(fields) - 1 else ""
        schema_lines.append(f'  "{field["name"]}": {value}{comma}')
    
    schema_lines.append("}")
    return "\n".join(schema_lines)


def _get_industry_context(industry: str) -> str:
    """Get industry-specific context to add to the prompt."""
    industry_lower = industry.lower()
    
    contexts = {
        "retail": "For retail analysis, pay special attention to brand names, product conditions, pricing labels, and shelf placement.",
        "manufacturing": "For manufacturing inspection, focus on defects, dimensional accuracy, surface quality, and compliance with specifications.",
        "healthcare": "For healthcare content, maintain HIPAA awareness - flag any PHI. Focus on accuracy and defer diagnosis to medical professionals.",
        "logistics": "For logistics analysis, prioritize tracking numbers, addresses, package conditions, and handling instructions.",
        "financial": "For financial documents, ensure accuracy of amounts, dates, and account numbers. Flag any potential discrepancies.",
        "media": "For media content, evaluate content appropriateness, identify subjects, and assess visual quality.",
        "insurance": "For insurance documents, extract claim details, verify documentation completeness, and flag inconsistencies.",
        "agriculture": "For agricultural analysis, assess crop health, identify pests or diseases, and evaluate growth conditions.",
        "construction": "For construction inspection, verify safety compliance, material quality, and work progress.",
        "automotive": "For automotive inspection, identify damage, verify part numbers, and assess vehicle condition."
    }
    
    for key, context in contexts.items():
        if key in industry_lower:
            return context
    
    return "Provide detailed analysis relevant to the specific use case requirements."


def _parse_generated_questions(content: str, industry: str) -> List[Dict[str, Any]]:
    """Parse AI-generated questions into structured format."""
    # Simple parsing - in production would be more sophisticated
    questions = []
    lines = content.split('\n')
    
    current_question = None
    for line in lines:
        line = line.strip()
        if line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.', '- ', '• ')):
            if current_question:
                questions.append(current_question)
            current_question = {
                "question": line.lstrip('0123456789.-• ').strip(),
                "category": "general",
                "importance": "medium",
                "compute_relevant": "compute" in line.lower() or "gpu" in line.lower(),
                "follow_ups": [],
            }
    
    if current_question:
        questions.append(current_question)
    
    return questions[:10]  # Limit to 10 questions


def create_app():
    """Create and configure the FastAPI application."""
    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
