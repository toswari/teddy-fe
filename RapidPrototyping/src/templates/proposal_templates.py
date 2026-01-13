"""
Proposal Templates

Jinja2-based templates for generating proposal documents.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, PackageLoader, select_autoescape, BaseLoader, TemplateNotFound


# Inline templates for portability
PROPOSAL_TEMPLATE = """# Project Proposal: {{ project_name }}

**Customer:** {{ customer_name }}
**Date:** {{ date }}
**Prepared by:** {{ prepared_by | default('Clarifai Solution Engineering') }}

---

## Executive Summary

{{ executive_summary }}

---

## Problem Statement

{{ problem_statement }}

---

## Proposed Solution

{{ proposed_solution }}

### Clarifai Capabilities Leveraged

{% for capability in capabilities %}
- **{{ capability.name }}**: {{ capability.description }}
{% endfor %}

---

## Technical Approach

{{ technical_approach }}

### Architecture Overview

```
{{ architecture_diagram | default('Architecture diagram to be provided') }}
```

---

## Deliverables

| # | Deliverable | Description | Acceptance Criteria |
|---|-------------|-------------|---------------------|
{% for d in deliverables %}
| {{ loop.index }} | {{ d.name }} | {{ d.description }} | {{ d.criteria }} |
{% endfor %}

---

## Timeline & Milestones

| Phase | Duration | Milestones | Deliverables |
|-------|----------|------------|--------------|
{% for phase in timeline %}
| {{ phase.name }} | {{ phase.duration }} | {{ phase.milestones }} | {{ phase.deliverables }} |
{% endfor %}

---

## Pricing Considerations

{{ pricing_section }}

### Cost Factors

{% for factor in cost_factors %}
- {{ factor }}
{% endfor %}

---

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
{% for risk in risks %}
| {{ risk.description }} | {{ risk.impact }} | {{ risk.probability }} | {{ risk.mitigation }} |
{% endfor %}

---

## Success Metrics

{% for metric in success_metrics %}
- **{{ metric.name }}**: {{ metric.target }} (Baseline: {{ metric.baseline | default('TBD') }})
{% endfor %}

---

## Next Steps

{% for step in next_steps %}
{{ loop.index }}. {{ step }}
{% endfor %}

---

## Appendix

{{ appendix | default('') }}

---

*This proposal is valid for 30 days from the date above.*

**Clarifai, Inc.**
"""

EXECUTIVE_SUMMARY_TEMPLATE = """# Executive Summary

**Project:** {{ project_name }}
**Customer:** {{ customer_name }}
**Date:** {{ date }}

---

## The Opportunity

{{ opportunity_statement }}

## Proposed Solution

{{ solution_summary }}

## Expected Outcomes

{% for outcome in expected_outcomes %}
- {{ outcome }}
{% endfor %}

## Investment Overview

{{ investment_summary }}

## Timeline

{{ timeline_summary }}

## Why Clarifai

{{ why_clarifai }}

---

## Recommended Next Steps

{% for step in next_steps %}
{{ loop.index }}. {{ step }}
{% endfor %}

---

*Contact: {{ contact_info | default('solutions@clarifai.com') }}*
"""

POC_TEMPLATE = """# Proof of Concept Plan

**Project:** {{ project_name }}
**Customer:** {{ customer_name }}
**Duration:** {{ duration }}
**Start Date:** {{ start_date }}

---

## POC Objectives

{% for objective in objectives %}
{{ loop.index }}. {{ objective }}
{% endfor %}

---

## Scope

### In Scope

{% for item in in_scope %}
- {{ item }}
{% endfor %}

### Out of Scope

{% for item in out_scope %}
- {{ item }}
{% endfor %}

---

## Success Criteria

| Criterion | Target | Measurement Method |
|-----------|--------|-------------------|
{% for criterion in success_criteria %}
| {{ criterion.name }} | {{ criterion.target }} | {{ criterion.method }} |
{% endfor %}

---

## Weekly Plan

{% for week in weekly_plan %}
### Week {{ week.number }}: {{ week.title }}

**Focus:** {{ week.focus }}

**Activities:**
{% for activity in week.activities %}
- {{ activity }}
{% endfor %}

**Deliverables:**
{% for deliverable in week.deliverables %}
- {{ deliverable }}
{% endfor %}

{% endfor %}

---

## Data Requirements

{{ data_requirements }}

---

## Resource Requirements

### Clarifai Team

{% for resource in clarifai_resources %}
- {{ resource.role }}: {{ resource.allocation }}
{% endfor %}

### Customer Team

