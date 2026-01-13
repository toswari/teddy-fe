"""
Main entry point for the Clarifai Rapid Prototyping Framework.

Provides both CLI and interactive modes for generating proposals.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from src.config import init_config, get_config
from src.agents import ProposalAgent, DiscoveryAgent, SolutionAgent
from src.processors import DocumentProcessor, ImageProcessor
from src.clients.clarifai_client import ClarifaiClient


console = Console()
logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO"):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )


def print_banner():
    """Print the application banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║           Clarifai Rapid Prototyping Framework                ║
║                                                               ║
║   AI-Powered Solution Engineering Assistant                   ║
╚═══════════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold blue")


def interactive_mode():
    """Run the interactive CLI mode."""
    print_banner()
    
    config = get_config()
    
    console.print("\n[bold green]Welcome to the Clarifai Rapid Prototyping Framework![/bold green]")
    console.print("This tool helps Solution Engineers create proposals and technical documentation.\n")
    
    # Check API key
    if not config.settings.clarifai_api_key:
        api_key = Prompt.ask("Enter your Clarifai API key")
        import os
        os.environ["CLARIFAI_API_KEY"] = api_key
    
    while True:
        console.print("\n[bold]What would you like to do?[/bold]")
        console.print("1. Generate Discovery Questions")
        console.print("2. Generate Project Proposal")
        console.print("3. Design Solution Architecture")
        console.print("4. Analyze Documents")
        console.print("5. Analyze Images/Diagrams")
        console.print("6. Full Proposal Workflow")
        console.print("7. Exit")
        
        choice = Prompt.ask("\nEnter your choice", choices=["1", "2", "3", "4", "5", "6", "7"])
        
        try:
            if choice == "1":
                run_discovery_workflow()
            elif choice == "2":
                run_proposal_workflow()
            elif choice == "3":
                run_solution_workflow()
            elif choice == "4":
                run_document_analysis()
            elif choice == "5":
                run_image_analysis()
            elif choice == "6":
                run_full_workflow()
            elif choice == "7":
                console.print("\n[bold]Thank you for using Clarifai Rapid Prototyping![/bold]")
                break
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled.[/yellow]")
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            logger.exception("Error in interactive mode")


def run_discovery_workflow():
    """Run the discovery questions workflow."""
    console.print("\n[bold blue]═══ Discovery Questions Generator ═══[/bold blue]\n")
    
    customer_name = Prompt.ask("Customer name")
    industry = Prompt.ask("Industry", default="technology")
    context = Prompt.ask("Describe the customer's needs/situation")
    
    console.print("\n[yellow]Generating discovery questions...[/yellow]")
    
    agent = DiscoveryAgent()
    result = agent.generate_questions(
        customer_context=context,
        industry=industry,
    )
    
    console.print("\n")
    console.print(Panel(Markdown(result.content), title="Discovery Questions"))
    
    if Confirm.ask("\nSave to file?"):
        output_dir = get_config().settings.output_dir
        filepath = result.save(output_dir)
        console.print(f"[green]Saved to: {filepath}[/green]")


def run_proposal_workflow():
    """Run the proposal generation workflow."""
    console.print("\n[bold blue]═══ Project Proposal Generator ═══[/bold blue]\n")
    
    customer_name = Prompt.ask("Customer name")
    project_name = Prompt.ask("Project name")
    industry = Prompt.ask("Industry", default="technology")
    
    console.print("\nEnter project goals (one per line, empty line to finish):")
    goals = []
    while True:
        goal = Prompt.ask("Goal", default="")
        if not goal:
            break
        goals.append(goal)
    
    requirements = Prompt.ask("Describe the requirements (or press Enter to skip)", default="")
    
    console.print("\n[yellow]Generating proposal...[/yellow]")
    
    agent = ProposalAgent()
    result = agent.generate_proposal(
        customer_name=customer_name,
        project_name=project_name,
        goals=goals,
        industry=industry,
        requirements=requirements if requirements else None,
    )
    
    console.print("\n")
    console.print(Panel(Markdown(result.content), title="Project Proposal"))
    
    if Confirm.ask("\nSave to file?"):
        output_dir = get_config().settings.output_dir
        filepath = result.save(output_dir)
        console.print(f"[green]Saved to: {filepath}[/green]")


def run_solution_workflow():
    """Run the solution architecture workflow."""
    console.print("\n[bold blue]═══ Solution Architecture Designer ═══[/bold blue]\n")
    
    requirements = Prompt.ask("Describe the technical requirements")
    
    console.print("\nEnter constraints (one per line, empty line to finish):")
    constraints = []
    while True:
        constraint = Prompt.ask("Constraint", default="")
        if not constraint:
            break
        constraints.append(constraint)
    
    existing_infra = Prompt.ask("Describe existing infrastructure (or press Enter to skip)", default="")
    
    console.print("\n[yellow]Designing solution architecture...[/yellow]")
    
    agent = SolutionAgent()
    result = agent.design_architecture(
        requirements=requirements,
        constraints=constraints if constraints else None,
        existing_infrastructure=existing_infra if existing_infra else None,
    )
    
    console.print("\n")
    console.print(Panel(Markdown(result.content), title="Solution Architecture"))
    
    if Confirm.ask("\nSave to file?"):
        output_dir = get_config().settings.output_dir
        filepath = result.save(output_dir)
        console.print(f"[green]Saved to: {filepath}[/green]")


