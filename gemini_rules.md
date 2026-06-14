# Angel Quant - Project Context & Rules

This file serves as the memory and guideline document for the Angel Quant project. When interacting with an AI assistant, reference this file to quickly regain context on the UI/UX standards, architecture, and coding preferences.

## 1. Technology Stack & Architecture
- **Backend**: Python, Flask.
- **AI Integration**: Uses the `google-genai` SDK. Models in use: `gemini-2.5-flash`. 
  - *Rule*: AI responses are handled via **Server-Sent Events (SSE)** for real-time streaming directly to the frontend.
- **Frontend**: Vanilla HTML/JS/CSS (No Tailwind).
- **Logging**: Centralized logging using a custom `RequestFilter` in `app.py`. 
  - *Rule*: Always capture the real client IP using headers (`CF-Connecting-IP`, `X-Real-IP`, `X-Forwarded-For`) to avoid capturing the app's proxy URL.

## 2. UI/UX Design System: "Sage & Stone"
The application adheres to a highly specific, clean, and professional mineral tones theme.
- **Layout**: Full-screen web-app dashboard. Persistent left sidebar with dynamic main content swapping.
- **Sidebar**: Deep charcoal-sage (`#2b3233`). Active tabs have a glassy, mineral-blue backlit glow (`rgba(136, 171, 165, 0.4)`).
- **Background**: Textured stone background via `bg.png` (`background-blend-mode: multiply` is applied for theme compatibility).
- **Card Structures**: Main content is wrapped in `.card` classes.
  - **Headers**: Sage-Grey (`#8a9a98` light / `#2b3233` dark).
  - **Bodies**: Off-white (`#f8faf9` light / `#333b3c` dark).
- **Dark Mode**: Uses soft, readable slate/charcoal tones (`#262d2e` for background) rather than stark black to maintain the grounded, mineral aesthetic.

## 3. Frontend Structure (`index.html` & `main.js`)
- All UI sections (CSV Candle Data, AI Market Intelligence, Chart Window, Backtesting) are contained within `index.html` as hidden/visible divs (`content-live`, `content-ai`).
- State management and DOM updates are handled purely via vanilla JavaScript in `static/js/main.js`. 
- *Rule*: When adding new features, extend the existing sidebar navigation and `.card` wrappers rather than creating entirely new HTML pages.

## 4. Development Guidelines
1. **Preserve the Theme**: Before adding new UI elements, consult the CSS Custom Properties (`:root` and `[data-theme="dark"]`) in `index.html` to ensure colors match the Sage & Stone palette.
2. **Error Handling**: Use the built-in `.error-message` CSS class for displaying front-end errors.
3. **Data Display**: Always use the `.table-responsive` and `.data-table` classes for financial data to ensure it adheres to the sticky-header, hover-row styling.