{% for resource in customer_resources %}
- {{ resource.role }}: {{ resource.responsibilities }}
{% endfor %}

---

## Demo Scenarios

{% for demo in demo_scenarios %}
### Demo {{ loop.index }}: {{ demo.name }}

{{ demo.description }}

**Success Indicator:** {{ demo.success_indicator }}

{% endfor %}

---

## Go/No-Go Criteria

| Criterion | Threshold | Decision |
|-----------|-----------|----------|
{% for criterion in go_nogo_criteria %}
| {{ criterion.name }} | {{ criterion.threshold }} | {{ criterion.decision }} |
{% endfor %}

---

## Risk Mitigation

{% for risk in risks %}
- **{{ risk.name }}**: {{ risk.mitigation }}
{% endfor %}

---

*POC Sign-off required from both parties before commencement.*
"""


class StringLoader(BaseLoader):
    """Load templates from strings."""
    
    def __init__(self, templates: Dict[str, str]):
        self.templates = templates
    
    def get_source(self, environment, template):
        if template in self.templates:
            return self.templates[template], template, lambda: True
        raise TemplateNotFound(template)


class BaseTemplate:
    """Base class for proposal templates."""
    
    template_string: str = ""
    template_name: str = "base"
    
    def __init__(self):
        self.env = Environment(
            loader=StringLoader({self.template_name: self.template_string}),
            autoescape=select_autoescape(['html', 'xml']),
        )
        self.template = self.env.get_template(self.template_name)
    
    def render(self, **kwargs) -> str:
        """Render the template with provided variables."""
        # Add default date
        if 'date' not in kwargs:
            kwargs['date'] = datetime.now().strftime("%B %d, %Y")
        
        return self.template.render(**kwargs)
    
    def save(self, output_path: str, **kwargs) -> Path:
        """Render and save to file."""
        content = self.render(**kwargs)
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path


class ProposalTemplate(BaseTemplate):
    """Full project proposal template."""
    
    template_string = PROPOSAL_TEMPLATE
    template_name = "proposal"
    
    def render(
        self,
        project_name: str,
        customer_name: str,
        executive_summary: str,
        problem_statement: str,
        proposed_solution: str,
        technical_approach: str,
        capabilities: List[Dict[str, str]] = None,
        deliverables: List[Dict[str, str]] = None,
        timeline: List[Dict[str, str]] = None,
        pricing_section: str = "",
        cost_factors: List[str] = None,
        risks: List[Dict[str, str]] = None,
        success_metrics: List[Dict[str, str]] = None,
        next_steps: List[str] = None,
        **kwargs
    ) -> str:
        """Render the proposal template."""
        return super().render(
            project_name=project_name,
            customer_name=customer_name,
            executive_summary=executive_summary,
            problem_statement=problem_statement,
            proposed_solution=proposed_solution,
            technical_approach=technical_approach,
            capabilities=capabilities or [],
            deliverables=deliverables or [],
            timeline=timeline or [],
            pricing_section=pricing_section,
            cost_factors=cost_factors or [],
            risks=risks or [],
            success_metrics=success_metrics or [],
            next_steps=next_steps or [],
            **kwargs
        )


class ExecutiveSummaryTemplate(BaseTemplate):
    """Executive summary template."""
    
    template_string = EXECUTIVE_SUMMARY_TEMPLATE
    template_name = "executive_summary"


class TechnicalAppendixTemplate(BaseTemplate):
    """Technical appendix template."""
    
    template_string = """# Technical Appendix

**Project:** {{ project_name }}
**Version:** {{ version | default('1.0') }}
**Date:** {{ date }}

---

## API Specifications

{{ api_specifications }}

---

## Data Requirements

### Input Data

{{ input_data_specs }}

### Output Data

{{ output_data_specs }}

---

## Model Configuration

{% for model in models %}
### {{ model.name }}

- **URL:** {{ model.url }}
- **Version:** {{ model.version }}
- **Use Case:** {{ model.use_case }}

{% endfor %}

---

## Infrastructure Requirements

{{ infrastructure_requirements }}

---

## Security Considerations

{{ security_considerations }}

---

## Performance Benchmarks

| Metric | Target | Notes |
|--------|--------|-------|
{% for benchmark in benchmarks %}
| {{ benchmark.metric }} | {{ benchmark.target }} | {{ benchmark.notes }} |
{% endfor %}

---

## Integration Guide

{{ integration_guide }}
"""
    template_name = "technical_appendix"


class POCPlanTemplate(BaseTemplate):
    """POC plan template."""
    
    template_string = POC_TEMPLATE
    template_name = "poc_plan"
