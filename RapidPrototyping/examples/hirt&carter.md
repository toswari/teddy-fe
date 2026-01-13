Automated AI-Driven QA System that validates images against these strict criteria before they reach human reviewers or go live.

Goal is to leverage Clarifai api to sort customer images based on these.

The project encompasses three distinct verification layers:
1. E-commerce Retouching Automation This layer focuses on post-production hygiene. The system must verify:
Background Compliance: Ensuring pure white backgrounds (Hex #FFFFFF) with no visible edges or inconsistencies.
Product Integrity: Checking that shape/proportions are accurate (no distortion) and that no parts are missing or cropped.
Retouching Hygiene: Detecting missed defects like dust, scratches, and fingerprints , or harsh cloning marks.
Color Consistency: Monitoring for oversaturation or color shifts and ensuring consistency across angles.
2. Photography Technical Validation
 This layer analyzes the raw photographic quality. The AI must detect:
Technical Errors: Issues with sharpness/focus and unintentional motion blur.
Exposure: Identifying over/underexposed images and ensuring correct white balance.
Composition: Verifying the subject is framed correctly and the background is free of distracting elements.
3. Digital Asset Compliance & Metadata
 This layer focuses on file governance and brand safety. The system needs to check:
Brand Compliance: Flagging unauthorized logos, watermarks, or text to ensure the image meets marketplace standards.
File Specs: Validating resolution (e.g., 300 DPI) , color profiles (RGB vs CMYK) , and preventing upscaling artifacts.

