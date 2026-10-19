from django.urls import include, path, re_path

from trips.views import show_the_react_app

urlpatterns = [
    path("api/", include("trips.urls")),
    # anything thats not the api goes to the react app (so refreshing the page works)
    re_path(r"^(?!api/|static/).*$", show_the_react_app, name="spa"),
]
