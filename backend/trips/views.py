import logging

from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import TripAskSerializer
from .services.errors import TripPlanningError
from .services.plan_trip import plan_the_trip

log = logging.getLogger(__name__)


class PlanTripView(APIView):
    """POST /api/plan-trip/  -> 3 routes + checkpoints + risk + heatmap"""

    def post(self, request):
        ask = TripAskSerializer(data=request.data)
        ask.is_valid(raise_exception=True)
        data = ask.validated_data
        try:
            plan = plan_the_trip(
                origin_text=data["origin"],
                destination_text=data["destination"],
                departure=data["departure_iso"],
                load_lbs=data["load_lbs"],
                sample_miles=int(data["sample_miles"]),
            )
        except TripPlanningError as exc:
            # these are "nice" errors we expect (bad city name, api down etc)
            return Response({"detail": str(exc)}, status=exc.status_code)
        except Exception:  # noqa: BLE001 - last line of defense so the UI gets JSON not a crash page
            log.exception("trip planning blew up")
            return Response(
                {"detail": "Something broke while planning the trip. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(plan)


class HealthView(APIView):
    """GET /api/health/ just says hi so hosting sites know we're alive"""

    throttle_classes = []

    def get(self, request):
        return Response({"ok": True})


def show_the_react_app(request):
    """sends the built react index.html (only works after `npm run build`)"""
    index = settings.FRONTEND_DIST / "index.html"
    if not index.exists():
        return HttpResponse(
            "Frontend not built yet. Run `npm run build` in /frontend, or use the Vite dev server on :5173.",
            status=404,
            content_type="text/plain",
        )
    return HttpResponse(index.read_text(encoding="utf-8"), content_type="text/html")
