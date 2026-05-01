# XAI Code Audit - Development Setup

## Quick Start

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Start development server:**
   ```bash
   npm start
   ```

3. **Build for production:**
   ```bash
   npm run build
   ```

## Features Overview

### 🏠 Landing Page
- Modern hero section with project branding
- Feature highlights with smooth animations
- Dark/light mode toggle
- Responsive design for all devices

### 📝 Code Input
- Drag & drop file upload
- Syntax highlighting
- Support for multiple languages (JS, TS, Python, Java, C++, etc.)
- Real-time validation

### 🔍 Risk Detection
- AI-powered security analysis
- Severity classification (High/Medium/Low)
- Interactive charts and visualizations
- Filterable results table

### 🧠 Explainable AI
- Detailed explanations for each risk
- Code snippet highlighting
- Exploit scenarios
- Recommended fixes
- AI confidence scores

### 📊 Analytics Dashboard
- Key performance indicators
- Trend analysis
- Risk concentration heatmap
- Category distribution charts

### 📄 Audit Reports
- Export in PDF, Excel, HTML formats
- Comprehensive risk summaries
- Detailed findings and recommendations
- Professional report templates

## Technology Stack

- **Frontend:** React 18 + TypeScript
- **Styling:** TailwindCSS + Custom CSS
- **Animations:** Framer Motion
- **Charts:** Recharts
- **Icons:** Lucide React
- **Routing:** React Router DOM

## Project Structure

```
src/
├── components/           # React components
│   ├── LandingPage.tsx
│   ├── Dashboard.tsx
│   ├── CodeInput.tsx
│   ├── RiskResults.tsx
│   ├── Explainability.tsx
│   ├── AnalyticsDashboard.tsx
│   └── AuditReport.tsx
├── contexts/            # React contexts
│   └── ThemeContext.tsx
├── App.tsx              # Main app
├── index.tsx            # Entry point
└── index.css            # Global styles
```

## Customization

### Colors
The color scheme can be customized in `tailwind.config.js`:
- Primary: Blue theme
- Danger: Red for high severity
- Warning: Orange for medium severity  
- Success: Green for low severity

### Animations
Animations are handled by Framer Motion with custom easing and timing.

### Dark Mode
Automatic dark mode detection with manual toggle option.

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Development Notes

- Uses React 18 with TypeScript for type safety
- TailwindCSS for rapid styling
- Framer Motion for smooth animations
- Responsive design with mobile-first approach
- Accessibility features included
- SEO optimized with proper meta tags
