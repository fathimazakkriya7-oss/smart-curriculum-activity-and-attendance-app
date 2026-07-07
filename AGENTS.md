# AGENTS instructions

This workspace is a small Flask attendance app.

## Project shape
- Main app entry point: app.py
- Flask routes live in routes/ and should stay focused on one feature area (auth, students, attendance, curriculum, activities)
- SQLAlchemy models live in models/
- HTML templates live in templates/ and static assets live in static/

## Working conventions
- Prefer small, targeted changes that match the existing Flask structure
- Keep new routes, templates, and models organized by feature area
- If you add a route, make sure the corresponding template or behavior is also wired up consistently
- The app uses SQLite via Flask-SQLAlchemy; avoid introducing unrelated database changes

## Common commands
- Run the app locally with: python app.py

## Notes
- The project appears to be in early development, so preserve existing file organization and avoid unnecessary refactors
