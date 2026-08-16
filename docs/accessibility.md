# Smart ELMS accessibility notes

These notes support Mohammad Hafeez's WCAG 2.1 Level AA objective. They record what is built into the interface. WAVE and Lighthouse still need to be run in Chrome before the professor meeting so the report can include live scores.

## Built into the pages

- Semantic landmarks: `header`, `nav`, `main`, `aside`, headings in order.
- Skip to content on sign-in, register, forgot password, and every signed-in page.
- Labels tied to controls with `for` / `id` on authentication, class, milestone, quiz builder, and submit forms.
- Remember me, file upload, and search fields have accessible names.
- File dropzone is a keyboard button (Enter or Space opens the file picker).
- Errors use `role="alert"`. Confirmation and quiz results use `role="status"`.
- Focus is visible (`:focus-visible` outline).
- Colour contrast uses navy `#1B365D`, primary blue `#3B6FF5`, and dark text on light cards.
- The AI reminder is a yellow banner with a support link. It is a prompt, not a red failing grade.
- Responsive breakpoints: 320px, 768px, 1024px, 1440px. Short nav labels stay readable on tablet. Mobile uses a bottom bar plus a Sign out control in the top bar.

## How to capture WAVE and Lighthouse

1. Start the app and sign in as the student.
2. In Chrome, open Lighthouse (DevTools, Lighthouse tab). Run Accessibility on Dashboard, Courses, Submit, and Support. Save the scores.
3. Install the WAVE extension. Scan Login, Dashboard, Submit, Instructor dashboard, and Milestones. Fix any remaining contrast or label warnings and re-scan.
4. Repeat at 320px, 768px, 1024px and 1440px widths.
5. Spot-check Firefox and Edge. Safari if a Mac is available.

## Known demo limits

- Forgot password does not send email. That is intentional for a synthetic demonstration.
- WAVE / Lighthouse numbers are not stored in this folder because they must be taken from a real browser session.
- Charts are PNG images. Each figure has an `alt` title. They are not interactive SVG.
