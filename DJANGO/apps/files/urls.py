from django.urls import path, include

from rest_framework.routers import SimpleRouter

from .views import (
    FileSystemNodeViewSet,
    UserFilePermissionViewSet,
    FileLockViewSet,
    GroupFilePermissionViewSet,
    PresignedURLViewSet,
    NetworkDriveViewSet
)


router = SimpleRouter()

router.register(
    r'nodes',
    FileSystemNodeViewSet,
    basename='node'
)

router.register(
    r'permissions',
    UserFilePermissionViewSet,
    basename='file-permission'
)

router.register(
    r'locks',
    FileLockViewSet,
    basename='file-lock'
)

router.register(
    r'group-permissions',
    GroupFilePermissionViewSet,
    basename='group-file-permission'
)

router.register(
    r'presigned-urls',
    PresignedURLViewSet,
    basename='presigned-url'
)

router.register(
    r'network-drives',
    NetworkDriveViewSet,
    basename='network-drive'
)


urlpatterns = [

    # Download protegido de ficheiro
    path(
        'nodes/<uuid:pk>/download/',
        FileSystemNodeViewSet.as_view(
            {
                'get': 'download'
            }
        ),
        name='node-download'
    ),

    # API principal
    path(
        '',
        include(router.urls)
    ),
]