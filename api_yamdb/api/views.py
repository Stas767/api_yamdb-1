from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from django.db.models import Avg
from django.db import IntegrityError

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.permissions import (IsAuthenticated,
                                        IsAuthenticatedOrReadOnly)
from rest_framework.serializers import ValidationError
from rest_framework import status
from rest_framework import mixins, viewsets
from rest_framework import filters

from rest_framework_simplejwt.tokens import AccessToken

import pyotp

from api.filters import TitleFilter
from api_yamdb.settings import DEFAULT_FROM_EMAIL
from reviews.models import User, Category, Genre, Title, Review
from .permissions import (IsAdminOrSuperUser,
                          IsModeratorOrIsOwner)
from .serializers import (
    UserSerializer,
    SignUpSerializer,
    LoginUserSerializer,
    CategorySerializer,
    CommentSerializer,
    GenreSerializer,
    TitleSerializer,
    TitlePostPatchSerializer,
    ReviewSerializer,
)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = 'username'
    permission_classes = (IsAdminOrSuperUser,)
    filter_backends = (filters.SearchFilter, )
    search_fields = ('username',)

    @action(detail=False, methods=['get'],
            permission_classes=(IsAuthenticated,))
    def me(self, request):
        me = request.user
        serializer = self.get_serializer(me)

        return Response(serializer.data, status=status.HTTP_200_OK)

    @me.mapping.patch
    def patch_me(self, request):
        me = request.user
        serializer = self.get_serializer(me, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(role=me.role)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        partial = kwargs.get('partial', False)
        if not partial:
            raise Response(exception=MethodNotAllowed(method='PUT'))

        return super().update(request, *args, **kwargs)


class SignUpView(APIView):

    def send_mail(self, otp, email):

        return send_mail('Токен OTP',
                         f'Для получения API-токена '
                         f'используйте следующий confirmation_code: {otp}',
                         DEFAULT_FROM_EMAIL,
                         (email,))

    def post(self, request):
        serializer = SignUpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data['username']
        email = serializer.validated_data['email']
        try:
            _existence_user, created = User.objects.get_or_create(
                username=username, email=email)
        except IntegrityError:

            return Response(serializer.errors,
                            status=status.HTTP_400_BAD_REQUEST)

        otp = pyotp.random_base32()
        _existence_user.otp = otp
        _existence_user.save()
        self.send_mail(otp, email)

        return Response(serializer.data, status=status.HTTP_200_OK)


class LoginUserView(APIView):

    def post(self, request):
        serializer = LoginUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = get_object_or_404(User, username=data['username'])
        if user.otp != data['confirmation_code']:
            return Response(
                exception=ValidationError(
                    'Неверное имя пользователя или пароль.'),
                status=status.HTTP_400_BAD_REQUEST
            )

        refresh = AccessToken.for_user(user)
        user.otp = ''  # Удаляем ОТР после выдачи токена
        user.save()
        return Response({'token': str(refresh.access_token), },
                        status=status.HTTP_200_OK)


class CreateListDel(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet
):
    filter_backends = (filters.SearchFilter,)
    search_fields = ('name',)
    lookup_field = 'slug'


class CategoryViewSet(CreateListDel):
    permission_classes = (IsAdminOrSuperUser,)
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.action == 'list':

            return (IsAuthenticatedOrReadOnly(), )

        return super().get_permissions()


class GenreViewSet(CreateListDel):
    permission_classes = (IsAdminOrSuperUser,)
    queryset = Genre.objects.all()
    serializer_class = GenreSerializer

    def get_permissions(self):
        if self.action == 'create' or self.action == 'destroy':

            return (IsAdminOrSuperUser(),)
        if self.action == 'list':

            return (IsAuthenticatedOrReadOnly(), )

        return super().get_permissions()


class TitleViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAdminOrSuperUser,)
    queryset = (
        Title.objects.all().annotate(_average_rating=Avg('reviews__score')))
    serializer_class = TitleSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = TitleFilter

    def get_serializer_class(self):
        if self.action == 'create' or self.action == 'partial_update':

            return TitlePostPatchSerializer

        return TitleSerializer

    def get_permissions(self):
        if (self.action == 'create'
           or self.action == 'destroy'
           or self.action == 'partial_update'):

            return (IsAdminOrSuperUser(),)

        if self.action == 'list' or self.action == 'retrieve':

            return (IsAuthenticatedOrReadOnly(), )

        return super().get_permissions()


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = (IsModeratorOrIsOwner,)

    def get_serializer_context(self):
        context = super(ReviewViewSet, self).get_serializer_context()
        title = get_object_or_404(Title, id=self.kwargs.get('title_id'))
        context.update({'title': title})

        return context

    def get_queryset(self):
        title_id = self.kwargs.get('title_id')
        title = get_object_or_404(Title, pk=title_id)

        return title.reviews.all()

    def perform_create(self, serializer):
        title_id = self.kwargs.get('title_id')
        title = get_object_or_404(Title, pk=title_id)
        serializer.save(author=self.request.user, title=title)

        return title.reviews.all()


class CommentViewSet(viewsets.ModelViewSet):
    serializer_class = CommentSerializer
    permission_classes = (IsModeratorOrIsOwner,)

    def get_queryset(self):
        review_id = self.kwargs.get('review_id')
        review = get_object_or_404(Review, pk=review_id)

        return review.comments.all()

    def perform_create(self, serializer):
        review_id = self.kwargs.get('review_id')
        review = get_object_or_404(Review, pk=review_id)
        serializer.save(author=self.request.user, review=review)
