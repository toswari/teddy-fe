# Sales Engineering Prompts Repository 📝

This directory contains a curated collection of specialized AI prompts developed for various Clarifai customer projects and proof-of-concepts. Each prompt is carefully crafted for specific use cases and AI models to ensure optimal performance and accuracy.

## 📋 Available Prompts

### 🛰️ ClassifAI - Document Classification
**File:** `ClassifAI-Prompt.md`
- **Customer:** Government/Intelligence Community
- **Use Case:** ODNI Classification Guide-based document classification
- **Model Compatibility:** Claude 3.5 Sonnet, GPT-4o, Gemini, Llama 3.2
- **Features:** 
  - Comprehensive ODNI Classification Guide (Version 2.1)
  - FISA, Human Resources, Location, and Collection guidelines
  - Multi-level classification (U, C, S, TS)
  - Structured JSON output format
- **Integration:** Used in ClassifAI Streamlit demo application

### 🍽️ HelloFresh - Brand Compliance
**File:** `HelloFreshGuidance-Prompt.md`
- **Customer:** HelloFresh
- **Use Case:** Marketing creative brand compliance analysis
- **Model Compatibility:** Multi-modal LLMs (Claude, GPT-4o, Gemini)
- **Features:**
  - Logo integrity verification
  - Brand name spelling validation
  - Packaging design compliance
  - Text legibility assessment
  - Food presentation quality checks
  - Offer disclaimer requirements
- **Integration:** Used in HelloFresh Brand Compliance Specialist POC

### 🚗 KIA Motors - Brand Guidelines
**File:** `KIAGuidance-Prompt.md`
- **Customer:** KIA Motors Corporation
- **Use Case:** Visual asset brand guideline compliance
- **Model Compatibility:** Claude 3.5 Sonnet, Gemini 1.5 Pro, GPT-4o
- **Features:**
  - Core logo integrity analysis
  - Logo expansion guidelines
  - Partnership/collaboration logo rules
  - Precise geometric measurements (K-height based)
  - Multi-category logo type identification
  - Structured JSON compliance reporting
- **Integration:** Used in KIA AI Brand Compliance Specialist application

## 🎯 Prompt Development Guidelines

### Creating New Prompts

When developing new prompts for customer projects, follow these best practices:

1. **Create a dedicated file:** `[CustomerName][UseCase]-Prompt.md`
2. **Include metadata:**
   ```markdown
   # Customer: [Company Name]
   # Use Case: [Specific application]
   # Model Compatibility: [Supported AI models]
   # Version: [1.0]
   # Last Updated: [Date]
   ```

3. **Structure Requirements:**
   - Clear persona definition
   - Specific objective statement
   - Step-by-step process instructions
   - Detailed guidelines/rules
   - Expected output format (preferably JSON)
   - Example inputs/outputs when possible

### Prompt Engineering Best Practices

#### 🎭 **Persona Definition**
- Define a clear, expert persona (e.g., "Brand Compliance Specialist")
- Specify expertise areas and behavioral traits
- Set the tone for analytical precision

#### 🎯 **Objective Clarity**
- State the exact goal of the analysis
- Define success criteria
- Specify compliance standards or guidelines

#### 🔄 **Process Structure**
- Break down analysis into logical steps
- Use numbered or bulleted instructions
- Include decision trees for complex scenarios

#### 📊 **Output Formatting**
- Prefer structured JSON for programmatic processing
- Include confidence scores when applicable
- Provide detailed violation descriptions
- Add actionable recommendations

## 🔧 Model Compatibility Matrix

| Prompt | Claude 3.5 | GPT-4o | Gemini 1.5 | Llama 3.2 | Phi-4 | Qwen |
|--------|------------|---------|------------|-----------|-------|------|
| ClassifAI | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| HelloFresh | ✅ | ✅ | ✅ | ⚠️ | ⚠️ | ⚠️ |
| KIA | ✅ | ✅ | ✅ | ⚠️ | ❌ | ⚠️ |

**Legend:**
- ✅ **Fully Compatible:** Tested and optimized
- ⚠️ **Partially Compatible:** Works with adjustments
- ❌ **Not Compatible:** Requires significant modifications

## 📁 Integration Examples

### Streamlit Applications
```python
# Example: Loading a prompt for use in Streamlit
def load_prompt(prompt_file):
    with open(f"Prompts/{prompt_file}", "r") as f:
        return f.read()

# Usage in ClassifAI
ODNI_PROMPT = load_prompt("ClassifAI-Prompt.md")
response = model.predict(inputs=[{
    "data": {
        "text": {"raw": ODNI_PROMPT + user_input}
    }
}])
```

### Clarifai SDK Integration
```python
from clarifai.client.model import Model

# Initialize model with prompt
model = Model(url=model_url, pat=clarifai_pat)
prompt_text = load_brand_prompt("KIAGuidance-Prompt.md")

# Analyze image with custom prompt
response = model.predict(inputs=[{
    "data": {
        "image": {"base64": image_base64},
        "text": {"raw": prompt_text}
    }
}])
```

## 🔍 Testing & Validation

### Prompt Performance Testing

For each new prompt, ensure comprehensive testing:

1. **Accuracy Testing:**
   - Test with known compliant examples
   - Test with known violation cases
   - Verify edge case handling

2. **Model Consistency:**
   - Test across different supported models
   - Compare output consistency
   - Document model-specific variations

3. **Output Format Validation:**
   - Verify JSON structure compliance
   - Test parsing reliability
   - Validate required fields presence

### Quality Metrics

Track these metrics for prompt effectiveness:
- **Accuracy Rate:** Percentage of correct classifications
- **Consistency Score:** Agreement across different models
- **Response Time:** Average processing duration
- **Token Efficiency:** Input/output token optimization

## 📚 Documentation Standards

### Customer Information
Each prompt file should include:
- Customer company name and contact
- Project timeline and status
- Business requirements and constraints
- Success criteria and KPIs

### Technical Specifications
Document the following:
- Supported input formats (image, text, PDF)
- Expected output structure
- Error handling requirements
- Rate limiting considerations

### Version Control
Maintain version history for each prompt:
- Change log with dates and reasons
- Backward compatibility notes
- Migration instructions for updates

## 🚀 Deployment Guidelines

### Production Readiness Checklist

Before deploying prompts to customer environments:

- [ ] **Testing Complete:** All test cases pass
- [ ] **Model Validation:** Verified on target AI models
- [ ] **Performance Benchmarks:** Meets speed/accuracy requirements
- [ ] **Documentation Updated:** README and inline docs current
- [ ] **Customer Approval:** Final prompt approved by customer
- [ ] **Security Review:** No sensitive information in prompts
- [ ] **Error Handling:** Graceful failure modes implemented

### Integration Support

For technical integration assistance:
1. Review the specific prompt documentation
2. Check model compatibility matrix
3. Test with sample inputs first
4. Monitor performance metrics in production
5. Contact the sales engineering team for optimization

## 📞 Support & Contact

For prompt development, customization, or technical support:
- **Sales Engineering Team:** [Internal Contact]
- **Documentation Issues:** Create issue in this repository
- **Feature Requests:** Contact customer success team
- **Emergency Support:** [Internal escalation process]

---

**Last Updated:** September 2025 | **Maintained by:** Clarifai Sales Engineering Team

*This repository is part of the Clarifai PS-Field-Engineering project and contains proprietary customer-specific prompts.*
