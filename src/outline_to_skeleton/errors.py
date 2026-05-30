class OutlineToSkeletonError(RuntimeError):
    """Base error for outline-to-centerline conversion."""


class OutlineExtractionError(OutlineToSkeletonError):
    pass


class PolygonRepairError(OutlineToSkeletonError):
    pass


class SkeletonExtractionError(OutlineToSkeletonError):
    pass


class RobotPathError(OutlineToSkeletonError):
    pass


class ZDepthError(OutlineToSkeletonError):
    pass
