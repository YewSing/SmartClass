# Import all models here in dependency order so SQLAlchemy's mapper
# has all classes registered before any query or migration runs.
from app.models.user import User, Student, Lecturer  # noqa: F401
from app.models.class_ import Course, ClassOccurrence, Enrollment  # noqa: F401
from app.models.face import FaceEmbedding  # noqa: F401
from app.models.camera import Camera  # noqa: F401
from app.models.session import AttendanceSession  # noqa: F401
from app.models.attendance import AttendanceRecord  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.face_review import FaceReviewEntry  # noqa: F401
