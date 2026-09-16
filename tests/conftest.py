import io
import shutil
import tempfile
from pathlib import Path
import pytest
from PIL import Image as PILImage
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.services.gemini import GeminiService, get_gemini_service
from app.services.storage import LocalStorageService, get_storage_service


@pytest.fixture(scope="session")
def sample_image_bytes() -> bytes:
    """Generate a real 200x200 JPEG image in memory for testing file uploads."""
    img = PILImage.new("RGB", (200, 200), color=(120, 120, 120))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(scope="session")
def sample_png_bytes() -> bytes:
    """Generate a real 200x200 PNG image in memory."""
    img = PILImage.new("RGB", (200, 200), color=(80, 100, 140))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for file storage during testing."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def test_db_session(temp_dir):
    """Provide an isolated SQLite database session for each test."""
    db_path = Path(temp_dir) / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_db_session, temp_dir):
    """FastAPI TestClient with isolated database and storage."""
    temp_storage = LocalStorageService(base_dir=temp_dir)
    mock_gemini = GeminiService(api_key="mock")

    # Dependency overrides
    app.dependency_overrides[get_db] = lambda: test_db_session
    app.dependency_overrides[get_storage_service] = lambda: temp_storage
    app.dependency_overrides[get_gemini_service] = lambda: mock_gemini

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
