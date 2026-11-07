from app.core.logging import configure_logging
from app.services.analysis_worker import run

if __name__ == "__main__":
    configure_logging()
    run()
