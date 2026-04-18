# Spherecast Material Substitute Finder - UI

This directory contains the frontend user interface for the Spherecast Material Substitute Finder application.

## Files Structure

```
frontend/
├── index.html              # Main HTML page
├── styles/
│   └── main.css           # Main stylesheet
├── components/            # JavaScript components
│   ├── ScoreBreakdown.js  # 5D scoring visualization
│   ├── ResultsList.js     # Top candidates display
│   ├── ComparisonView.js  # Original vs candidate comparison
│   ├── WeightSliders.js   # Scoring weights adjustment
│   ├── SearchForm.js      # Material search form
│   ├── RejectedList.js    # Rejected candidates display
│   └── CandidateCard.js   # Individual candidate details
└── utils/
    └── api.js             # API client for backend communication
```

## Features

### 5D Scoring Visualization
- **ScoreBreakdown Component**: Interactive visualization of the five scoring dimensions
  - Spec Similarity (40%) - Semantic material similarity
  - Compliance (25%) - Certification matching
  - Price Delta (15%) - Price difference analysis
  - Lead Time (10%) - Delivery time comparison
  - Quality Signals (10%) - Supplier quality indicators

### Interactive Components
- **Search Form**: Input form for material search with validation
- **Results List**: Display top material candidates with mini score previews
- **Comparison View**: Side-by-side comparison of original vs candidate materials
- **Weight Sliders**: Demo feature to adjust scoring weights in real-time
- **Rejected List**: Expandable list of materials filtered out during scoring

### Responsive Design
- Mobile-friendly responsive layout
- Modern CSS with gradients and animations
- Accessible color schemes and typography

## Usage

### Local Development
1. Start the backend API server
2. Serve the frontend files:
   ```bash
   cd src/ui/frontend
   python -m http.server 8000
   ```
3. Open http://localhost:8000 in your browser

### Integration with Backend
The UI communicates with the FastAPI backend through the `api.js` client:
- `POST /search` - Search for material substitutes
- `GET /results/{id}` - Retrieve search results
- `GET/PUT /config` - Get/update scoring weights
- `POST /rescore/{id}` - Rescore with new weights

## Scoring Dimensions

### 1. Spec Similarity (40%)
- Uses OpenAI embeddings for semantic similarity
- Optimized for supplements/food materials
- Considers synonyms, functions, and applications

### 2. Compliance (25%)
- Certification matching and regulatory compliance
- Set intersection of required vs available certifications

### 3. Price Delta (15%)
- Percentage price difference with capping
- Considers incoterms and currency

### 4. Lead Time (10%)
- Delivery time comparison with tolerance
- Accounts for stock availability

### 5. Quality Signals (10%)
- Supplier ratings and reliability indicators
- On-time delivery, defect rates, business longevity

## Demo Features

- **Weight Adjustment**: Modify scoring weights to see how rankings change
- **Real-time Rescoring**: Apply new weights without re-searching
- **Detailed Comparisons**: Drill down into material specifications
- **Confidence Indicators**: Visual confidence levels for each score

## Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- ES6+ JavaScript modules
- CSS Grid and Flexbox
- No external dependencies (vanilla JS/CSS)

## Development Notes

- Components use modern ES6 classes
- Event-driven architecture with custom events
- Responsive design with CSS Grid
- Accessible markup and keyboard navigation
- Modular CSS with BEM-like naming convention