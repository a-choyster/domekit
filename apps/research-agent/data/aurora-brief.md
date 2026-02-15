# Project Aurora — Brief

**Lead:** Dr. Elena Vasquez
**Status:** Active | **Budget:** $420,000

## Objective
Develop a federated-learning pipeline that trains medical-imaging models
across hospital sites *without* transmitting raw patient data.

## Key Constraints
- All gradient aggregation must happen on-device.
- No image pixels may leave the originating node.
- Model updates are differentially private (epsilon < 2.0).

## Milestones
| Quarter | Target |
|---------|--------|
| Q1 2025 | Prototype round-trip on 3 simulated sites |
| Q2 2025 | Gradient compression integration |
| Q3 2025 | Clinical partner onboarding (2 hospitals) |
