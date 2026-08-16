from app import create_app
from app.extensions import db

app = create_app()


@app.cli.command("init-db")
def init_db():
    """Create empty tables."""
    with app.app_context():
        db.create_all()
        print("Database tables created.")


@app.cli.command("seed")
def seed_cmd():
    """Create tables, train the AI model if needed, and load demo data."""
    from app.services.seed import seed_all

    with app.app_context():
        seed_all()
        print("Seed complete.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        from app.models import Student

        if Student.query.count() == 0:
            from app.services.seed import seed_all

            print("Empty database detected — running first-time seed...")
            seed_all()
        else:
            from app.services.seed import ensure_demo_alert

            ensure_demo_alert()
    app.run(debug=True, host="127.0.0.1", port=5000)
