from rest_framework import permissions
from rest_framework.permissions import BasePermission


class IsAdminOrSuperUser(BasePermission):
    def has_permission(self, request, view):
        return (request.user.is_authenticated and request.user.role == 'admin'
                or request.user.is_superuser)
    
    def has_object_permission(self, request, view, obj):

        return (request.user.is_authenticated and request.user.role == 'admin'
                or request.user.is_superuser)

# class IsAdminOrSuperUser(BasePermission):
#     def has_permission(self, request, view):
#         if request.user.is_authenticated:
#             return request.user.role == 'admin' or request.user.is_superuser


class IsModeratorOrIsOwner(BasePermission):
    def has_permission(self, request, view):

        
        return (request.user.is_authenticated
        or request.method in permissions.SAFE_METHODS)
    
    def has_object_permission(self, request, view, obj):

        return ((request.user.is_authenticated and request.user.role == 'admin')
        or (request.user.is_authenticated and  request.user.role == 'moderator')
        or (request.user.is_authenticated and  request.user.is_superuser)
        or (request.user.is_authenticated and  obj.author == request.user)
        or (request.method in permissions.SAFE_METHODS))


class AuthorOrReadOnly(permissions.BasePermission):

    def has_permission(self, request, view):
        
        return (request.user.is_authenticated)



class ReadOnly(permissions.BasePermission):

    def has_permission(self, request, view):
        return (request.method in permissions.SAFE_METHODS
                or request.user.is_authenticated)
