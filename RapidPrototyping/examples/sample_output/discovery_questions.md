# Discovery Questions for TechRetail Inc.

**Customer:** TechRetail Inc.
**Industry:** E-commerce / Retail
**Generated:** January 12, 2026

---

## Business Requirements

### 1. What are your top 3 business objectives for this AI initiative?
**Why this matters:** Understanding priority helps us focus the solution on highest-impact areas.
**Red flags:** Vague objectives, unrealistic expectations, misalignment between stakeholders.

### 2. How do you measure success for your current search functionality?
**Why this matters:** Establishes baseline metrics for improvement measurement.
**Follow-up:** What is your current search-to-purchase conversion rate?

### 3. What is the business impact of manual product tagging today?
**Why this matters:** Quantifies the ROI potential for automation.
**Follow-up:** How many hours per week are spent on tagging? What is the cost?

### 4. Who are the key decision-makers for this project?
**Why this matters:** Ensures we engage all stakeholders appropriately.
**Red flags:** Unclear decision authority, missing technical or business representation.

---

## Technical Requirements

### 5. Can you describe your current AWS architecture in more detail?
**Why this matters:** Determines integration approach and deployment options.
**Follow-up:** Do you use managed Kubernetes (EKS)? What's your deployment process?

### 6. What are your latency requirements for search and tagging?
**Why this matters:** Impacts architecture decisions and model selection.
**Target understanding:** Real-time (<500ms) vs near-real-time (<5s) vs batch.

### 7. What authentication/authorization system do you use?
**Why this matters:** API integration and security requirements.
**Follow-up:** OAuth, API keys, JWT? Do you need role-based access?

### 8. What monitoring and observability tools do you use?
**Why this matters:** Integration with existing DevOps practices.
**Examples:** CloudWatch, Datadog, Prometheus, etc.

### 9. Do you have any specific security or compliance requirements beyond GDPR?
**Why this matters:** May impact deployment options and data handling.
**Follow-up:** PCI-DSS for payments? SOC 2 requirements for vendors?

---

## Data Requirements

### 10. How many product images do you currently have?
**Why this matters:** Determines indexing approach and storage requirements.
**Follow-up:** Average images per product? Image quality/resolution?

### 11. What format is your product metadata in?
**Why this matters:** Data pipeline design for integration.
**Follow-up:** Database schema? API available? Export formats?

### 12. Do you have labeled data for training custom models?
**Why this matters:** Determines if custom training is feasible.
**Examples:** Category labels, attribute annotations, quality grades.

### 13. How frequently is your product catalog updated?
**Why this matters:** Index refresh strategy and real-time requirements.
**Follow-up:** New products per day/week? Update frequency for existing?

### 14. What is the volume of user-generated content requiring moderation?
**Why this matters:** Sizing the moderation pipeline.
**Follow-up:** Images per day? Reviews per day? Peak periods?

---

## Integration Requirements

### 15. What APIs does your current product catalog expose?
**Why this matters:** Determines integration complexity.
**Follow-up:** REST/GraphQL? Authentication? Rate limits?

### 16. How do you currently integrate with third-party services?
**Why this matters:** Understanding preferred integration patterns.
**Follow-up:** Webhooks? Message queues? Direct API calls?

### 17. Do you have a data warehouse or analytics platform?
**Why this matters:** Reporting and metrics integration.
**Follow-up:** BigQuery, Redshift, Snowflake? BI tools?

### 18. What's your preference for deployment: cloud-hosted vs on-premise?
**Why this matters:** Clarifai offers both options.
**Follow-up:** Any data residency requirements? On-premise constraints?

---

## Timeline & Budget

### 19. Is the 6-month timeline firm, or is there flexibility?
**Why this matters:** Determines feasible scope and phasing.
**Red flags:** Unrealistic timeline expectations, external deadline pressures.

### 20. How was the $150-200K annual budget determined?
**Why this matters:** Understanding budget flexibility and expectations.
**Follow-up:** Does this include implementation services? Internal costs?

### 21. What is your procurement process for new vendors?
**Why this matters:** Impacts project timeline.
**Follow-up:** Security review? Legal review? Typical duration?

### 22. Are there any dependencies on other projects or initiatives?
**Why this matters:** Identifies potential blockers or synergies.
**Follow-up:** Platform migrations? Team changes? Other AI projects?

---

## Success Criteria

### 23. How will you measure the 30% improvement in search conversion?
**Why this matters:** Ensures we're aligned on measurement methodology.
**Follow-up:** A/B testing planned? Current analytics capabilities?

### 24. What does "same-day listing" mean specifically?
**Why this matters:** Clear definition of success criteria.
**Follow-up:** From image upload to live on site? Working hours only?

### 25. Who will evaluate and sign off on POC success?
**Why this matters:** Ensures clear decision criteria and authority.
**Follow-up:** What would make you say "no" to moving forward?

### 26. What happens if we achieve some but not all success criteria?
**Why this matters:** Understanding flexibility and priorities.
**Red flags:** All-or-nothing expectations, unclear prioritization.

---

## Additional Discovery Areas

### Team & Resources

### 27. What team members will be involved in the implementation?
**Follow-up:** Technical skills available? Dedicated or shared resources?

### 28. Do you have ML/AI expertise in-house?
**Why this matters:** Training needs and ongoing support model.

### 29. Who will maintain the system after go-live?
**Why this matters:** Support and operational model planning.

### Competitive & Strategic

### 30. Are you evaluating other AI/ML solutions?
**Why this matters:** Competitive positioning and differentiation.

### 31. What made you consider Clarifai specifically?
**Why this matters:** Understanding value drivers and expectations.

### 32. How does this initiative fit into your broader technology strategy?
**Why this matters:** Long-term partnership potential.

---

## Notes for Follow-up

After the initial discovery call, we should:
1. Request sample data (product images, metadata export)
2. Schedule technical deep-dive with engineering team
3. Get access to current analytics dashboards
4. Review existing API documentation
5. Understand current vendor relationships (CDN, search provider, etc.)

---

*Generated by Clarifai Rapid Prototyping Framework*