def run_document_analysis():
    """Run document analysis workflow."""
    console.print("\n[bold blue]═══ Document Analyzer ═══[/bold blue]\n")
    
    file_path = Prompt.ask("Enter document path")
    
    if not Path(file_path).exists():
        console.print(f"[red]File not found: {file_path}[/red]")
        return
    
    console.print("\n[yellow]Processing document...[/yellow]")
    
    processor = DocumentProcessor()
    doc = processor.process(file_path, generate_summary=True)
    
    console.print("\n")
    console.print(Panel(
        f"**File:** {doc.filename}\n"
        f"**Type:** {doc.file_type}\n"
        f"**Chunks:** {len(doc.chunks)}\n\n"
        f"**Summary:**\n{doc.summary or 'No summary generated'}",
        title="Document Analysis"
    ))


def run_image_analysis():
    """Run image analysis workflow."""
    console.print("\n[bold blue]═══ Image/Diagram Analyzer ═══[/bold blue]\n")
    
    image_source = Prompt.ask("Enter image URL or path")
    analysis_type = Prompt.ask(
        "Analysis type",
        choices=["general", "diagram", "mockup", "product", "data"],
        default="general"
    )
    
    console.print("\n[yellow]Analyzing image...[/yellow]")
    
    processor = ImageProcessor()
    result = processor.analyze(image_source, analysis_type)
    
    console.print("\n")
    console.print(Panel(
        f"**Source:** {result.source}\n\n"
        f"**Description:**\n{result.description}",
        title="Image Analysis"
    ))


def run_full_workflow():
    """Run the full proposal workflow."""
    console.print("\n[bold blue]═══ Full Proposal Workflow ═══[/bold blue]\n")
    
    # Step 1: Basic info
    console.print("[bold]Step 1: Basic Information[/bold]\n")
    customer_name = Prompt.ask("Customer name")
    project_name = Prompt.ask("Project name")
    industry = Prompt.ask("Industry", default="technology")
    
    # Step 2: Goals
    console.print("\n[bold]Step 2: Project Goals[/bold]")
    console.print("Enter goals (one per line, empty line to finish):")
    goals = []
    while True:
        goal = Prompt.ask("Goal", default="")
        if not goal:
            break
        goals.append(goal)
    
    # Step 3: Document analysis (optional)
    console.print("\n[bold]Step 3: Document Analysis (Optional)[/bold]")
    doc_summary = None
    if Confirm.ask("Do you have documents to analyze?"):
        doc_path = Prompt.ask("Enter document path")
        if Path(doc_path).exists():
            console.print("[yellow]Analyzing document...[/yellow]")
            processor = DocumentProcessor()
            doc = processor.process(doc_path, generate_summary=True)
            doc_summary = doc.summary
            console.print(f"[green]Document analyzed: {doc.filename}[/green]")
    
    # Step 4: Generate discovery questions
    console.print("\n[bold]Step 4: Generating Discovery Questions[/bold]")
    console.print("[yellow]Generating...[/yellow]")
    
    discovery_agent = DiscoveryAgent()
    discovery_result = discovery_agent.generate_questions(
        customer_context=f"{customer_name} in {industry} industry. Goals: {', '.join(goals)}",
        industry=industry,
    )
    
    console.print(Panel(Markdown(discovery_result.content), title="Discovery Questions"))
    
    # Step 5: Generate proposal
    console.print("\n[bold]Step 5: Generating Proposal[/bold]")
    console.print("[yellow]Generating...[/yellow]")
    
    proposal_agent = ProposalAgent()
    proposal_result = proposal_agent.generate_proposal(
        customer_name=customer_name,
        project_name=project_name,
        goals=goals,
        industry=industry,
        documents_summary=doc_summary,
    )
    
    console.print(Panel(Markdown(proposal_result.content), title="Project Proposal"))
    
    # Step 6: Generate solution architecture
    console.print("\n[bold]Step 6: Generating Solution Architecture[/bold]")
    console.print("[yellow]Generating...[/yellow]")
    
    solution_agent = SolutionAgent()
    solution_result = solution_agent.design_architecture(
        requirements=f"Goals: {', '.join(goals)}. Industry: {industry}",
    )
    
    console.print(Panel(Markdown(solution_result.content), title="Solution Architecture"))
    
    # Save all outputs
    if Confirm.ask("\nSave all outputs?"):
        output_dir = Path(get_config().settings.output_dir) / customer_name.replace(" ", "_")
        
        discovery_result.save(str(output_dir))
        proposal_result.save(str(output_dir))
        solution_result.save(str(output_dir))
        
        console.print(f"[green]All outputs saved to: {output_dir}[/green]")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clarifai Rapid Prototyping Framework"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration directory"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(log_level)
    
    # Initialize configuration
    if args.config:
        init_config(args.config)
    else:
        init_config()
    
    # Run interactive mode by default
    interactive_mode()


if __name__ == "__main__":
    main()
